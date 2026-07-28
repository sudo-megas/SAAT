from pathlib import Path

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from saat.sellers import Seller, save_sellers


class SellersDialog(QDialog):
    """Add, edit and delete sellers.toml entries. See SPEC.md §3. Each
    action persists immediately via save_sellers() — a direct data manager,
    not a staged edit behind a Save/Cancel gate the way WatchForm is."""

    def __init__(self, sellers: list[Seller], backups_dir: Path, path: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.resize(560, 420)
        self._backups_dir = backups_dir
        self._path = path
        self._sellers = list(sellers)
        self._editing_index: int | None = None

        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_selection_changed)

        self._name = QLineEdit()
        self._url = QLineEdit()
        self._url.setPlaceholderText("https://…")
        self._city = QLineEdit()
        self._notes = QLineEdit()

        self._form = QFormLayout()
        self._form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        # A genuinely empty label string ("") makes QFormLayout skip
        # creating a QLabel at all -- labelForField() would then return
        # None, not a relabelable widget -- confirmed empirically. A
        # placeholder space forces creation; _retranslate() below
        # immediately overwrites it with the real text.
        self._form.addRow(" ", self._name)
        self._form.addRow(" ", self._url)
        self._form.addRow(" ", self._city)
        self._form.addRow(" ", self._notes)

        self._new_button = QPushButton()
        self._new_button.clicked.connect(self._on_new)
        self._save_button = QPushButton()
        self._save_button.clicked.connect(self._on_save)
        self._delete_button = QPushButton()
        self._delete_button.setProperty("variant", "destructive")
        self._delete_button.clicked.connect(self._on_delete)

        buttons_row = QHBoxLayout()
        buttons_row.addWidget(self._new_button)
        buttons_row.addWidget(self._save_button)
        buttons_row.addWidget(self._delete_button)

        right = QVBoxLayout()
        right.addLayout(self._form)
        right.addLayout(buttons_row)
        right.addStretch()
        right_widget = QWidget()
        right_widget.setLayout(right)

        body = QHBoxLayout()
        body.addWidget(self._list, 1)
        body.addWidget(right_widget, 1)

        self._close_button = QPushButton()
        self._close_button.clicked.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.addLayout(body, 1)
        layout.addWidget(self._close_button, alignment=Qt.AlignmentFlag.AlignRight)

        self._retranslate()
        self._render_list()
        self._on_new()

    def _retranslate(self) -> None:
        self.setWindowTitle(self.tr("Manage sellers"))
        self._form.labelForField(self._name).setText(self.tr("Name *"))
        self._form.labelForField(self._url).setText(self.tr("URL"))
        self._form.labelForField(self._city).setText(self.tr("City"))
        self._form.labelForField(self._notes).setText(self.tr("Notes"))
        self._new_button.setText(self.tr("New"))
        self._save_button.setText(self.tr("Save"))
        self._delete_button.setText(self.tr("Delete"))
        self._close_button.setText(self.tr("Close"))

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)

    def sellers(self) -> list[Seller]:
        return list(self._sellers)

    def _render_list(self) -> None:
        self._list.blockSignals(True)
        self._list.clear()
        for seller in self._sellers:
            self._list.addItem(QListWidgetItem(seller.name))
        self._list.blockSignals(False)

    def _on_selection_changed(self, row: int) -> None:
        if row < 0 or row >= len(self._sellers):
            return
        self._editing_index = row
        seller = self._sellers[row]
        self._name.setText(seller.name)
        self._url.setText(seller.url or "")
        self._city.setText(seller.city or "")
        self._notes.setText(seller.notes or "")
        self._delete_button.setEnabled(True)

    def _on_new(self) -> None:
        self._editing_index = None
        self._list.clearSelection()
        self._list.setCurrentRow(-1)
        self._name.clear()
        self._url.clear()
        self._city.clear()
        self._notes.clear()
        self._delete_button.setEnabled(False)
        self._name.setFocus()

    def _on_save(self) -> None:
        name = self._name.text().strip()
        if not name:
            QMessageBox.warning(self, self.tr("Name required"), self.tr("A seller needs a name."))
            return
        seller = Seller(
            name=name,
            url=self._url.text().strip() or None,
            city=self._city.text().strip() or None,
            notes=self._notes.text().strip() or None,
        )
        if self._editing_index is None:
            self._sellers.append(seller)
        else:
            self._sellers[self._editing_index] = seller
        save_sellers(self._backups_dir, self._path, self._sellers)
        self._render_list()
        self._on_new()

    def _on_delete(self) -> None:
        if self._editing_index is None:
            return
        del self._sellers[self._editing_index]
        save_sellers(self._backups_dir, self._path, self._sellers)
        self._render_list()
        self._on_new()
