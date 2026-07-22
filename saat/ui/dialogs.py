from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout, QWidget

from saat.models import Watch

# SPEC.md §6: ruby appears in exactly two places in the whole app — delete,
# and the unsaved-changes warning. Both dialogs in this module use it.


class DeleteConfirmDialog(QDialog):
    """Delete requires typing the model name to confirm. See SPEC.md §5.6."""

    def __init__(self, watch: Watch, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Delete watch")
        self._model = watch.model

        layout = QVBoxLayout(self)
        message = QLabel(
            f'This moves "{watch.brand} {watch.model}" to backups/deleted/. '
            f'Type the model name ("{watch.model}") to confirm.'
        )
        message.setWordWrap(True)
        layout.addWidget(message)

        self._input = QLineEdit()
        self._input.textChanged.connect(self._update_enabled)
        layout.addWidget(self._input)

        buttons = QDialogButtonBox()
        cancel_button = buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
        cancel_button.clicked.connect(self.reject)
        self._delete_button = QPushButton("Delete")
        self._delete_button.setProperty("variant", "destructive")
        self._delete_button.setEnabled(False)
        self._delete_button.clicked.connect(self.accept)
        buttons.addButton(self._delete_button, QDialogButtonBox.ButtonRole.DestructiveRole)
        layout.addWidget(buttons)

    def _update_enabled(self, text: str) -> None:
        self._delete_button.setEnabled(text == self._model)


def confirm_discard_changes(parent: QWidget | None) -> bool:
    """SPEC.md §5.7: closing with unsaved changes prompts."""
    box = QMessageBox(parent)
    box.setWindowTitle("Discard changes?")
    box.setText("You have unsaved changes. Discard them?")
    discard_button = box.addButton("Discard", QMessageBox.ButtonRole.DestructiveRole)
    discard_button.setProperty("variant", "destructive")
    cancel_button = box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(cancel_button)
    box.exec()
    return box.clickedButton() is discard_button
