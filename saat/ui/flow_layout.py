"""Adapted from Qt's "Flow Layout" example (Widgets/Layouts/FlowLayout).
Qt's own QBoxLayout/QGridLayout have no notion of "wrap to a new row once
out of horizontal space" -- this is Qt's own answer to that, not something
invented for this app. Used by saat/ui/grid_view.py for the watch-card
grid (SPEC.md §5.2, milestone 21b): real QWidget children in a real
QLayout, so Qt's own focus/size/show-hide machinery keeps working on them
unmodified, instead of a hand-rolled absolute-positioning scheme.

_do_layout() below applies contentsMargins to get its layout rect, which
upstream's own example does not do (it force-zeroes contentsMargins
whenever a parent widget is given, since its demo has no use for margins
at all) -- this app's grid needs a real page margin around the whole
card area, so that one behaviour was changed. Everything else -- the
item list, the row-wrap algorithm, spacing composition -- matches
upstream.

Copyright (C) 2013 Riverbank Computing Limited.
Copyright (C) 2022 The Qt Company Ltd.
SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are
met:
 * Redistributions of source code must retain the above copyright
   notice, this list of conditions and the following disclaimer.
 * Redistributions in binary form must reproduce the above copyright
   notice, this list of conditions and the following disclaimer in
   the documentation and/or other materials provided with the
   distribution.
 * Neither the name of The Qt Company Ltd nor the names of its
   contributors may be used to endorse or promote products derived
   from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
"AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import QLayout, QSizePolicy


class FlowLayout(QLayout):
    def __init__(self, parent=None, margin: int = 0, spacing: int = -1) -> None:
        super().__init__(parent)
        self.setContentsMargins(margin, margin, margin, margin)
        if spacing >= 0:
            self.setSpacing(spacing)
        self._item_list = []

    def __del__(self) -> None:
        while self.count():
            self.takeAt(0)

    def addItem(self, item) -> None:
        self._item_list.append(item)

    def count(self) -> int:
        return len(self._item_list)

    def itemAt(self, index: int):
        if 0 <= index < len(self._item_list):
            return self._item_list[index]
        return None

    def takeAt(self, index: int):
        if 0 <= index < len(self._item_list):
            return self._item_list.pop(index)
        return None

    def expandingDirections(self) -> Qt.Orientation:
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._do_layout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect: QRect) -> None:
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self._item_list:
            size = size.expandedTo(item.minimumSize())
        left, top, right, bottom = self.getContentsMargins()
        size += QSize(left + right, top + bottom)
        return size

    def _do_layout(self, rect: QRect, test_only: bool) -> int:
        left, top, right, bottom = self.getContentsMargins()
        effective_rect = rect.adjusted(left, top, -right, -bottom)
        x = effective_rect.x()
        y = effective_rect.y()
        line_height = 0
        spacing = self.spacing()

        for item in self._item_list:
            style = item.widget().style()
            # QStyle.layoutSpacing() returns -1 for "this style doesn't
            # specify a recommendation" (QCommonStyle's own default, never
            # overridden by Fusion -- confirmed directly, and it's Fusion
            # SAAT actually runs under, since nothing here ever calls
            # QApplication.setStyle()). Upstream's own example sums it in
            # unguarded, which would silently shave a real pixel off the
            # spacing set below; clamped to 0 so an unsupported style
            # never changes the requested gap instead of only ever adding
            # to it.
            layout_spacing_x = max(
                style.layoutSpacing(
                    QSizePolicy.ControlType.PushButton, QSizePolicy.ControlType.PushButton, Qt.Orientation.Horizontal
                ),
                0,
            )
            layout_spacing_y = max(
                style.layoutSpacing(
                    QSizePolicy.ControlType.PushButton, QSizePolicy.ControlType.PushButton, Qt.Orientation.Vertical
                ),
                0,
            )
            space_x = spacing + layout_spacing_x
            space_y = spacing + layout_spacing_y
            next_x = x + item.sizeHint().width() + space_x
            if next_x - space_x > effective_rect.right() and line_height > 0:
                x = effective_rect.x()
                y = y + line_height + space_y
                next_x = x + item.sizeHint().width() + space_x
                line_height = 0

            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))

            x = next_x
            line_height = max(line_height, item.sizeHint().height())

        return y + line_height - rect.y() + bottom
