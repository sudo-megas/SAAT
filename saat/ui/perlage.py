import random

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPixmap

TILE_SIZE = 64
CIRCLE_COUNT = 24
MIN_RADIUS = 3.0
MAX_RADIUS = 6.5
# Fewer, larger circles rather than a denser field: less overlap means less
# compounding of the alpha blend at any one pixel, which is what actually
# sets the ceiling -- so this combination clears it with a HIGHER alpha
# (stronger, more perceptible grain) than a denser field could. Tuned
# empirically against every real plate/rule pairing this app uses, not
# estimated from a single-layer blend formula -- overlapping circles
# compound, and integer channel rounding hides very low deltas entirely.
# See tests/test_perlage.py.
GRAIN_ALPHA = 10
SEED = 1337  # fixed: the tile must be reproducible, not a different pattern on every launch

_tile_cache: dict[tuple[str, str, int, int], QPixmap] = {}


def render_perlage_tile(base_hex: str, grain_hex: str, alpha: int = GRAIN_ALPHA, tile_size: int = TILE_SIZE) -> QPixmap:
    """Overlapping circular graining -- the actual decorative finish applied
    to a real movement plate, at a contrast low enough to read as texture,
    never as pattern (SPEC.md §6). Pre-rendered once to a QPixmap; the
    caller tiles it with painter.fillRect(rect, QBrush(tile)) rather than
    redrawing circles on every paint event. Cached by the exact parameters
    that determine the result -- a theme toggle changes the hex strings,
    which changes the key, which regenerates the tile with no manual
    invalidation needed, the same self-invalidating pattern icons.py's own
    pixmap() cache already uses. Circles that overlap a tile edge are
    duplicated, shifted by a full tile_size, so the pattern repeats
    seamlessly with no visible seam."""
    key = (base_hex, grain_hex, alpha, tile_size)
    cached = _tile_cache.get(key)
    if cached is not None:
        return cached

    tile = QPixmap(tile_size, tile_size)
    tile.fill(QColor(base_hex))

    grain = QColor(grain_hex)
    grain.setAlpha(alpha)

    rng = random.Random(SEED)
    painter = QPainter(tile)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(grain)

    for _ in range(CIRCLE_COUNT):
        cx = rng.uniform(0, tile_size)
        cy = rng.uniform(0, tile_size)
        radius = rng.uniform(MIN_RADIUS, MAX_RADIUS)
        for dx in (-tile_size, 0, tile_size):
            for dy in (-tile_size, 0, tile_size):
                x, y = cx + dx, cy + dy
                if x + radius < 0 or x - radius > tile_size or y + radius < 0 or y - radius > tile_size:
                    continue
                painter.drawEllipse(QRectF(x - radius, y - radius, radius * 2, radius * 2))
    painter.end()

    _tile_cache[key] = tile
    return tile
