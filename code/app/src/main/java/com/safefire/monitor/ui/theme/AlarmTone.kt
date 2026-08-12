package com.safefire.monitor.ui.theme

import androidx.compose.runtime.Composable
import androidx.compose.runtime.Immutable
import androidx.compose.ui.graphics.Color
import com.safefire.monitor.data.AlarmLevel

/**
 * The colours one alarm level owns.
 *
 * [signal] and [ink] are kept apart because they answer different questions.
 * A fill only has to be distinguishable as a graphical object, while text has
 * to be readable on a surface, and the old palette conflated them: `ConfirmRed`
 * is a perfectly good fill and a failing text colour at 4.39:1.
 *
 * [signal], [onBand] and [border] are the same in light and dark. Only [ink]
 * follows the theme, because it is the only one measured against a surface that
 * changes.
 *
 * [border] is null for every level except OFFLINE, which is drawn as a dark
 * neutral and needs a visible edge to be a band at all.
 */
@Immutable
data class AlarmTone(
    val signal: Color,
    val ink: Color,
    val onBand: Color,
    val border: Color?
)

@Composable
fun AlarmLevel.tone(): AlarmTone {
    val dark = isDarkPalette()
    return when (this) {
        AlarmLevel.NORMAL -> AlarmTone(
            signal = NormalSignal,
            ink = if (dark) NormalInkDark else NormalInkLight,
            onBand = OnBand,
            border = null
        )
        AlarmLevel.WATCH -> AlarmTone(
            signal = WatchSignal,
            ink = if (dark) WatchInkDark else WatchInkLight,
            onBand = OnBand,
            border = null
        )
        AlarmLevel.ALERT -> AlarmTone(
            signal = AlertSignal,
            ink = if (dark) AlertInkDark else AlertInkLight,
            onBand = OnBand,
            border = null
        )
        AlarmLevel.CONFIRMED -> AlarmTone(
            signal = ConfirmSignal,
            ink = if (dark) ConfirmInkDark else ConfirmInkLight,
            onBand = OnBand,
            border = null
        )
        // The offline band stays dark in both themes, so its text and its edge
        // are measured against that band and not against the page.
        AlarmLevel.OFFLINE -> AlarmTone(
            signal = OfflineSignal,
            ink = if (dark) OfflineInkDark else OfflineInkLight,
            onBand = Paper,
            border = OfflineInkDark
        )
    }
}
