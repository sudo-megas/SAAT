package io.github.sudomegas.saat.ui.screens

import android.net.Uri
import android.provider.OpenableColumns
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.size
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.core.content.FileProvider
import coil3.compose.AsyncImagePainter
import coil3.compose.rememberAsyncImagePainter
import io.github.sudomegas.saat.R
import io.github.sudomegas.saat.ui.form.FormImage
import io.github.sudomegas.saat.ui.form.WatchFormState
import java.io.File
import java.io.OutputStream

/**
 * The Images group — SPEC-ANDROID 5.7, and hard rule 2 throughout.
 *
 * TWO WAYS IN, NEITHER OF THEM A PERMISSION. The system Photo Picker returns a
 * `content://` URI for a photograph the owner chose, in a UI this app never
 * sees and cannot influence; `ACTION_IMAGE_CAPTURE` hands the camera app a
 * FileProvider URI to write one file into. Neither asks the owner for anything,
 * and the merged manifest still declares no permission at all — which
 * `verifyReleaseManifestPolicy` re-proves on every build.
 *
 * EVERYTHING IS COPIED, and nothing is referenced. A `content://` URI is a
 * temporary grant to someone else's file: it dies with the process, and it dies
 * for good if the owner clears the gallery app's data. The bytes are read once,
 * here, into a staged file, and become part of the collection when the watch is
 * saved. That is the difference between a record and a bookmark.
 */
@Composable
fun ImagesEditor(
    images: List<FormImage>,
    /** Hands the bytes to the ViewModel, which stages them off the main thread. */
    onPicked: (name: String, write: (OutputStream) -> Unit) -> Unit,
    /** A file for the camera to write into. Not part of the form until it is taken. */
    newCaptureFile: () -> File,
    onCaptured: (File) -> Unit,
    apply: ((WatchFormState) -> WatchFormState) -> Unit,
) {
    val context = LocalContext.current
    var pendingCapture by remember { mutableStateOf<File?>(null) }

    // PickMultipleVisualMedia: the modern picker, no permission, and on devices
    // without it the support library falls back to ACTION_OPEN_DOCUMENT, which
    // needs none either.
    val pick = rememberLauncherForActivityResult(
        ActivityResultContracts.PickMultipleVisualMedia(MAX_PICKED_AT_ONCE)
    ) { uris ->
        uris.forEach { uri ->
            onPicked(context.displayName(uri)) { output ->
                context.contentResolver.openInputStream(uri)?.use { it.copyTo(output) }
            }
        }
    }

    val capture = rememberLauncherForActivityResult(ActivityResultContracts.TakePicture()) { taken ->
        val file = pendingCapture
        pendingCapture = null
        if (!taken || file == null) {
            // Cancelled, or the camera app wrote nothing. The empty staged file
            // it was handed is removed rather than left to become a photograph
            // of nothing at the next save.
            file?.delete()
            file?.parentFile?.delete()
            return@rememberLauncherForActivityResult
        }
        onCaptured(file)
    }

    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            TextButton(onClick = {
                pick.launch(
                    PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly)
                )
            }) {
                Text(text = stringResource(R.string.action_choose_photos))
            }
            TextButton(onClick = {
                val file = newCaptureFile()
                pendingCapture = file
                capture.launch(
                    FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", file)
                )
            }) {
                Text(text = stringResource(R.string.action_take_photo))
            }
        }

        if (images.isEmpty()) {
            Text(
                text = stringResource(R.string.screen_form_images_empty),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }

        images.forEachIndexed { index, image ->
            ImageRow(
                image = image,
                isPrimary = index == 0,
                canMoveUp = index > 0,
                canMoveDown = index < images.lastIndex,
                onSetPrimary = { apply { it.withImageMoved(index, 0) } },
                onMoveUp = { apply { it.withImageMoved(index, index - 1) } },
                onMoveDown = { apply { it.withImageMoved(index, index + 1) } },
                onRemove = { apply { it.withImageRemoved(index) } },
            )
        }
    }
}

