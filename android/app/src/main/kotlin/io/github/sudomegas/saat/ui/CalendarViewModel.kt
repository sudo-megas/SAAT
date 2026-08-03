package io.github.sudomegas.saat.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import io.github.sudomegas.saat.SaatApplication
import io.github.sudomegas.saat.storage.SaatPaths
import io.github.sudomegas.saat.storage.WatchRepository
import io.github.sudomegas.saat.storage.wornIndex
import io.github.sudomegas.saat.ui.calendar.MonthLayout
import io.github.sudomegas.saat.ui.calendar.monthLayout
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import java.io.File
import java.time.LocalDate
import java.time.YearMonth

/** One day in the grid: the watch on it, if any, and what to draw for it. */
data class CalendarDay(
    val date: LocalDate,
    val slug: String?,
    /** The watch's primary photograph, or null — the cell falls back to its number. */
    val image: File?,
    val isToday: Boolean,
)

data class CalendarUiState(
    val month: YearMonth = YearMonth.now(),
    val layout: MonthLayout = monthLayout(YearMonth.now()),
    /** Keyed by date; a date with no entry is an empty day. */
    val days: Map<LocalDate, CalendarDay> = emptyMap(),
    val isLoaded: Boolean = false,
    val isCollectionEmpty: Boolean = false,
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

    val state: StateFlow<CalendarUiState> =
        combine(repository.state, _month) { collection, month ->
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
            )
        }.stateIn(
            viewModelScope,
            SharingStarted.WhileSubscribed(5_000),
            CalendarUiState(month = YearMonth.from(today()), layout = monthLayout(YearMonth.from(today()))),
        )

    fun showMonth(month: YearMonth) {
        _month.value = month
    }

    fun step(months: Long) {
        _month.value = _month.value.plusMonths(months)
    }

    companion object {
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
