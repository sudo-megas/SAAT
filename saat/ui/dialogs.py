from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout, QWidget

from saat.models import Watch

# SPEC.md §6: ruby appears in exactly two places in the whole app — delete,
# and the unsaved-changes warning. Both dialogs in this module use it.


class DeleteConfirmDialog(QDialog):
    """Delete requires typing the model name to confirm. See SPEC.md §5.6."""

    def __init__(self, watch: Watch, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._brand = watch.brand
        self._model = watch.model

        layout = QVBoxLayout(self)
        self._message = QLabel()
        self._message.setWordWrap(True)
        layout.addWidget(self._message)

        self._input = QLineEdit()
        self._input.textChanged.connect(self._update_enabled)
        layout.addWidget(self._input)

        buttons = QDialogButtonBox()
        cancel_button = buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
        cancel_button.clicked.connect(self.reject)
        self._delete_button = QPushButton()
        self._delete_button.setProperty("variant", "destructive")
        self._delete_button.setEnabled(False)
        self._delete_button.clicked.connect(self.accept)
        buttons.addButton(self._delete_button, QDialogButtonBox.ButtonRole.DestructiveRole)
        layout.addWidget(buttons)

        self._retranslate()

    def _retranslate(self) -> None:
        self.setWindowTitle(self.tr("Delete watch"))
        self._message.setText(
            self.tr('This moves "{brand} {model}" to backups/deleted/. Type the model name ("{model}") to confirm.').format(
                brand=self._brand, model=self._model
            )
        )
        self._delete_button.setText(self.tr("Delete"))

    def changeEvent(self, event: QEvent) -> None:
        # Rare (needs a language switch delivered while this modal is
        # still open -- see the plan's note on tray delivery into a
        # nested exec() loop not being a verified-impossible path) but
        # cheap to handle correctly, same as every other widget in this
        # sweep -- built uniformly rather than betting on the unverified
        # assumption that it can't happen.
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)

    def _update_enabled(self, text: str) -> None:
        self._delete_button.setEnabled(text == self._model)


def confirm_discard_changes(parent: QWidget | None) -> bool:
    """SPEC.md §5.7: closing with unsaved changes prompts."""
    box = QMessageBox(parent)
    box.setWindowTitle(QCoreApplication.translate("Dialogs", "Discard changes?"))
    box.setText(QCoreApplication.translate("Dialogs", "You have unsaved changes. Discard them?"))
    discard_button = box.addButton(
        QCoreApplication.translate("Dialogs", "Discard"), QMessageBox.ButtonRole.DestructiveRole
    )
    discard_button.setProperty("variant", "destructive")
    cancel_button = box.addButton(
        QCoreApplication.translate("Dialogs", "Cancel"), QMessageBox.ButtonRole.RejectRole
    )
    box.setDefaultButton(cancel_button)
    box.exec()
    return box.clickedButton() is discard_button