@Composable
private fun ImageRow(
    image: FormImage,
    isPrimary: Boolean,
    canMoveUp: Boolean,
    canMoveDown: Boolean,
    onSetPrimary: () -> Unit,
    onMoveUp: () -> Unit,
    onMoveDown: () -> Unit,
    onRemove: () -> Unit,
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        StagedThumbnail(image)
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = image.filename,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurface,
            )
            if (isPrimary) {
                Text(
                    text = stringResource(R.string.screen_form_images_primary),
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.primary,
                )
            }
        }
        if (!isPrimary) {
            TextButton(onClick = onSetPrimary) {
                Text(text = stringResource(R.string.action_set_primary))
            }
        }
        if (canMoveUp) {
            TextButton(onClick = onMoveUp) { Text(text = stringResource(R.string.action_move_up)) }
        }
        if (canMoveDown) {
            TextButton(onClick = onMoveDown) { Text(text = stringResource(R.string.action_move_down)) }
        }
        TextButton(onClick = onRemove) {
            Text(
                text = stringResource(R.string.action_remove),
                color = MaterialTheme.colorScheme.error,
            )
        }
    }
}

/**
 * The staged file if there is one, the saved file otherwise.
 *
 * Coil applies EXIF orientation at decode, which is the whole of "no photo lies
 * on its side" — the bytes on disk keep the tag the camera wrote and are never
 * re-encoded.
 */
@Composable
private fun StagedThumbnail(image: FormImage) {
    val painter = rememberAsyncImagePainter(model = image.staged)
    val state by painter.state.collectAsState()

    Box(
        modifier = Modifier
            .size(48.dp)
            .background(MaterialTheme.colorScheme.surfaceContainerHigh)
            .border(Dp.Hairline, MaterialTheme.colorScheme.outlineVariant),
    ) {
        if (image.staged != null && state !is AsyncImagePainter.State.Error) {
            Image(
                painter = painter,
                contentDescription = null,
                contentScale = ContentScale.Crop,
                modifier = Modifier.fillMaxSize(),
            )
        }
    }
}

/**
 * Move a photograph, keeping the rest in order. Index 0 is the primary —
 * SPEC-ANDROID 5.7's "setting the primary" is this and nothing more, which is
 * also how `Watch.images` stores it.
 */
internal fun WatchFormState.withImageMoved(from: Int, to: Int): WatchFormState {
    if (from !in images.indices || to !in images.indices || from == to) return this
    val reordered = images.toMutableList()
    reordered.add(to, reordered.removeAt(from))
    return copy(images = reordered)
}

/**
 * Remove a photograph.
 *
 * A SAVED file is remembered in [WatchFormState.removedImages] so the save can
 * move it into `backups/deleted/`; a staged one simply disappears, because
 * nothing on disk ever knew about it. Either way, any strap pointing at it is
 * cleared — the desktop does this too, and a strap naming a photograph that is
 * gone would render as a permanently broken thumbnail.
 */
internal fun WatchFormState.withImageRemoved(index: Int): WatchFormState {
    val image = images.getOrNull(index) ?: return this
    image.staged?.let {
        it.delete()
        it.parentFile?.delete()
    }
    return copy(
        images = images.filterIndexed { i, _ -> i != index },
        removedImages = if (image.staged == null) removedImages + image.filename else removedImages,
        straps = straps.map { if (it.image == image.filename) it.copy(image = "") else it },
    )
}

/**
 * The name the picker's file already has, so a photograph keeps the name its
 * owner recognises. Falls back when the provider answers no display name, which
 * some do.
 */
private fun android.content.Context.displayName(uri: Uri): String {
    contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)
        ?.use { cursor ->
            if (cursor.moveToFirst() && !cursor.isNull(0)) return cursor.getString(0)
        }
    return DEFAULT_PICKED_NAME
}

/**
 * The picker's own cap. Higher than any watch needs, low enough that a stray
 * "select all" on a camera roll cannot stage a thousand files into cacheDir.
 */
private const val MAX_PICKED_AT_ONCE = 20

private const val DEFAULT_PICKED_NAME = "photo.jpg"

