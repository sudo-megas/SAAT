import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QMessageBox

from saat.models import Case, Movement, Strap, Watch
from saat.storage import create_watch, load_collection
from saat.ui.form_fields import (
    WaterResistanceField,
    bool_value,
    double_value,
    int_value,
    optional_checkbox,
    optional_double_spin,
    optional_int_spin,
    set_bool_value,
    set_double_value,
    set_int_value,
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
