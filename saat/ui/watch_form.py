from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from saat.models import Acquisition, Case, Dial, Maintenance, Movement, Watch
from saat.sellers import Seller
from saat.storage import WatchRecord
from saat.ui.dialogs import confirm_discard_changes
from saat.ui.form_fields import (
    WaterResistanceField,
    bool_value,
    combo_value,
    date_value,
    double_value,
    existing_values,
    fixed_combo,
    int_value,
    optional_checkbox,
    optional_date_edit,
    optional_double_spin,
    optional_int_spin,
    refresh_combo_options,
    set_bool_value,
    set_combo_value,
    set_date_value,
    set_double_value,
    set_int_value,
    suggested_combo,
)
from saat.ui.images_tab import ImagesTab
from saat.ui.list_editors import LogEditor, StringListEditor, StrapsEditor, TimingEditor

GROUP_SUGGESTIONS = ["Seiko Group", "Casio", "Swatch Group", "Citizen Group", "Micro Brand", "Independent", "Other"]
STYLE_SUGGESTIONS = ["Field", "Pilot", "Diver", "Dress", "Sport", "Chronograph", "GMT", "Racing", "Skeleton", "Digital", "Other"]
STATUS_OPTIONS = ["Owned", "Incoming", "Wishlist", "Sold", "Gifted"]
MOVEMENT_KIND_SUGGESTIONS = ["Automatic", "Manual", "Automatic + Handwinding", "Quartz", "Solar", "Mecha-quartz", "Kinetic"]
QUARTZ_LIKE_KINDS = ("Quartz", "Solar")
ACCURACY_UNIT_OPTIONS = ["sec/day", "sec/month"]
CASE_MATERIAL_SUGGESTIONS = ["Stainless Steel", "Titanium", "Bronze", "Ceramic", "Resin", "Silicone", "Gold-plated"]
CRYSTAL_SUGGESTIONS = ["Sapphire", "Mineral", "Hardlex", "Acrylic", "Sapphire-coated"]
CROWN_SUGGESTIONS = ["Screw-down", "Push-pull", "Screw-down + guards"]
BEZEL_SUGGESTIONS = ["Fixed", "Unidirectional", "Bidirectional", "Tachymeter", "GMT", "None"]
CASEBACK_SUGGESTIONS = ["Solid", "Exhibition", "Engraved"]
INDICES_SUGGESTIONS = ["Applied", "Printed", "Arabic", "Roman", "Mixed", "Inverted", "None"]
COMPLICATIONS_SUGGESTIONS = ["Date", "Day-Date", "GMT", "Chronograph", "Power Reserve", "Moonphase", "Open-Heart", "Small Seconds", "Alarm"]
CONDITION_OPTIONS = ["New", "Pre-owned"]

_TRACKABLE_TYPES = (QComboBox, QDateEdit, QSpinBox, QDoubleSpinBox, QCheckBox, QLineEdit, QPlainTextEdit)


