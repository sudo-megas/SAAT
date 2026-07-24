from collections.abc import Callable

from PySide6.QtCore import QParallelAnimationGroup, QPropertyAnimation
from PySide6.QtWidgets import QGraphicsOpacityEffect, QLabel, QWidget

from saat.ui import theme


def fade_transition(container: QWidget, apply_change: Callable[[], None]) -> None:
    """Snapshot container's current appearance, apply the real change
    underneath it, then fade the snapshot away to reveal what apply_change
    left in its place. One mechanism for both a QStackedWidget page switch
    and an in-place re-render (e.g. calendar month navigation) — works
    whether the outgoing widget is kept alive or destroyed by apply_change,
    since nothing here depends on it still existing once the snapshot is
    taken. SPEC.md §6: nothing animates on first paint, only state changes —
    callers only reach this from a click/navigation handler, never from
    initial construction."""
    snapshot = container.grab()
    overlay = QLabel(container)
    overlay.setPixmap(snapshot)
    overlay.setGeometry(container.rect())
    overlay.show()
    overlay.raise_()

    apply_change()

    effect = QGraphicsOpacityEffect(overlay)
    overlay.setGraphicsEffect(effect)
    animation = QPropertyAnimation(effect, b"opacity", overlay)
    animation.setDuration(theme.ANIM_DURATION_MS)
    animation.setEasingCurve(theme.ANIM_EASING)
    animation.setStartValue(1.0)
    animation.setEndValue(0.0)
    animation.finished.connect(overlay.deleteLater)
    # Qt's C++ parent-child ownership (overlay) keeps the animation alive
    # too, but a live Python reference avoids relying on that alone.
    overlay._fade_animation = animation
    animation.start()


def animate_width(widget: QWidget, target_width: int) -> None:
    """Sidebar collapse/expand: setFixedWidth's instant jump, eased instead
    by animating the same minimumWidth/maximumWidth pair setFixedWidth
    itself sets under the hood, then pinning both exactly with a real
    setFixedWidth once the animation lands — belt and suspenders against
    any float/rounding drift leaving the widget not-quite-fixed."""
    start_width = widget.width()
    group = QParallelAnimationGroup(widget)
    for prop in (b"minimumWidth", b"maximumWidth"):
        animation = QPropertyAnimation(widget, prop, widget)
        animation.setDuration(theme.ANIM_DURATION_MS)
        animation.setEasingCurve(theme.ANIM_EASING)
        animation.setStartValue(start_width)
        animation.setEndValue(target_width)
        group.addAnimation(animation)
    group.finished.connect(lambda: widget.setFixedWidth(target_width))
    widget._width_animation = group
    group.start()
