import random
from collections.abc import Callable

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import (
    QDialog,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from saat.selection import MODE_RANDOM, MODE_WEIGHTED, pick_one
from saat.storage import WatchRecord
from saat.ui import motion, theme
from saat.ui.images import cropped_pixmap, first_image
from saat.wear import owned_watches

DIE_SIZE = 96
RESULT_IMAGE_SIZE = 120
_TUMBLE_TICKS = 14
_TUMBLE_FIRST_DELAY_MS = 40
_TUMBLE_LAST_DELAY_MS = 220


class HairlineDie(QWidget):
    """Milestone 20's settle animation, drawn flat in the app's hairline
    vocabulary — deliberately NOT a 3D bouncing object (SPEC.md §6
    exception). Shows a face count equal to the number of owned watches
    being chosen among, tumbling briefly through faces before settling on
    the caller's already-made pick — this widget never makes the choice
    itself, only dramatises it.

    The tumble is a plain QTimer chain with an increasing delay between
    ticks (fast at first, slowing toward the end, per theme.ANIM_EASING).
    The final settle is one real QPropertyAnimation over the die's own
    opacity, reusing theme.ANIM_DURATION_MS/ANIM_EASING directly, the same
    machinery motion.py already uses elsewhere — kept separate from the
    tick chain because a QPropertyAnimation interpolates smoothly between
    two values and can't itself express "flash through N unrelated random
    faces", which is what the tumble needs."""

    settled = Signal()

    def __init__(self, face_count: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._face_count = max(face_count, 1)
        self._face = 1
        self._final_face = 1
        self._tick_index = 0
        self._tumble_rand = random.Random()  # only flashes faces -- never the real pick
        self.setFixedSize(DIE_SIZE, DIE_SIZE)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._tick)

        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(1.0)
        self.setGraphicsEffect(self._opacity_effect)
        self._settle_animation: QPropertyAnimation | None = None

    def roll_to(self, final_face: int, animate: bool) -> None:
        """Starts the tumble ending on final_face — already the caller's
        real pick. With animate=False (reduced motion, or a test), settles
        immediately and still emits `settled` so callers don't need two
        code paths."""
        self._timer.stop()
        self._final_face = final_face
        if not animate:
            self._face = final_face
            self._opacity_effect.setOpacity(1.0)
            self.update()
            self.settled.emit()
            return
        self._tick_index = 0
        self._tick()

    def _tick(self) -> None:
        self._tick_index += 1
        if self._tick_index >= _TUMBLE_TICKS:
            self._face = self._final_face
            self.update()
            self._play_settle_flourish()
            return
        self._face = self._tumble_rand.randint(1, self._face_count) if self._face_count > 1 else 1
        self.update()
        progress = self._tick_index / _TUMBLE_TICKS
        eased = QEasingCurve(theme.ANIM_EASING).valueForProgress(progress)
        delay = round(_TUMBLE_FIRST_DELAY_MS + (_TUMBLE_LAST_DELAY_MS - _TUMBLE_FIRST_DELAY_MS) * eased)
        self._timer.start(delay)

    def _play_settle_flourish(self) -> None:
        animation = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        animation.setDuration(theme.ANIM_DURATION_MS)
        animation.setEasingCurve(theme.ANIM_EASING)
        animation.setStartValue(0.5)
        animation.setEndValue(1.0)
        animation.finished.connect(self.settled.emit)
        self._settle_animation = animation
        animation.start()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        colors = theme.colors()
        rect = self.rect().adjusted(1, 1, -1, -1)

        painter.setPen(QPen(QColor(colors.rule), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect, 8, 8)

        font = QFont(theme.resolve_fonts()["mono"])
        font.setPixelSize(theme.SIZE_XL)
        painter.setFont(font)
        painter.setPen(QColor(colors.text))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(self._face))
        painter.end()


class TodayPickerDialog(QDialog):
    """SPEC.md milestone 20: "a picker surface reachable from the top bar."
    Picks one owned watch (saat.selection), settles the die on it, then
    offers a single "Wore this today" action. That action reuses the
    existing wore-today path — this dialog only emits a request; the caller
    is the one that calls wear.mark_worn_today, exactly as every other
    "Wore this today" button in the app already does. Re-rolling before
    that action is pressed writes nothing."""

    wore_today_requested = Signal(object)  # WatchRecord

    def __init__(
        self,
        records: list[WatchRecord],
        mode: str,
        on_mode_changed: Callable[[str], None] | None = None,
        reduced_motion: bool | None = None,
        rand: random.Random | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("Pick for me"))
        self._records = records
        self._mode = mode
        self._on_mode_changed = on_mode_changed
        self._reduced_motion = reduced_motion if reduced_motion is not None else motion.reduced_motion_preferred()
        self._rand = rand if rand is not None else random.Random()
        self._chosen: WatchRecord | None = None
        self._owned = owned_watches(records)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        if not self._owned:
            message = QLabel(self.tr("No owned watches to pick from yet."))
            message.setProperty("muted", True)
            message.setAlignment(Qt.AlignmentFlag.AlignCenter)
            message.setWordWrap(True)
            layout.addWidget(message)
            self.resize(360, 140)
            return

        if len(self._owned) == 1:
            only = self._owned[0]
            label = QLabel(
                self.tr("Only one watch to wear: {brand} {model}.").format(
                    brand=only.watch.brand, model=only.watch.model
                )
            )
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setWordWrap(True)
            button = QPushButton(self.tr("Wore this today"))
            button.setProperty("variant", "primary")
            button.clicked.connect(lambda: self._confirm(only))
            layout.addWidget(label)
            layout.addWidget(button)
            self.resize(360, 180)
            return

        toggle_row = QHBoxLayout()
        self._random_button = QPushButton(self.tr("Random"))
        self._random_button.setCheckable(True)
        self._weighted_button = QPushButton(self.tr("Weighted"))
        self._weighted_button.setCheckable(True)
        for button, target_mode in ((self._random_button, MODE_RANDOM), (self._weighted_button, MODE_WEIGHTED)):
            button.clicked.connect(lambda _checked, m=target_mode: self._set_mode(m))
        toggle_row.addStretch()
        toggle_row.addWidget(self._random_button)
        toggle_row.addWidget(self._weighted_button)
        toggle_row.addStretch()
        layout.addLayout(toggle_row)

        self._die = HairlineDie(len(self._owned))
        self._die.settled.connect(self._on_settled)
        layout.addWidget(self._die, alignment=Qt.AlignmentFlag.AlignHCenter)

        self._result_image = QLabel()
        self._result_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._result_image.setFixedHeight(0)  # reserved only once settling actually has a photo to show (_on_settled)
        self._result_label = QLabel()
        self._result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._result_image)
        layout.addWidget(self._result_label)
        # Absorbs the dialog's fixed height here rather than letting Qt
        # distribute it as implicit slack across the labels above — without
        # this, a photo-less result centers its text partway down an
        # oversized cell instead of sitting directly under the die.
        layout.addStretch(1)

        button_row = QHBoxLayout()
        self._reroll_button = QPushButton(self.tr("Re-roll"))
        self._reroll_button.clicked.connect(self._roll)
        self._wore_today_button = QPushButton(self.tr("Wore this today"))
        self._wore_today_button.setProperty("variant", "primary")
        self._wore_today_button.setEnabled(False)
        self._wore_today_button.clicked.connect(self._on_wore_today_clicked)
        button_row.addWidget(self._reroll_button)
        button_row.addStretch()
        button_row.addWidget(self._wore_today_button)
        layout.addLayout(button_row)

        self._update_mode_buttons()
        self.resize(360, 420)
        self._roll()

    def _roll(self) -> None:
        self._wore_today_button.setEnabled(False)
        self._result_label.setText("")
        self._result_image.clear()
        self._result_image.setFixedHeight(0)
        self._chosen = pick_one(self._records, self._mode, self._rand)
        final_face = self._owned.index(self._chosen) + 1
        self._die.roll_to(final_face, animate=not self._reduced_motion)

    def _on_settled(self) -> None:
        assert self._chosen is not None
        watch = self._chosen.watch
        self._result_label.setText(f"{watch.brand} {watch.model}")
        path = first_image(self._chosen)
        pixmap = cropped_pixmap(path, RESULT_IMAGE_SIZE, RESULT_IMAGE_SIZE) if path else None
        if pixmap is not None:
            self._result_image.setFixedHeight(RESULT_IMAGE_SIZE)
            self._result_image.setPixmap(pixmap)
        self._wore_today_button.setEnabled(True)

    def _on_wore_today_clicked(self) -> None:
        if self._chosen is not None:
            self._confirm(self._chosen)

    def _confirm(self, record: WatchRecord) -> None:
        self.wore_today_requested.emit(record)
        self.accept()

    def _set_mode(self, mode: str) -> None:
        if mode == self._mode:
            return
        self._mode = mode
        self._update_mode_buttons()
        if self._on_mode_changed is not None:
            self._on_mode_changed(mode)
        self._roll()

    def _update_mode_buttons(self) -> None:
        self._random_button.setChecked(self._mode == MODE_RANDOM)
        self._weighted_button.setChecked(self._mode == MODE_WEIGHTED)
