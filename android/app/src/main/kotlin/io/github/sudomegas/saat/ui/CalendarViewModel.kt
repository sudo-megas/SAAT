package io.github.sudomegas.saat.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import io.github.sudomegas.saat.SaatApplication
import io.github.sudomegas.saat.storage.SaatPaths
import io.github.sudomegas.saat.storage.WatchRepository
import io.github.sudomegas.saat.storage.WatchSort
import io.github.sudomegas.saat.storage.query
import io.github.sudomegas.saat.storage.wornIndex
import io.github.sudomegas.saat.ui.calendar.MonthLayout
import io.github.sudomegas.saat.ui.calendar.MonthStats
import io.github.sudomegas.saat.ui.calendar.monthStats
import io.github.sudomegas.saat.ui.calendar.daysBetween
import io.github.sudomegas.saat.ui.calendar.monthLayout
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import java.io.File
import java.time.LocalDate
import java.time.YearMonth

/** One watch in the picker: a thumbnail and a name. */
data class PickerWatch(
    val slug: String,
    val brand: String,
    val model: String,
    val image: File?,
)

/** One day in the grid: the watch on it, if any, and what to draw for it. */
data class CalendarDay(
    val date: LocalDate,
    val slug: String?,
    /** The watch's primary photograph, or null — the cell falls back to its number. */
    val image: File?,
    val isToday: Boolean,
)

/**
 * A span of days being chosen — SPEC-ANDROID 5.5's long-press range mode.
 *
 * Two dates rather than a list, so extending the span is one assignment and the
 * order they were touched in does not matter. It replaces the desktop's
 * click-drag, which has no touch equivalent worth imitating: a drag across a
 * calendar competes with the scroll, and a drag that starts on a cell competes
 * with the tap.
 */
data class DaySelection(val anchor: LocalDate, val extent: LocalDate) {
    val dates: List<LocalDate> get() = daysBetween(anchor, extent)
    fun contains(date: LocalDate): Boolean = date in dates
}

data class CalendarUiState(
    val month: YearMonth = YearMonth.now(),
    val layout: MonthLayout = monthLayout(YearMonth.now()),
    /** Keyed by date; a date with no entry is an empty day. */
    val days: Map<LocalDate, CalendarDay> = emptyMap(),
    val isLoaded: Boolean = false,
    val isCollectionEmpty: Boolean = false,
    /** Non-null while the owner is choosing a span. */
    val selection: DaySelection? = null,
    /** The days the picker is about to fill, or null when it is closed. */
    val picking: List<LocalDate>? = null,
    val stats: MonthStats = MonthStats(0, 0, emptyList()),
    /** True while the twelve-month view is showing instead of the grid. */
    val isYearView: Boolean = false,
    /** Twelve months of `date -> slug`, for the year view's chips. */
    val year: List<Pair<YearMonth, Map<LocalDate, String>>> = emptyList(),
)

/**
 * The calendar — SPEC-ANDROID 5.5.
 *
 * The index is rebuilt from the collection on every emission rather than cached
 * and invalidated. It is a map over a few thousand dates at most, and the
 * alternative is a second copy of the wear history with three places to
 * invalidate it from — the detail button, this screen and AM8's widget — which
 * is exactly the "centralise wear storage for efficiency" this milestone's brief
 * forbids.
 */
