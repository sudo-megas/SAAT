import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QCoreApplication, QEvent, QTranslator
from PySide6.QtWidgets import QApplication, QMessageBox

from saat.models import Acquisition, Case, Movement, Strap, Watch
from saat.sellers import Seller
from saat.storage import create_watch, load_collection
from saat.ui.form_fields import (
    WaterResistanceField,
    bool_value,
    combo_value,
    double_value,
    fixed_combo,
    int_value,
    optional_checkbox,
    optional_double_spin,
    optional_int_spin,
    retranslate_combo,
    set_bool_value,
    set_double_value,
    set_int_value,
    suggested_combo,
)
from saat.ui.list_editors import StrapsEditor
from saat.ui.watch_form import WatchForm

_app = QApplication.instance() or QApplication([])


class UITestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="saat-form-test-"))
        self.watches_dir = self.tmp / "watches"
        self.backups_dir = self.tmp / "backups"
        self.watches_dir.mkdir()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)


class OptionalFieldSentinelTests(unittest.TestCase):
    """The unset-sentinel pattern is the substantive trick in the form layer:
    a real 0 must never read back as None. See SPEC.md §4."""

    def test_int_spin_round_trips_none(self) -> None:
        spin = optional_int_spin(0, 5)
        self.assertIsNone(int_value(spin))
        set_int_value(spin, 3)
        self.assertEqual(int_value(spin), 3)
        set_int_value(spin, None)
        self.assertIsNone(int_value(spin))

    def test_int_spin_zero_is_not_confused_with_unset(self) -> None:
        spin = optional_int_spin(0, 5)
        set_int_value(spin, 0)
        self.assertEqual(int_value(spin), 0)

    def test_double_spin_round_trips_none_and_negative(self) -> None:
        spin = optional_double_spin(-9999, 9999, decimals=0)
        self.assertIsNone(double_value(spin))
        set_double_value(spin, -20)
        self.assertEqual(double_value(spin), -20)

    def test_tristate_checkbox_round_trips_true_false_none(self) -> None:
        box = optional_checkbox()
        self.assertIsNone(bool_value(box))
        set_bool_value(box, True)
        self.assertTrue(bool_value(box))
        set_bool_value(box, False)
        self.assertFalse(bool_value(box))
        set_bool_value(box, None)
        self.assertIsNone(bool_value(box))


class WaterResistanceFieldTests(unittest.TestCase):
    def test_bar_converts_to_metres_on_entry(self) -> None:
        field = WaterResistanceField()
        field._value.setValue(10)
        field._unit.setCurrentText("bar")
        self.assertEqual(field.value_m(), 100)

    def test_atm_converts_to_metres_on_entry(self) -> None:
        field = WaterResistanceField()
        field._value.setValue(5)
        field._unit.setCurrentText("atm")
        self.assertEqual(field.value_m(), 50)

    def test_loading_existing_metres_value_selects_metres_unit(self) -> None:
        field = WaterResistanceField()
        field.set_value_m(200)
        self.assertEqual(field.value_m(), 200)
        self.assertEqual(field._unit.currentText(), "m")


class StrapsEditorFittedExclusivityTests(unittest.TestCase):
    def test_checking_one_fitted_unchecks_others(self) -> None:
        editor = StrapsEditor(existing_materials=[])
        row_a = editor.add_row(Strap(material="Leather", fitted=True))
        row_b = editor.add_row(Strap(material="NATO", fitted=False))

        row_b.fitted.setChecked(True)

        self.assertFalse(row_a.fitted.isChecked())
        self.assertTrue(row_b.fitted.isChecked())
        fitted = [s for s in editor.values() if s.fitted]
        self.assertEqual(len(fitted), 1)
        self.assertEqual(fitted[0].material, "NATO")

    def test_new_strap_defaults_width_to_case_lug_width(self) -> None:
        editor = StrapsEditor(existing_materials=[])
        editor.set_default_width_mm(20)
        row = editor.add_row()
        self.assertEqual(row.get_value().width_mm, 20)


