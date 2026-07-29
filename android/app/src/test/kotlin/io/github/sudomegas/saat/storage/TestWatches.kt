package io.github.sudomegas.saat.storage

import java.time.LocalDate

/**
 * Fixtures, built in code and never committed as files — SPEC-ANDROID hard rule
 * 1 applies to test assets exactly as it applies to shipped code.
 *
 * [fullyPopulatedWatch] is the parity fixture and has a twin: the same watch,
 * field for field and value for value, is constructed in Python by
 * `android/tools/parity_check.py`. That is deliberate duplication. The script
 * writes its copy with the desktop's own `saat.storage.save_watch` and reads
 * Kotlin's copy back with the desktop's own `saat.storage.load_collection`, so
 * if the two ever stop agreeing — a renamed key, a dropped field, a date that
 * turned into a string — the Android build goes red instead of the divergence
 * waiting until AM10's ZIP bridge to be discovered.
 *
 * EVERY field carries a distinctive value, including the ones no screen reads
 * yet. A field left at its default here would round-trip successfully whether
 * or not the mapper knows it exists.
 */
fun fullyPopulatedWatch() = Watch(
    brand = "Grand Seiko",
    model = "SBGA211",
    reference = "SBGA211",
    nickname = "Snowflake",
    serial = "D1234567",
    group = "Seiko Group",
    style = "Dress",
    status = "Owned",
    storage = "Winder slot 2",
    rating = 5,
    // İzmir is in the tags on purpose: a dotted capital I is the character that
    // breaks naive lowercasing, and it has to survive a UTF-8 round trip
    // through both writers untouched.
    tags = listOf("grail", "daily", "İzmir"),

    movement = Movement(
        caliber = "9R65",
        kind = "Spring Drive",
        powerReserveHours = 72.0,
        batteryLifeYears = 2.5,
        accuracyMin = -1.0,
        accuracyMax = 1.0,
        accuracyUnit = "sec/day",
        jewels = 30,
        bph = 28800,
        hacking = true,
        handwinding = false,
        origin = "Japan",
    ),
    case = Case(
        diameterMm = 41.0,
        lugToLugMm = 49.0,
        thicknessMm = 12.5,
        lugWidthMm = 19,
        material = "Titanium",
        crystal = "Sapphire",
        crown = "Push-pull",
        bezel = "Fixed",
        caseback = "Exhibition",
        waterResistanceM = 100,
        weightG = 100.5,
    ),
    dial = Dial(
        colour = "White",
        material = "Snowflake pattern",
        indices = "Applied",
        lume = "LumiBrite",
        complications = listOf("Power Reserve", "Date"),
    ),
    straps = listOf(
        Strap(
            material = "Titanium Bracelet",
            colour = "Silver",
            widthMm = 19,
            clasp = "Butterfly",
            fitted = true,
            image = "bracelet.jpg",
        ),
        Strap(
            material = "Leather",
            colour = "Brown",
            clasp = "Pin Buckle",
            fitted = false,
        ),
    ),
    acquisition = Acquisition(
        date = LocalDate.of(2024, 3, 11),
        price = 4200.5,
        currency = "TRY",
        seller = "Saat Dünyası",
        url = "https://example.com/sbga211",
        condition = "New",
        boxAndPapers = true,
        warrantyUntil = LocalDate.of(2027, 3, 11),
        targetPrice = 3900.0,
        targetDate = LocalDate.of(2024, 1, 1),
    ),
    maintenance = Maintenance(
        serviceIntervalYears = 5.5,
        batteryDue = LocalDate.of(2027, 1, 1),
    ),
    log = listOf(
        LogEntry(date = LocalDate.of(2024, 3, 11), kind = "Note", note = "Bought in İzmir"),
        LogEntry(date = LocalDate.of(2025, 1, 2), kind = "Service", note = "Full service"),
    ),
    worn = listOf(
        LocalDate.of(2024, 3, 12),
        LocalDate.of(2024, 3, 13),
        LocalDate.of(2025, 1, 1),
    ),
    timing = listOf(
        TimingEntry(date = LocalDate.of(2024, 4, 1), deviationSec = 0.5, position = "Dial Up"),
        TimingEntry(date = LocalDate.of(2024, 5, 1), deviationSec = -1.25, position = "Crown Down"),
    ),
    notes = "A daily wearer.\nSecond line of notes.",
    images = listOf("front.jpg", "clasp.jpg"),
)

/** The other end of the range: what SPEC-ANDROID 5.7 promises must be saveable. */
fun minimalWatch() = Watch(brand = "Casio", model = "F-91W")

/**
 * The exact bytes the desktop's `saat/storage.py` writes for
 * [fullyPopulatedWatch], captured by running it.
 *
 * Embedded rather than generated so the "a desktop file loads here intact" test
 * runs everywhere, including on a machine with no Python. CI additionally
 * regenerates this from the desktop's real writer and asserts the two are
 * byte-identical, so the constant cannot quietly drift away from what the
 * desktop actually produces — see `DesktopParityTest`.
 */
val DESKTOP_WRITTEN_FIXTURE = """
brand = "Grand Seiko"
model = "SBGA211"
reference = "SBGA211"
nickname = "Snowflake"
serial = "D1234567"
group = "Seiko Group"
style = "Dress"
status = "Owned"
storage = "Winder slot 2"
rating = 5
tags = ["grail", "daily", "İzmir"]
worn = [2024-03-12, 2024-03-13, 2025-01-01]
notes = "A daily wearer.\nSecond line of notes."
images = ["front.jpg", "clasp.jpg"]

[movement]
caliber = "9R65"
kind = "Spring Drive"
power_reserve_hours = 72.0
battery_life_years = 2.5
accuracy_min = -1.0
accuracy_max = 1.0
accuracy_unit = "sec/day"
jewels = 30
bph = 28800
hacking = true
handwinding = false
origin = "Japan"

[case]
diameter_mm = 41.0
lug_to_lug_mm = 49.0
thickness_mm = 12.5
lug_width_mm = 19
material = "Titanium"
crystal = "Sapphire"
crown = "Push-pull"
bezel = "Fixed"
caseback = "Exhibition"
water_resistance_m = 100
weight_g = 100.5

[dial]
colour = "White"
material = "Snowflake pattern"
indices = "Applied"
lume = "LumiBrite"
complications = ["Power Reserve", "Date"]

[[straps]]
material = "Titanium Bracelet"
colour = "Silver"
width_mm = 19
clasp = "Butterfly"
fitted = true
image = "bracelet.jpg"

[[straps]]
material = "Leather"
colour = "Brown"
clasp = "Pin Buckle"
fitted = false

[acquisition]
date = 2024-03-11
price = 4200.5
currency = "TRY"
seller = "Saat Dünyası"
url = "https://example.com/sbga211"
condition = "New"
box_and_papers = true
warranty_until = 2027-03-11
target_price = 3900.0
target_date = 2024-01-01

[maintenance]
service_interval_years = 5.5
battery_due = 2027-01-01

[[log]]
date = 2024-03-11
kind = "Note"
note = "Bought in İzmir"

[[log]]
date = 2025-01-02
kind = "Service"
note = "Full service"

[[timing]]
date = 2024-04-01
deviation_sec = 0.5
position = "Dial Up"

[[timing]]
date = 2024-05-01
deviation_sec = -1.25
position = "Crown Down"
""".trimStart()
