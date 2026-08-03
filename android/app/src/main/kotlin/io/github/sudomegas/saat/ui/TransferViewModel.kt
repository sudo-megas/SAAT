package io.github.sudomegas.saat.ui

import android.content.ContentResolver
import android.net.Uri
import android.provider.OpenableColumns
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import io.github.sudomegas.saat.SaatApplication
import io.github.sudomegas.saat.storage.ExportSummary
import io.github.sudomegas.saat.storage.ImportSummary
import io.github.sudomegas.saat.storage.SaatPaths
import io.github.sudomegas.saat.storage.WatchRepository
import io.github.sudomegas.saat.storage.exportCollection
import io.github.sudomegas.saat.storage.importCollection
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * Export and import — SPEC-ANDROID 3.2, the bridge to the desktop app.
 *
 * Separate from `SettingsViewModel` because the two have nothing in common
 * beyond living on the same screen: one flips three preferences, the other
 * streams a collection through a `ContentResolver` on a background dispatcher
 * and has a running state, a progress figure and three ways to fail.
 */
data class TransferUiState(
    val isRunning: Boolean = false,
    /** Files finished and files total, or null before the first callback. */
    val progress: Progress? = null,
    /** Shown once, then cleared by the screen. */
    val result: TransferResult? = null,
)

data class Progress(val done: Int, val total: Int)

sealed interface TransferResult {
    data class Exported(val summary: ExportSummary, val destination: String) : TransferResult

    data class Imported(val summary: ImportSummary) : TransferResult

    /**
     * Hard rule 6: the message reaches the UI intact rather than becoming a log
     * line. A failed export is one of the few things in this app that can lose
     * an afternoon, and "it didn't work" is not enough to act on.
     */
    data class Failed(val message: String) : TransferResult
}

class TransferViewModel(
    private val resolver: ContentResolver,
    private val paths: SaatPaths,
    private val repository: WatchRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(TransferUiState())
    val state: StateFlow<TransferUiState> = _state.asStateFlow()

    /**
     * Write the collection to a document the owner picked.
     *
     * All of it on [Dispatchers.IO]: this reads every photograph in the
     * collection off disk and deflates it, which is exactly the sort of work
     * that turns into a dropped frame count on the main thread.
     *
     * The URI's display name is read back rather than assumed, because
     * `ACTION_CREATE_DOCUMENT` lets the owner rename the file in the picker and
     * a completion notice naming a file that is not there would be worse than
     * naming none.
     */
    fun export(destination: Uri) {
        if (_state.value.isRunning) return
        _state.value = TransferUiState(isRunning = true)

        viewModelScope.launch {
            val outcome = withContext(Dispatchers.IO) {
                runCatching {
                    val summary = resolver.openOutputStream(destination)
                        ?.use { out ->
                            exportCollection(paths, out) { done, total ->
                                _state.value = _state.value.copy(progress = Progress(done, total))
                            }
                        }
                        ?: error("Could not open $destination for writing")

                    TransferResult.Exported(summary, resolver.displayName(destination))
                }
            }

            _state.value = TransferUiState(
                result = outcome.getOrElse { TransferResult.Failed(it.messageForUi()) },
            )
        }
    }

    /**
     * Read an archive the owner picked into the collection.
     *
     * The URI is opened TWICE — `importCollection` surveys the archive before it
     * writes anything, and `ZipInputStream` cannot seek — so a factory is passed
     * rather than a stream. `openInputStream` on a Storage Access Framework
     * document is reopenable for as long as the permission grant lasts, which
     * for a one-shot `ACTION_OPEN_DOCUMENT` result is the life of this call.
     *
     * The repository is reloaded afterwards rather than being told what changed:
     * the files on disk are the truth (hard rule 4), and re-reading them is both
     * simpler and impossible to get out of step with what was actually written.
     */
    fun import(source: Uri) {
        if (_state.value.isRunning) return
        _state.value = TransferUiState(isRunning = true)

        viewModelScope.launch {
            val outcome = withContext(Dispatchers.IO) {
                runCatching {
                    val summary = importCollection(
                        paths = paths,
                        open = {
                            resolver.openInputStream(source)
                                ?: error("Could not open $source for reading")
                        },
                        onProgress = { done, total ->
                            _state.value = _state.value.copy(progress = Progress(done, total))
                        },
                    )
                    TransferResult.Imported(summary)
                }
            }

            // Only when something actually landed. A refused archive changed
            // nothing, and a reload would be work done to discover that.
            if ((outcome.getOrNull() as? TransferResult.Imported)?.summary?.added?.isNotEmpty() == true) {
                repository.load()
            }

            _state.value = TransferUiState(
                result = outcome.getOrElse { TransferResult.Failed(it.messageForUi()) },
            )
        }
    }

    fun clearResult() {
        _state.value = _state.value.copy(result = null)
    }

    companion object {
        fun factory(app: SaatApplication): ViewModelProvider.Factory =
            object : ViewModelProvider.Factory {
                @Suppress("UNCHECKED_CAST")
                override fun <T : ViewModel> create(modelClass: Class<T>): T =
                    TransferViewModel(
                        resolver = app.contentResolver,
                        paths = app.paths,
                        repository = app.watchRepository,
                    ) as T
            }
    }
}

/**
 * The file's name as the picker knows it, falling back to the URI itself.
 *
 * A query rather than `uri.lastPathSegment`, which for a Storage Access
 * Framework document is an opaque provider id like `msf:1000000042` and would
 * name nothing the owner could find.
 */
internal fun ContentResolver.displayName(uri: Uri): String {
    val name = runCatching {
        query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { cursor ->
            val column = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
            if (column >= 0 && cursor.moveToFirst()) cursor.getString(column) else null
        }
    }.getOrNull()

    return name?.takeIf { it.isNotBlank() } ?: uri.toString()
}

/** Never an empty string: an exception class with no message still says something. */
internal fun Throwable.messageForUi(): String =
    message?.takeIf { it.isNotBlank() } ?: this::class.java.simpleName