class WatchFormBuildTests(UITestCase):
    """Exercise _on_save() directly rather than through the modal exec() loop
    — that loop is standard QDialog machinery, not the logic under test."""

    def test_brand_and_model_only_is_sufficient_to_save(self) -> None:
        form = WatchForm(records=[], record=None)
        form._brand.setText("Seiko")
        form._model.setText("SARB033")
        form._on_save()

        watch = form.saved_watch()
        self.assertIsNotNone(watch)
        self.assertEqual(watch.brand, "Seiko")
        self.assertEqual(watch.model, "SARB033")
        self.assertIsNone(watch.reference)

    def test_missing_brand_blocks_save(self) -> None:
        form = WatchForm(records=[], record=None)
        form._model.setText("SARB033")
        with patch.object(QMessageBox, "warning") as warning:
            form._on_save()
        warning.assert_called_once()
        self.assertIsNone(form.saved_watch())

    def test_movement_kind_switches_reserve_field_visibility(self) -> None:
        # form is never shown, so isVisible() reflects the (unshown) ancestor
        # chain for every descendant regardless of setVisible() calls;
        # isHidden() reflects each widget's own explicit state instead.
        form = WatchForm(records=[], record=None)
        form._kind.setCurrentText("Automatic")
        self.assertFalse(form._power_reserve_hours.isHidden())
        self.assertTrue(form._battery_life_years.isHidden())

        form._kind.setCurrentText("Quartz")
        self.assertTrue(form._power_reserve_hours.isHidden())
        self.assertFalse(form._battery_life_years.isHidden())

    def test_full_round_trip_across_tabs(self) -> None:
        form = WatchForm(records=[], record=None)
        form._brand.setText("Seiko")
        form._model.setText("SARB033")
        form._kind.setCurrentText("Automatic")
        set_int_value(form._rating, 0)  # zero must survive, not read back as unset
        form._case_material.setCurrentText("Stainless Steel")
        form._water_resistance._value.setValue(10)
        form._water_resistance._unit.setCurrentText("bar")
        form._tags.set_values(["everyday", "vintage"])
        form._notes.setPlainText("A test note.")
        form._on_save()

        watch = form.saved_watch()
        self.assertEqual(watch.rating, 0)
        self.assertEqual(watch.case.material, "Stainless Steel")
        self.assertEqual(watch.case.water_resistance_m, 100)
        self.assertEqual(watch.tags, ["everyday", "vintage"])
        self.assertEqual(watch.notes, "A test note.")

    def test_target_price_and_target_date_are_distinct_from_price_and_date(self) -> None:
        """SPEC.md §4: target_price is what it costs, distinct from price
        (what was paid) — must not overload one field for both."""
        form = WatchForm(records=[], record=None)
        form._brand.setText("Seiko")
        form._model.setText("SARB033")
        form._price.setValue(500)
        form._target_price.setValue(650)
        form._target_date.setDate(form._target_date.minimumDate().addDays(1))
        form._on_save()

        watch = form.saved_watch()
        self.assertEqual(watch.acquisition.price, 500)
        self.assertEqual(watch.acquisition.target_price, 650)
        self.assertIsNotNone(watch.acquisition.target_date)

    def test_target_price_and_target_date_default_to_unset(self) -> None:
        form = WatchForm(records=[], record=None)
        form._brand.setText("Seiko")
        form._model.setText("SARB033")
        form._on_save()

        watch = form.saved_watch()
        self.assertIsNone(watch.acquisition.target_price)
        self.assertIsNone(watch.acquisition.target_date)

    def test_seller_combo_offers_sellers_toml_names_and_existing_collection_values(self) -> None:
        """SPEC.md §3/§4: same enum* pattern as group/style/etc — sellers.toml
        entries plus every seller value already used in the collection."""
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Casio", model="F-91W", acquisition=Acquisition(seller="Collection Seller")))
        records = load_collection(self.watches_dir)
        sellers = [Seller(name="Toml Seller")]

        form = WatchForm(records=records, record=None, sellers=sellers)
        items = [form._seller.itemText(i) for i in range(form._seller.count())]
        self.assertIn("Toml Seller", items)
        self.assertIn("Collection Seller", items)

    def test_seller_combo_still_accepts_free_text(self) -> None:
        """SPEC.md §3: loose coupling — free text never requires a matching
        sellers.toml entry."""
        form = WatchForm(records=[], record=None, sellers=[Seller(name="Toml Seller")])
        form._brand.setText("Seiko")
        form._model.setText("SARB033")
        form._seller.setCurrentText("A Brand New Shop")
        form._on_save()

        watch = form.saved_watch()
        self.assertEqual(watch.acquisition.seller, "A Brand New Shop")

    def test_manage_sellers_button_refreshes_the_combo_without_losing_typed_text(self) -> None:
        form = WatchForm(records=[], record=None, sellers=[], manage_sellers=lambda: [Seller(name="Newly Added")])
        form._seller.setCurrentText("Still Typing")

        form._on_manage_sellers()

        items = [form._seller.itemText(i) for i in range(form._seller.count())]
        self.assertIn("Newly Added", items)
        self.assertEqual(form._seller.currentText(), "Still Typing")

    def test_editing_preserves_worn_list_untouched(self) -> None:
        """The form has no worn-tracking UI (calendar-driven, milestone 7) —
        saving through it must not silently wipe existing wear history."""
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033"))
        [record] = load_collection(self.watches_dir)
        record.document["worn"] = [date(2024, 1, 1), date(2024, 1, 2)]
        import tomlkit
        (record.path / "watch.toml").write_text(tomlkit.dumps(record.document), encoding="utf-8")
        [record] = load_collection(self.watches_dir)
        self.assertEqual(record.watch.worn, [date(2024, 1, 1), date(2024, 1, 2)])

        form = WatchForm(records=[record], record=record)
        form._nickname.setText("Edited")
        form._on_save()

        watch = form.saved_watch()
        self.assertEqual(watch.worn, [date(2024, 1, 1), date(2024, 1, 2)])
        self.assertEqual(watch.nickname, "Edited")