class CalendarViewModel(
    private val repository: WatchRepository,
    private val paths: SaatPaths,
    private val today: () -> LocalDate = LocalDate::now,
) : ViewModel() {

    private val _month = MutableStateFlow(YearMonth.from(today()))
    private val _selection = MutableStateFlow<DaySelection?>(null)
    private val _picking = MutableStateFlow<List<LocalDate>?>(null)
    private val _pickerQuery = MutableStateFlow("")
    private val _isYearView = MutableStateFlow(false)

    /** What is typed in the picker's search field. Cleared when it closes. */
    val pickerQuery: StateFlow<String> = _pickerQuery.asStateFlow()

    /**
     * The collection as the picker shows it: search field plus thumbnails —
     * SPEC-ANDROID 5.5.
     *
     * The AM3 matcher again, unchanged. A collection large enough to need a
     * search here is large enough that scrolling it under a bottom sheet would
     * be the slowest part of entering a year of backlog.
     */
    val pickerWatches: StateFlow<List<PickerWatch>> =
        combine(repository.state, _pickerQuery) { collection, query ->
            collection.watches
                .query(query, WatchSort.BRAND, today())
                .mapNotNull { record ->
                    val watch = record.watch ?: return@mapNotNull null
                    PickerWatch(
                        slug = record.slug,
                        brand = watch.brand,
                        model = watch.model,
                        image = watch.images.firstOrNull()
                            ?.let { File(paths.watchMedia(record.slug), File(it).name) },
                    )
                }
        }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())

    val state: StateFlow<CalendarUiState> =
        combine(
            repository.state,
            _month,
            _selection,
            _picking,
            _isYearView,
        ) { collection, month, selection, picking, isYearView ->
            val index = collection.records.wornIndex()
            val now = today()
            val layout = monthLayout(month)

            CalendarUiState(
                month = month,
                layout = layout,
                days = layout.days.associateWith { date ->
                    val record = index[date]
                    CalendarDay(
                        date = date,
                        slug = record?.slug,
                        image = record?.watch?.images?.firstOrNull()?.let {
                            File(paths.watchMedia(record.slug), File(it).name)
                        },
                        isToday = date == now,
                    )
                },
                isLoaded = collection.isLoaded,
                isCollectionEmpty = collection.isLoaded && collection.records.isEmpty(),
                selection = selection,
                picking = picking,
                stats = collection.records.monthStats(month),
                isYearView = isYearView,
                // Built only while the year view is showing: twelve months of
                // index lookups is cheap, but doing it on every emission of a
                // screen that is not on top would be work for nobody.
                year = if (!isYearView) emptyList() else (1..MONTHS_IN_YEAR).map { number ->
                    val each = YearMonth.of(month.year, number)
                    each to index.filterKeys { YearMonth.from(it) == each }
                        .mapValues { (_, record) -> record.slug }
                },
            )
        }.stateIn(
            viewModelScope,
            SharingStarted.WhileSubscribed(5_000),
            CalendarUiState(month = YearMonth.from(today()), layout = monthLayout(YearMonth.from(today()))),
        )

    /**
     * A tap: opens the picker for that one day, or extends the span when one is
     * being chosen.
     *
     * The same gesture on a filled day and an empty one — SPEC-ANDROID 5.5 opens
     * the same picker for both, with the current watch marked when there is one.
     * "Every day is editable, past or future", so nothing here consults the
     * clock: future days are how you plan.
     */
    fun onDayTapped(date: LocalDate) {
        val selection = _selection.value
        if (selection == null) {
            _picking.value = listOf(date)
        } else {
            _selection.value = selection.copy(extent = date)
        }
    }

    /** A long press starts range mode on that day — the brief's item 5. */
    fun onDayLongPressed(date: LocalDate) {
        _selection.value = DaySelection(date, date)
    }

    /** Open the picker for the whole span the owner has chosen. */
    fun pickForSelection() {
        _picking.value = _selection.value?.dates
    }

    fun cancelSelection() {
        _selection.value = null
    }

    fun dismissPicker() {
        _picking.value = null
        _pickerQuery.value = ""
    }

    fun setPickerQuery(query: String) {
        _pickerQuery.value = query
    }

    /**
     * Fill the days being picked with one watch.
     *
     * Straight through AM4b's `assignWorn` — the single wear-logging path — so
     * the one-watch-per-day rule, the silent move and the backup policy are the
     * ones already built and tested rather than a second implementation. This
     * milestone's brief says "reused, not reimplemented", and this is the whole
     * of that reuse: one call.
     */
    fun assign(slug: String) {
        val dates = _picking.value ?: return
        viewModelScope.launch {
            repository.assignWorn(slug, dates)
            _picking.value = null
            _selection.value = null
        }
    }

    /** Empty the days being picked, whichever watches hold them. */
    fun clearPicked() {
        val dates = _picking.value ?: return
        viewModelScope.launch {
            repository.clearWorn(dates)
            _picking.value = null
            _selection.value = null
        }
    }

    fun toggleYearView() {
        _isYearView.value = !_isYearView.value
    }

    fun showMonth(month: YearMonth) {
        _month.value = month
    }

    fun step(months: Long) {
        _month.value = _month.value.plusMonths(months)
    }

    companion object {
        private const val MONTHS_IN_YEAR = 12

        fun factory(app: SaatApplication): ViewModelProvider.Factory =
            object : ViewModelProvider.Factory {
                @Suppress("UNCHECKED_CAST")
                override fun <T : ViewModel> create(modelClass: Class<T>): T =
                    CalendarViewModel(
                        repository = app.watchRepository,
                        paths = app.paths,
                    ) as T
            }
    }
}
