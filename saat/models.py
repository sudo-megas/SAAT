from dataclasses import dataclass, field
from datetime import date


@dataclass
class Movement:
    caliber: str | None = None
    kind: str | None = None
    power_reserve_hours: float | None = None
    battery_life_years: float | None = None
    accuracy_min: float | None = None
    accuracy_max: float | None = None
    accuracy_unit: str | None = None
    jewels: int | None = None
    bph: int | None = None
    hacking: bool | None = None
    handwinding: bool | None = None
    origin: str | None = None


@dataclass
class Case:
    diameter_mm: float | None = None
    lug_to_lug_mm: float | None = None
    thickness_mm: float | None = None
    lug_width_mm: int | None = None
    material: str | None = None
    crystal: str | None = None
    crown: str | None = None
    bezel: str | None = None
    caseback: str | None = None
    water_resistance_m: int | None = None
    weight_g: float | None = None


@dataclass
class Dial:
    colour: str | None = None
    material: str | None = None
    indices: str | None = None
    lume: str | None = None
    complications: list[str] = field(default_factory=list)


@dataclass
class Strap:
    material: str | None = None
    colour: str | None = None
    width_mm: int | None = None
    clasp: str | None = None
    fitted: bool = False
    image: str | None = None


@dataclass
class Acquisition:
    date: date | None = None
    price: float | None = None
    currency: str | None = None
    seller: str | None = None
    url: str | None = None
    condition: str | None = None
    box_and_papers: bool | None = None
    warranty_until: date | None = None
    target_price: float | None = None
    target_date: date | None = None


@dataclass
class Maintenance:
    service_interval_years: float | None = None
    battery_due: date | None = None


@dataclass
class LogEntry:
    date: date | None = None
    kind: str | None = None
    note: str | None = None


@dataclass
class TimingEntry:
    date: date | None = None
    deviation_sec: float | None = None
    position: str | None = None


@dataclass
class Watch:
    brand: str
    model: str
    reference: str | None = None
    nickname: str | None = None
    serial: str | None = None
    group: str | None = None
    style: str | None = None
    status: str = "Owned"
    storage: str | None = None
    rating: int | None = None
    tags: list[str] = field(default_factory=list)

    movement: Movement = field(default_factory=Movement)
    case: Case = field(default_factory=Case)
    dial: Dial = field(default_factory=Dial)
    straps: list[Strap] = field(default_factory=list)
    acquisition: Acquisition = field(default_factory=Acquisition)
    maintenance: Maintenance = field(default_factory=Maintenance)
    log: list[LogEntry] = field(default_factory=list)
    worn: list[date] = field(default_factory=list)
    timing: list[TimingEntry] = field(default_factory=list)
    notes: str | None = None

    # Not in SPEC.md's data model table: the gallery order chosen in the
    # Images tab (first = primary, per SPEC.md §5.2/§5.6). Filenames only;
    # list_images() falls back to alphabetical order for any watch.toml
    # written before this field existed, or for files not listed here.
    images: list[str] = field(default_factory=list)