class _FakeEnumTranslator(QTranslator):
    """Stands in for a real saat_tr.qm/saat_ja.qm (Commit B) -- proves the
    display/storage split (form_fields.py's combo_value()/set_combo_value())
    holds under ANY installed translator, without needing real translations
    to exist yet. Returning None (not "") for an unmapped source text tells
    Qt's translation fallback "not handled here", which correctly resolves
    back to the untranslated source string -- confirmed empirically before
    writing this test."""

    _MAP = {"Diver": "XX_Diver_XX", "Owned": "XX_Owned_XX"}

    def translate(self, context, source_text, disambiguation=None, n=-1):
        if context == "EnumChoices" and source_text in self._MAP:
            return self._MAP[source_text]
        return None


class NonEnglishStorageSafetyTests(UITestCase):
    """Milestone 21, Commit A's whole reason for existing: a watch saved
    while the UI displays translated enum labels must still store the
    canonical English value, byte-for-byte identical to one saved in
    English -- SPEC.md's "a Turkish combo box shows 'Dalgıç' and writes
    'Diver'" rule. This exercises the actual combo → combo_value() → save
    path (test_storage.py's SlugTests have no QApplication and can't see a
    currentText() leak; this must go through the real widget)."""

    def setUp(self) -> None:
        super().setUp()
        self._translator = _FakeEnumTranslator()
        QApplication.instance().installTranslator(self._translator)
        self.addCleanup(QApplication.instance().removeTranslator, self._translator)

    def test_combo_displays_translated_label_but_saves_canonical_value(self) -> None:
        form = WatchForm(records=[], record=None)
        # Prove the label really is translated under this UI language --
        # otherwise the save-side assertion below would pass vacuously.
        style_labels = [form._style.itemText(i) for i in range(form._style.count())]
        self.assertIn("XX_Diver_XX", style_labels)
        self.assertNotIn("Diver", style_labels)

        index = form._style.findText("XX_Diver_XX")
        form._style.setCurrentIndex(index)
        form._status.setCurrentIndex(form._status.findText("XX_Owned_XX"))
        form._brand.setText("Seiko")
        form._model.setText("SARB033")
        form._on_save()

        watch = form.saved_watch()
        self.assertEqual(watch.style, "Diver")
        self.assertEqual(watch.status, "Owned")

    def test_watch_saved_under_translated_ui_reloads_identically_under_english(self) -> None:
        form = WatchForm(records=[], record=None)
        form._brand.setText("Seiko")
        form._model.setText("SARB033")
        form._style.setCurrentIndex(form._style.findText("XX_Diver_XX"))
        form._on_save()
        translated_watch = create_watch(self.watches_dir, self.backups_dir, form.saved_watch())

        QApplication.instance().removeTranslator(self._translator)
        [reloaded] = load_collection(self.watches_dir)
        self.assertEqual(reloaded.watch.style, translated_watch.watch.style)
        self.assertEqual(reloaded.watch.style, "Diver")


