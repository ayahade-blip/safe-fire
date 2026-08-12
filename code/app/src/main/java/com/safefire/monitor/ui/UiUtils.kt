package com.safefire.monitor.ui

import android.content.Context
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CloudOff
import androidx.compose.material.icons.filled.LocalFireDepartment
import androidx.compose.material.icons.filled.Shield
import androidx.compose.material.icons.filled.Visibility
import androidx.compose.material.icons.filled.Warning
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.stringResource
import com.safefire.monitor.R
import com.safefire.monitor.data.AlarmLevel
import com.safefire.monitor.data.SensorSample
import com.safefire.monitor.ui.theme.AlertOrange
import com.safefire.monitor.ui.theme.CalmGreen
import com.safefire.monitor.ui.theme.ConfirmRed
import com.safefire.monitor.ui.theme.OfflineGrey
import com.safefire.monitor.ui.theme.WatchAmber
import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Date
import java.util.Locale

/**
 * How an absent measurement is written. One constant, so a missing reading can
 * never be rendered as a plausible number by a call site that forgot to check.
 */
const val NO_READING = "—"

/**
 * Format a nullable measurement, or say plainly that there is none.
 *
 * Every sensor channel is nullable because null means "not measured": the
 * channel is down, the node is silent, or it has never been baselined. Printing
 * 0.0 for any of those, which is what this app used to do, states a measurement
 * that was never taken.
 */
fun Float?.orNoReading(format: String = "%.1f", unit: String = ""): String =
    if (this == null) NO_READING else format.format(this) + unit

fun Int?.orNoReading(unit: String = ""): String =
    if (this == null) NO_READING else "$this$unit"

data class AlarmVisual(
    val color: Color,
    val icon: ImageVector,
    val title: String,
    val description: String
)

@Composable
fun AlarmLevel.visual(): AlarmVisual = when (this) {
    AlarmLevel.NORMAL -> AlarmVisual(
        CalmGreen, Icons.Filled.Shield,
        stringResource(R.string.level_normal), stringResource(R.string.level_normal_desc)
    )
    AlarmLevel.WATCH -> AlarmVisual(
        WatchAmber, Icons.Filled.Visibility,
        stringResource(R.string.level_watch), stringResource(R.string.level_watch_desc)
    )
    AlarmLevel.ALERT -> AlarmVisual(
        AlertOrange, Icons.Filled.Warning,
        stringResource(R.string.level_alert), stringResource(R.string.level_alert_desc)
    )
    AlarmLevel.CONFIRMED -> AlarmVisual(
        ConfirmRed, Icons.Filled.LocalFireDepartment,
        stringResource(R.string.level_confirmed), stringResource(R.string.level_confirmed_desc)
    )
    AlarmLevel.OFFLINE -> AlarmVisual(
        OfflineGrey, Icons.Filled.CloudOff,
        stringResource(R.string.level_offline), stringResource(R.string.level_offline_desc)
    )
}

/**
 * The one-sentence verdict, in the reader's language.
 *
 * fuse() in node_reader.py derives this from the level and from nothing else, so
 * rebuilding it here loses no information and gains the reader their own
 * language. The English sentence the Jetson published stays in the event record,
 * where it belongs: that record is evidence of what the edge device concluded at
 * the time, and a display preference has no business rewriting it.
 */
@Composable
fun AlarmLevel.conclusionText(): String = stringResource(
    when (this) {
        AlarmLevel.NORMAL -> R.string.conclusion_normal
        AlarmLevel.WATCH -> R.string.conclusion_watch
        AlarmLevel.ALERT -> R.string.conclusion_alert
        AlarmLevel.CONFIRMED -> R.string.conclusion_confirmed
        AlarmLevel.OFFLINE -> R.string.conclusion_offline
    }
)

/** What the camera channel concluded, mirroring the three cases in fuse(). */
@Composable
fun visionText(contributed: Boolean, level: AlarmLevel): String = stringResource(
    when {
        contributed -> R.string.vision_sustained
        level == AlarmLevel.OFFLINE -> R.string.vision_pipeline_down
        else -> R.string.vision_none
    }
)

/**
 * What the sensor channel measured, composed from the sample itself.
 *
 * Only channels that answered appear. A channel that sent nothing is left out of
 * the sentence entirely rather than described as zero, which is the same rule the
 * tiles follow and the reason this is built here instead of being read from the
 * prose the node wrote.
 */
@Composable
fun SensorSample.sensorsText(): String {
    if (!present) return stringResource(R.string.sensors_no_sample)

    val separator = stringResource(R.string.list_separator)
    val surface = surfaceRiseC?.let {
        stringResource(R.string.sensors_part_surface, "%+.2f".format(it))
    }
    val gas = gasRatio?.let {
        stringResource(R.string.sensors_part_gas, "%.3f".format(it))
    }
    val infrared = flameDropMv?.let {
        stringResource(R.string.sensors_part_ir, it.toString())
    }

    val parts = listOfNotNull(surface, gas, infrared)
    if (parts.isEmpty()) return stringResource(R.string.sensors_none_elevated)
    return stringResource(R.string.sensors_said, parts.joinToString(separator))
}

fun AlarmLevel.tint(): Color = when (this) {
    AlarmLevel.NORMAL -> CalmGreen
    AlarmLevel.WATCH -> WatchAmber
    AlarmLevel.ALERT -> AlertOrange
    AlarmLevel.CONFIRMED -> ConfirmRed
    AlarmLevel.OFFLINE -> OfflineGrey
}

private val clock = SimpleDateFormat("HH:mm:ss", Locale.getDefault())
private val clockShort = SimpleDateFormat("HH:mm", Locale.getDefault())
private val dayStamp = SimpleDateFormat("d MMM", Locale.getDefault())

fun Long.asClock(): String = clock.format(Date(this))
fun Long.asClockShort(): String = clockShort.format(Date(this))
fun Long.asDay(): String = dayStamp.format(Date(this))

fun Long.asRelative(ctx: Context): String {
    val delta = System.currentTimeMillis() - this
    val minutes = delta / 60_000
    val hours = delta / 3_600_000
    return when {
        minutes < 1 -> ctx.getString(R.string.just_now)
        minutes < 60 -> ctx.getString(R.string.minutes_ago, minutes.toInt())
        hours < 24 -> ctx.getString(R.string.hours_ago, hours.toInt())
        else -> asDay()
    }
}

enum class DayBucket { TODAY, YESTERDAY, EARLIER }

fun Long.dayBucket(): DayBucket {
    val now = Calendar.getInstance()
    val then = Calendar.getInstance().apply { timeInMillis = this@dayBucket }
    val sameYear = now.get(Calendar.YEAR) == then.get(Calendar.YEAR)
    val dayDelta = now.get(Calendar.DAY_OF_YEAR) - then.get(Calendar.DAY_OF_YEAR)
    return when {
        sameYear && dayDelta == 0 -> DayBucket.TODAY
        sameYear && dayDelta == 1 -> DayBucket.YESTERDAY
        else -> DayBucket.EARLIER
    }
}
