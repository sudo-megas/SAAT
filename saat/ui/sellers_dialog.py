from pathlib import Path

from PySide6.QtCore import Qt
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
        self.setWindowTitle("Manage sellers")
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

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.addRow("Name *", self._name)
        form.addRow("URL", self._url)
        form.addRow("City", self._city)
        form.addRow("Notes", self._notes)

        new_button = QPushButton("New")
        new_button.clicked.connect(self._on_new)
        save_button = QPushButton("Save")
        save_button.clicked.connect(self._on_save)
        self._delete_button = QPushButton("Delete")
        self._delete_button.setProperty("variant", "destructive")
        self._delete_button.clicked.connect(self._on_delete)

        buttons_row = QHBoxLayout()
        buttons_row.addWidget(new_button)
        buttons_row.addWidget(save_button)
        buttons_row.addWidget(self._delete_button)

        right = QVBoxLayout()
        right.addLayout(form)
        right.addLayout(buttons_row)
        right.addStretch()
        right_widget = QWidget()
        right_widget.setLayout(right)

        body = QHBoxLayout()
        body.addWidget(self._list, 1)
        body.addWidget(right_widget, 1)

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.addLayout(body, 1)
        layout.addWidget(close_button, alignment=Qt.AlignmentFlag.AlignRight)

        self._render_list()
        self._on_new()

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
            QMessageBox.warning(self, "Name required", "A seller needs a name.")
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