class WatchFormLiveRetranslationTests(UITestCase):
    """A language switch delivered while WatchForm is already open (the
    tray submenu, not this dialog's own UI) -- the plan's own "build it
    everywhere" directive for every .exec()-modal dialog. Confirms the
    changeEvent -> _retranslate() wiring actually fires end-to-end: window
    title, a QFormLayout row label (via labelForField()), and a combo's
    items (via retranslate_combo(), which must preserve the selected
    canonical value even though its old display text no longer matches
    any item after relabeling)."""

    def test_switching_language_while_open_retranslates_labels_and_combos(self) -> None:
        form = WatchForm(records=[], record=None)
        brand_label = form._form_rows[0][0].labelForField(form._brand)
        self.assertEqual(brand_label.text(), "Brand *")
        form._style.setCurrentIndex(form._style.findText("Diver"))

        translator = _FakeEnumTranslator()
        QApplication.instance().installTranslator(translator)
        self.addCleanup(QApplication.instance().removeTranslator, translator)
        form.changeEvent(QEvent(QEvent.Type.LanguageChange))

        # Same QLabel/QComboBox instances, relabeled in place -- not
        # rebuilt (labelForField() would return something new otherwise).
        self.assertIs(form._form_rows[0][0].labelForField(form._brand), brand_label)
        self.assertEqual(combo_value(form._style), "Diver")
        self.assertEqual(form._style.currentText(), "XX_Diver_XX")


class RetranslateComboTests(unittest.TestCase):
    """retranslate_combo() is what every modal form's changeEvent calls to
    relabel its enum* combos on a language switch delivered while the
    modal is still open (rare -- see the plan's note on tray delivery
    into a nested exec() loop -- but cheap to get right). Must preserve
    the selected canonical value even though the display text it was
    selected under no longer exists after relabeling."""

    def setUp(self) -> None:
        self.translator = _FakeEnumTranslator()

    def test_relabels_items_and_preserves_the_selected_value(self) -> None:
        combo = suggested_combo(["Diver", "Dress"], [])
        combo.setCurrentIndex(combo.findText("Diver"))

        QApplication.instance().installTranslator(self.translator)
        self.addCleanup(QApplication.instance().removeTranslator, self.translator)
        retranslate_combo(combo)

        self.assertEqual(combo_value(combo), "Diver")
        self.assertEqual(combo.currentText(), "XX_Diver_XX")
        labels = [combo.itemText(i) for i in range(combo.count())]
        self.assertIn("XX_Diver_XX", labels)
        self.assertNotIn("Diver", labels)

    def test_free_typed_text_is_left_untouched(self) -> None:
        combo = suggested_combo(["Diver", "Dress"], [])
        combo.setCurrentText("Something I typed")

        QApplication.instance().installTranslator(self.translator)
        self.addCleanup(QApplication.instance().removeTranslator, self.translator)
        retranslate_combo(combo)

        self.assertEqual(combo.currentText(), "Something I typed")
        self.assertEqual(combo_value(combo), "Something I typed")

    def test_works_on_a_fixed_combo_too(self) -> None:
        combo = fixed_combo(["Owned", "Wishlist"])
        combo.setCurrentIndex(combo.findText("Owned"))

        QApplication.instance().installTranslator(self.translator)
        self.addCleanup(QApplication.instance().removeTranslator, self.translator)
        retranslate_combo(combo)

        self.assertEqual(combo_value(combo), "Owned")
        self.assertEqual(combo.currentText(), "XX_Owned_XX")


class EditSavePreservesCommentsTests(UITestCase):
    """The real risk this milestone introduces: an edit save must go through
    the loaded record's tomlkit document, not a freshly created one, or
    hand-written comments in watch.toml silently vanish. See SPEC.md §3."""

    def test_edit_via_form_and_save_watch_preserves_hand_written_comment(self) -> None:
        from saat.storage import save_watch

        record = create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033"))
        toml_path = record.path / "watch.toml"
        text = toml_path.read_text(encoding="utf-8")
        text = text.replace("brand = ", "# accuracy not published by the manufacturer\nbrand = ", 1)
        toml_path.write_text(text, encoding="utf-8")

        [loaded] = load_collection(self.watches_dir)
        form = WatchForm(records=[loaded], record=loaded)
        form._nickname.setText("Cocktail Time")
        form._on_save()

        import dataclasses
        updated_record = dataclasses.replace(loaded, watch=form.saved_watch())
        save_watch(self.backups_dir, updated_record)

        final_text = toml_path.read_text(encoding="utf-8")
        self.assertIn("# accuracy not published by the manufacturer", final_text)
        self.assertIn('nickname = "Cocktail Time"', final_text)


if __name__ == "__main__":
    unittest.main()
