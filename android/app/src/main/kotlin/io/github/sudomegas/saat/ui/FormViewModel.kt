package io.github.sudomegas.saat.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import io.github.sudomegas.saat.SaatApplication
import io.github.sudomegas.saat.storage.Watch
import io.github.sudomegas.saat.storage.WatchImages
import io.github.sudomegas.saat.storage.WatchRepository
import io.github.sudomegas.saat.storage.safeImageFilename
import io.github.sudomegas.saat.ui.form.FormImage
import io.github.sudomegas.saat.ui.form.WatchFormState
import io.github.sudomegas.saat.ui.form.toWatch
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File
import java.util.UUID

/**
 * The add/edit form's state holder — SPEC-ANDROID 5.7.
 *
 * A ViewModel rather than `remember`, and that is a requirement rather than a
 * habit: this milestone's brief asks that rotating the phone mid-edit lose
 * nothing, and a form this size cannot be threaded through `rememberSaveable`
 * field by field without one of them being forgotten. One state object, held
 * across configuration changes, is the version that cannot be partly right.
 *
 * [slug] null means ADD; anything else means edit that watch. The same screen
 * serves both, as the brief requires, and the only differences are where the
 * initial state comes from and whether saving creates or updates.
 */
class FormViewModel(
    private val repository: WatchRepository,
    private val images: WatchImages,
    /** Where a picked or captured photograph waits until the watch is saved. */
    private val stagingDir: File,
    private val slug: String?,
) : ViewModel() {

    /**
     * The state the form opened with, and the whole of the unsaved-changes
     * check. Reassigned on a successful save so that saving and then backing
     * out does not prompt about changes that are already on disk.
     */
    private var initial: WatchFormState = WatchFormState.empty()

    private val _state = MutableStateFlow(initial)
    val state: StateFlow<WatchFormState> = _state.asStateFlow()

    /** True when this form is editing an existing watch rather than adding one. */
    val isEditing: Boolean = slug != null

    /** False until an edit's watch has been read, so the form cannot save a blank over it. */
    private val _isReady = MutableStateFlow(slug == null)
    val isReady: StateFlow<Boolean> = _isReady.asStateFlow()

    /**
     * Every value the collection already uses, for the enum* dropdowns —
     * SPEC.md §4's "plus every value already used elsewhere in the collection".
     */
    val collection: StateFlow<List<Watch>> = repository.state
        .map { state -> state.watches.mapNotNull { it.watch } }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())

    /**
     * Backing out with this true prompts — SPEC-ANDROID 5.7.
     *
     * Structural inequality against the opening state, not a flag set by an
     * edit signal. Typing a character and deleting it comes back equal and asks
     * nothing, which the desktop's signal-based version gets wrong and which is
     * the difference between a prompt that means something and one people learn
     * to dismiss.
     */
    val isDirty: Boolean get() = _state.value != initial

    init {
        if (slug != null) {
            viewModelScope.launch {
                // Waits for the load rather than reading whatever is in memory
                // now: the form can be opened from a cold start, before the
                // collection has finished being read, and seeding from an empty
                // collection would put a blank form over a real watch.
                val collection = repository.state.first { it.isLoaded }
                val watch = collection.records.firstOrNull { it.slug == slug }?.watch
                if (watch != null) {
                    initial = WatchFormState.from(watch)
                    _state.value = initial
                }
                // Ready either way. A watch that will not parse leaves the form
                // blank, and the screen says so rather than spinning forever.
                _isReady.value = true
            }
        }
    }

    fun update(transform: (WatchFormState) -> WatchFormState) {
        _state.update(transform)
    }

    /**
     * A file for the camera to write into, inside the staging directory.
     *
     * Each capture gets its own subdirectory so two photographs taken before a
     * save cannot collide on a name. Nothing here is part of the collection
     * until [save] copies it into `media/<slug>/`.
     */
    fun stagedFile(name: String = DEFAULT_CAPTURE_NAME): File {
        val directory = File(stagingDir, UUID.randomUUID().toString())
        directory.mkdirs()
        return File(directory, safeImageFilename(name))
    }

    /**
     * Stage a picked photograph: copy its bytes into `cacheDir` and add it to
     * the form.
     *
     * The copy runs on the I/O dispatcher, not where the picker's callback left
     * us. A photograph off a modern phone is several megabytes, and reading one
     * through a ContentResolver on the main thread is a visible stall on the
     * frame that follows.
     */
    fun stagePicked(name: String, write: (java.io.OutputStream) -> Unit) {
        viewModelScope.launch {
            val staged = withContext(Dispatchers.IO) {
                val file = stagedFile(name)
                file.outputStream().use(write)
                file
            }
            addStaged(staged)
        }
    }

    /** A photograph the camera has just written into its staged file. */
    fun addStaged(file: File) {
        _state.update { it.copy(images = it.images + FormImage(file.name, file)) }
    }

    /**
     * Write the watch, and its photographs with it. Returns its slug, or null
     * when the write failed.
     *
     * The order is forced by the slug: an import needs somewhere to put a file
     * and a NEW watch has no folder until it has been written once. So a new
     * watch is created first with no photographs, the staged files are then
     * copied in, and the record is written again carrying their names. The
     * second write is a no-op when there are no photographs — the transform
     * produces an equal watch and the repository skips it — so an ordinary
     * add still touches the disk once. It is also the order the desktop uses,
     * for the same reason.
     *
     * `worn` is taken from the record being edited rather than from the form,
     * which does not carry it: wear is the calendar's field and the detail
     * button's, and rebuilding a watch without it would delete a wear history on
     * every edit of an unrelated field.
     */
    suspend fun save(): String? {
        val form = _state.value
        if (!form.canSave) return null

        val target = slug
            ?: repository.create(form.toWatch().copy(images = emptyList()))?.slug
            ?: return null

        val committed = withContext(Dispatchers.IO) {
            // Removals first, then imports — the desktop's order, and the one
            // that lets a photograph be removed and another of the same name
            // added in a single edit.
            form.removedImages.forEach { images.delete(target, it) }
            commitImages(target, form)
        }

        val saved = repository.update(target, backup = slug != null) { existing ->
            form.toWatch(preservedWorn = existing.worn).copy(images = committed)
        } ?: return null

        // What is on disk is now what is on screen, so backing out is not a
        // discard. Anything typed after this point is dirty again.
        initial = form.copy(
            images = committed.map(::FormImage),
            removedImages = emptyList(),
        )
        _state.value = initial
        return saved.slug
    }

    /**
     * Copy every staged photograph into `media/<slug>/`, in the owner's order.
     *
     * Names are re-uniquified against what is actually on disk AND against what
     * this same save has already written, so two photographs picked in one
     * gesture — both called `IMG_0001.jpg`, which is exactly what a camera roll
     * produces — cannot land on each other.
     */
    private fun commitImages(target: String, form: WatchFormState): List<String> {
        val taken = mutableSetOf<String>()
        return form.images.map { image ->
            val staged = image.staged
            if (staged == null) {
                taken += image.filename
                return@map image.filename
            }
            val name = staged.inputStream().use {
                images.import(target, it, image.filename, taken)
            }
            taken += name
            // The staged copy has served its purpose. Its parent directory goes
            // with it so the staging area does not fill up with empty folders.
            staged.delete()
            staged.parentFile?.delete()
            name
        }
    }

    companion object {
        /**
         * Must match the `path` in `res/xml/file_paths.xml`, which is what the
         * FileProvider will hand the camera a URI into. A mismatch is not a
         * compile error — it is an IllegalArgumentException at capture time.
         */
        const val STAGED_IMAGES = "staged-images"

        /** What a camera capture is called before it has a name of its own. */
        const val DEFAULT_CAPTURE_NAME = "photo.jpg"

        fun factory(app: SaatApplication, slug: String?): ViewModelProvider.Factory =
            object : ViewModelProvider.Factory {
                @Suppress("UNCHECKED_CAST")
                override fun <T : ViewModel> create(modelClass: Class<T>): T =
                    FormViewModel(
                        repository = app.watchRepository,
                        images = WatchImages(app.paths),
                        stagingDir = File(app.cacheDir, STAGED_IMAGES),
                        slug = slug,
                    ) as T
            }
    }
}