class WatchForm(QDialog):
    """Tabbed add/edit dialog mirroring the data model groups; the same
    dialog serves both operations. See SPEC.md §5.7."""

    def __init__(
        self,
        records: list[WatchRecord],
        record: WatchRecord | None = None,
        parent: QWidget | None = None,
        default_status: str | None = None,
        sellers: list[Seller] | None = None,
        manage_sellers: Callable[[], list[Seller]] | None = None,
    ) -> None:
        super().__init__(parent)
        self._records = records
        self._original_record = record
        self._dirty = False
        self._saved_watch: Watch | None = None
        self._sellers = list(sellers) if sellers is not None else []
        self._manage_sellers = manage_sellers

        # SPEC.md §5.12: adding from Wishlist scope defaults the new watch's
        # status to Wishlist — otherwise it saves as Owned and immediately
        # vanishes from the scope it was just added from.
        watch = record.watch if record is not None else Watch(brand="", model="", status=default_status or "Owned")
        self.setWindowTitle("Edit watch" if record is not None else "Add watch")
        self.resize(820, 680)

        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_identity_tab(watch), "Identity")
        self._tabs.addTab(self._build_images_tab(record), "Images")
        self._tabs.addTab(self._build_movement_tab(watch), "Movement")
        self._tabs.addTab(self._build_case_tab(watch), "Case")
        self._tabs.addTab(self._build_dial_tab(watch), "Dial")
        self._tabs.addTab(self._build_straps_tab(watch), "Straps")
        self._tabs.addTab(self._build_acquisition_tab(watch), "Acquisition")
        self._tabs.addTab(self._build_maintenance_tab(watch), "Maintenance")
        self._tabs.addTab(self._build_log_tab(watch), "Log")
        self._tabs.addTab(self._build_timing_tab(watch), "Timing")
        self._tabs.addTab(self._build_notes_tab(watch), "Notes")

        # Case's lug width seeds a newly-added strap's default width_mm (§4).
        self._straps_editor.set_default_width_mm(int_value(self._lug_width_mm))
        self._lug_width_mm.valueChanged.connect(
            lambda: self._straps_editor.set_default_width_mm(int_value(self._lug_width_mm))
        )

        # A strap's image is picked from whatever's currently staged in the
        # Images tab; removing an image there must null out any strap
        # referencing it, never leave a dangling filename.
        self._straps_editor.set_available_images(self._images_tab.filenames())
        self._images_tab.changed.connect(
            lambda: self._straps_editor.set_available_images(self._images_tab.filenames())
        )

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self._tabs)
        layout.addWidget(buttons)

        self._dirty = False  # building the form above marks fields "changed"; not a real edit yet

    def saved_watch(self) -> Watch | None:
        return self._saved_watch

    def images_tab(self) -> ImagesTab:
        return self._images_tab

    # --- dirty tracking -----------------------------------------------------

    def _track(self, widget: QWidget) -> None:
        changed_signal = getattr(widget, "changed", None)
        if changed_signal is not None:
            changed_signal.connect(self._mark_dirty)
            return
        if isinstance(widget, QComboBox):
            widget.currentTextChanged.connect(self._mark_dirty)
        elif isinstance(widget, QDateEdit):
            widget.dateChanged.connect(self._mark_dirty)
        elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
            widget.valueChanged.connect(self._mark_dirty)
        elif isinstance(widget, QCheckBox):
            widget.toggled.connect(self._mark_dirty)
        elif isinstance(widget, (QLineEdit, QPlainTextEdit)):
            widget.textChanged.connect(self._mark_dirty)
        else:
            for cls in _TRACKABLE_TYPES:
                for child in widget.findChildren(cls):
                    self._track(child)

    def _mark_dirty(self, *_args: object) -> None:
        self._dirty = True

    # --- tab scaffolding -----------------------------------------------------

    def _form_tab(self, rows: list[tuple[str, QWidget]]) -> QWidget:
        content = QWidget()
        form = QFormLayout(content)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setContentsMargins(16, 16, 16, 16)
        form.setSpacing(10)
        for label, widget in rows:
            form.addRow(label, widget)
            self._track(widget)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(content)
        return scroll

    def _existing(self, getter) -> list[str]:
        return existing_values(self._records, getter)

    # --- Identity -----------------------------------------------------------

    def _build_identity_tab(self, watch: Watch) -> QWidget:
        self._brand = QLineEdit(watch.brand)
        self._model = QLineEdit(watch.model)
        self._reference = QLineEdit(watch.reference or "")
        self._nickname = QLineEdit(watch.nickname or "")
        self._serial = QLineEdit(watch.serial or "")

        self._group = suggested_combo(GROUP_SUGGESTIONS, self._existing(lambda w: w.group))
        set_combo_value(self._group, watch.group)
        self._style = suggested_combo(STYLE_SUGGESTIONS, self._existing(lambda w: w.style))
        set_combo_value(self._style, watch.style)
        self._status = fixed_combo(STATUS_OPTIONS, allow_blank=False)
        self._status.setCurrentText(watch.status)
        self._storage = QLineEdit(watch.storage or "")
        self._rating = optional_int_spin(0, 5)
        set_int_value(self._rating, watch.rating)
        self._tags = StringListEditor()
        self._tags.set_values(watch.tags)

        return self._form_tab([
            ("Brand *", self._brand),
            ("Model *", self._model),
            ("Reference", self._reference),
            ("Nickname", self._nickname),
            ("Serial", self._serial),
            ("Group", self._group),
            ("Style", self._style),
            ("Status", self._status),
            ("Storage", self._storage),
            ("Rating", self._rating),
            ("Tags", self._tags),
        ])

    # --- Images -----------------------------------------------------------

    def _build_images_tab(self, record: WatchRecord | None) -> QWidget:
        self._images_tab = ImagesTab(record)
        self._track(self._images_tab)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(self._images_tab)
        return scroll

    # --- Movement -----------------------------------------------------------

    def _build_movement_tab(self, watch: Watch) -> QWidget:
        m = watch.movement
        self._caliber = QLineEdit(m.caliber or "")
        self._kind = suggested_combo(MOVEMENT_KIND_SUGGESTIONS, self._existing(lambda w: w.movement.kind))
        set_combo_value(self._kind, m.kind)

        # SPEC.md §4: show one or the other, driven by kind.
        self._power_reserve_hours = optional_double_spin(0, 300, decimals=0, suffix=" h")
        set_double_value(self._power_reserve_hours, m.power_reserve_hours)
        self._battery_life_years = optional_double_spin(0, 20, decimals=1, suffix=" y")
        set_double_value(self._battery_life_years, m.battery_life_years)
        reserve_row = QWidget()
        reserve_layout = QHBoxLayout(reserve_row)
        reserve_layout.setContentsMargins(0, 0, 0, 0)
        reserve_layout.addWidget(self._power_reserve_hours)
        reserve_layout.addWidget(self._battery_life_years)
        self._kind.currentTextChanged.connect(self._update_reserve_visibility)

        self._accuracy_min = optional_double_spin(-9999, 9999, decimals=0, suffix=" sec")
        set_double_value(self._accuracy_min, m.accuracy_min)
        self._accuracy_max = optional_double_spin(-9999, 9999, decimals=0, suffix=" sec")
        set_double_value(self._accuracy_max, m.accuracy_max)
        self._accuracy_unit = fixed_combo(ACCURACY_UNIT_OPTIONS)
        set_combo_value(self._accuracy_unit, m.accuracy_unit)
        accuracy_row = QWidget()
        accuracy_layout = QHBoxLayout(accuracy_row)
        accuracy_layout.setContentsMargins(0, 0, 0, 0)
        accuracy_layout.addWidget(QLabel("min"))
        accuracy_layout.addWidget(self._accuracy_min)
        accuracy_layout.addWidget(QLabel("max"))
        accuracy_layout.addWidget(self._accuracy_max)
        accuracy_layout.addWidget(self._accuracy_unit)

        self._jewels = optional_int_spin(0, 50)
        set_int_value(self._jewels, m.jewels)
        self._bph = optional_int_spin(0, 60000)
        set_int_value(self._bph, m.bph)
        self._hacking = optional_checkbox()
        set_bool_value(self._hacking, m.hacking)
        self._handwinding = optional_checkbox()
        set_bool_value(self._handwinding, m.handwinding)
        self._origin = QLineEdit(m.origin or "")

        self._update_reserve_visibility(self._kind.currentText())

        return self._form_tab([
            ("Caliber", self._caliber),
            ("Kind", self._kind),
            ("Power Reserve / Battery Life", reserve_row),
            ("Accuracy", accuracy_row),
            ("Jewels", self._jewels),
            ("Frequency", self._bph),
            ("Hacking", self._hacking),
            ("Handwinding", self._handwinding),
            ("Origin", self._origin),
        ])

    def _update_reserve_visibility(self, kind: str) -> None:
        quartz_like = kind in QUARTZ_LIKE_KINDS
        self._power_reserve_hours.setVisible(not quartz_like)
        self._battery_life_years.setVisible(quartz_like)

    # --- Case -----------------------------------------------------------

    def _build_case_tab(self, watch: Watch) -> QWidget:
        c = watch.case
        self._diameter_mm = optional_double_spin(0, 100, decimals=1, suffix=" mm")
        set_double_value(self._diameter_mm, c.diameter_mm)
        self._lug_to_lug_mm = optional_double_spin(0, 100, decimals=1, suffix=" mm")
        set_double_value(self._lug_to_lug_mm, c.lug_to_lug_mm)
        self._thickness_mm = optional_double_spin(0, 50, decimals=1, suffix=" mm")
        set_double_value(self._thickness_mm, c.thickness_mm)
        self._lug_width_mm = optional_int_spin(0, 40, suffix=" mm")
        set_int_value(self._lug_width_mm, c.lug_width_mm)
        self._case_material = suggested_combo(CASE_MATERIAL_SUGGESTIONS, self._existing(lambda w: w.case.material))
        set_combo_value(self._case_material, c.material)
        self._crystal = suggested_combo(CRYSTAL_SUGGESTIONS, self._existing(lambda w: w.case.crystal))
        set_combo_value(self._crystal, c.crystal)
        self._crown = suggested_combo(CROWN_SUGGESTIONS, self._existing(lambda w: w.case.crown))
        set_combo_value(self._crown, c.crown)
        self._bezel = suggested_combo(BEZEL_SUGGESTIONS, self._existing(lambda w: w.case.bezel))
        set_combo_value(self._bezel, c.bezel)
        self._caseback = suggested_combo(CASEBACK_SUGGESTIONS, self._existing(lambda w: w.case.caseback))
        set_combo_value(self._caseback, c.caseback)
        self._water_resistance = WaterResistanceField()
        self._water_resistance.set_value_m(c.water_resistance_m)
        self._weight_g = optional_double_spin(0, 500, decimals=1, suffix=" g")
        set_double_value(self._weight_g, c.weight_g)

        return self._form_tab([
            ("Diameter", self._diameter_mm),
            ("Lug-to-Lug", self._lug_to_lug_mm),
            ("Thickness", self._thickness_mm),
            ("Lug Width", self._lug_width_mm),
            ("Material", self._case_material),
            ("Crystal", self._crystal),
            ("Crown", self._crown),
            ("Bezel", self._bezel),
            ("Caseback", self._caseback),
            ("Water Resistance", self._water_resistance),
            ("Weight", self._weight_g),
        ])

    # --- Dial -----------------------------------------------------------

    def _build_dial_tab(self, watch: Watch) -> QWidget:
        d = watch.dial
        self._dial_colour = QLineEdit(d.colour or "")
        self._dial_material = QLineEdit(d.material or "")
        self._indices = suggested_combo(INDICES_SUGGESTIONS, self._existing(lambda w: w.dial.indices))
        set_combo_value(self._indices, d.indices)
        self._lume = QLineEdit(d.lume or "")
        self._complications = StringListEditor(COMPLICATIONS_SUGGESTIONS)
        self._complications.set_values(d.complications)

        return self._form_tab([
            ("Colour", self._dial_colour),
            ("Material", self._dial_material),
            ("Indices", self._indices),
            ("Lume", self._lume),
            ("Complications", self._complications),
        ])

    # --- Straps -----------------------------------------------------------

    def _build_straps_tab(self, watch: Watch) -> QWidget:
        self._straps_editor = StrapsEditor(self._existing(lambda w: [s.material for s in w.straps if s.material]))
        self._straps_editor.set_values(watch.straps)
        return self._form_tab([("Straps", self._straps_editor)])

    # --- Acquisition -----------------------------------------------------------

    def _build_acquisition_tab(self, watch: Watch) -> QWidget:
        a = watch.acquisition
        self._acquired_date = optional_date_edit()
        set_date_value(self._acquired_date, a.date)
        self._price = optional_double_spin(0, 1_000_000, decimals=2)
        set_double_value(self._price, a.price)
        # SPEC.md §4: what it costs (target_price) vs. what was paid (price)
        # — kept adjacent to Price for direct comparison, never overloading
        # one field for both meanings.
        self._target_price = optional_double_spin(0, 1_000_000, decimals=2)
        set_double_value(self._target_price, a.target_price)
        self._target_date = optional_date_edit()
        set_date_value(self._target_date, a.target_date)
        self._currency = QLineEdit(a.currency or "TRY")  # SPEC.md §4: default TRY

        # SPEC.md §3/§4: an enum*-style combo — sellers.toml entries plus
        # every seller value already used in the collection, plus free
        # text — same pattern as group/style/case material etc.
        self._seller = suggested_combo([s.name for s in self._sellers], self._existing(lambda w: w.acquisition.seller))
        set_combo_value(self._seller, a.seller)
        manage_sellers_button = QPushButton("Manage sellers…")
        manage_sellers_button.setProperty("variant", "link")
        manage_sellers_button.setCursor(Qt.CursorShape.PointingHandCursor)
        manage_sellers_button.clicked.connect(self._on_manage_sellers)
        seller_row = QWidget()
        seller_layout = QHBoxLayout(seller_row)
        seller_layout.setContentsMargins(0, 0, 0, 0)
        seller_layout.addWidget(self._seller, 1)
        seller_layout.addWidget(manage_sellers_button)

        self._url = QLineEdit(a.url or "")
        self._condition = fixed_combo(CONDITION_OPTIONS)
        set_combo_value(self._condition, a.condition)
        self._box_and_papers = optional_checkbox()
        set_bool_value(self._box_and_papers, a.box_and_papers)
        self._warranty_until = optional_date_edit()
        set_date_value(self._warranty_until, a.warranty_until)

        return self._form_tab([
            ("Acquired", self._acquired_date),
            ("Price", self._price),
            ("Target Price", self._target_price),
            ("Target Date", self._target_date),
            ("Currency", self._currency),
            ("Seller", seller_row),
            ("URL", self._url),
            ("Condition", self._condition),
            ("Box & Papers", self._box_and_papers),
            ("Warranty Until", self._warranty_until),
        ])

    def _on_manage_sellers(self) -> None:
        """Delegates the actual dialog to the caller (MainWindow owns
        backups_dir/sellers_path, WatchForm doesn't) — refreshes the combo
        in place afterward so a newly added seller is selectable without
        closing and reopening this form."""
        if self._manage_sellers is None:
            return
        self._sellers = self._manage_sellers()
        refresh_combo_options(
            self._seller, [s.name for s in self._sellers], self._existing(lambda w: w.acquisition.seller)
        )

    # --- Maintenance -----------------------------------------------------------

    def _build_maintenance_tab(self, watch: Watch) -> QWidget:
        m = watch.maintenance
        self._service_interval_years = optional_double_spin(0, 20, decimals=1, suffix=" y")
        set_double_value(self._service_interval_years, m.service_interval_years)
        self._battery_due = optional_date_edit()
        set_date_value(self._battery_due, m.battery_due)

        return self._form_tab([
            ("Service Interval", self._service_interval_years),
            ("Battery Due", self._battery_due),
        ])

    # --- Log / Timing / Notes -----------------------------------------------------------

    def _build_log_tab(self, watch: Watch) -> QWidget:
        self._log_editor = LogEditor()
        self._log_editor.set_values(watch.log)
        return self._form_tab([("Log", self._log_editor)])

    def _build_timing_tab(self, watch: Watch) -> QWidget:
        self._timing_editor = TimingEditor()
        self._timing_editor.set_values(watch.timing)
        return self._form_tab([("Timing", self._timing_editor)])

    def _build_notes_tab(self, watch: Watch) -> QWidget:
        self._notes = QPlainTextEdit(watch.notes or "")
        self._notes.setPlaceholderText("Notes")
        return self._form_tab([("Notes", self._notes)])

    # --- save / cancel -----------------------------------------------------------

    def _build_watch(self) -> Watch:
        preserved_worn = list(self._original_record.watch.worn) if self._original_record and self._original_record.watch else []
        return Watch(
            brand=self._brand.text().strip(),
            model=self._model.text().strip(),
            reference=self._reference.text().strip() or None,
            nickname=self._nickname.text().strip() or None,
            serial=self._serial.text().strip() or None,
            group=combo_value(self._group),
            style=combo_value(self._style),
            status=self._status.currentText(),
            storage=self._storage.text().strip() or None,
            rating=int_value(self._rating),
            tags=self._tags.values(),
            movement=Movement(
                caliber=self._caliber.text().strip() or None,
                kind=combo_value(self._kind),
                power_reserve_hours=double_value(self._power_reserve_hours),
                battery_life_years=double_value(self._battery_life_years),
                accuracy_min=double_value(self._accuracy_min),
                accuracy_max=double_value(self._accuracy_max),
                accuracy_unit=combo_value(self._accuracy_unit),
                jewels=int_value(self._jewels),
                bph=int_value(self._bph),
                hacking=bool_value(self._hacking),
                handwinding=bool_value(self._handwinding),
                origin=self._origin.text().strip() or None,
            ),
            case=Case(
                diameter_mm=double_value(self._diameter_mm),
                lug_to_lug_mm=double_value(self._lug_to_lug_mm),
                thickness_mm=double_value(self._thickness_mm),
                lug_width_mm=int_value(self._lug_width_mm),
                material=combo_value(self._case_material),
                crystal=combo_value(self._crystal),
                crown=combo_value(self._crown),
                bezel=combo_value(self._bezel),
                caseback=combo_value(self._caseback),
                water_resistance_m=self._water_resistance.value_m(),
                weight_g=double_value(self._weight_g),
            ),
            dial=Dial(
                colour=self._dial_colour.text().strip() or None,
                material=self._dial_material.text().strip() or None,
                indices=combo_value(self._indices),
                lume=self._lume.text().strip() or None,
                complications=self._complications.values(),
            ),
            straps=self._straps_editor.values(),
            acquisition=Acquisition(
                date=date_value(self._acquired_date),
                price=double_value(self._price),
                currency=self._currency.text().strip() or None,
                seller=combo_value(self._seller),
                url=self._url.text().strip() or None,
                condition=combo_value(self._condition),
                box_and_papers=bool_value(self._box_and_papers),
                warranty_until=date_value(self._warranty_until),
                target_price=double_value(self._target_price),
                target_date=date_value(self._target_date),
            ),
            maintenance=Maintenance(
                service_interval_years=double_value(self._service_interval_years),
                battery_due=date_value(self._battery_due),
            ),
            log=self._log_editor.values(),
            worn=preserved_worn,  # calendar-driven (milestone 7); this form never touches it
            timing=self._timing_editor.values(),
            notes=self._notes.toPlainText().strip() or None,
            images=self._images_tab.filenames(),
        )

    def _on_save(self) -> None:
        # SPEC.md §5.7: saving with only brand and model filled must succeed;
        # validation blocks nothing else.
        if not self._brand.text().strip() or not self._model.text().strip():
            QMessageBox.warning(self, "Missing required fields", "Brand and model are required.")
            return
        self._saved_watch = self._build_watch()
        self.accept()

    def reject(self) -> None:
        if self._dirty and not confirm_discard_changes(self):
            return
        super().reject()
