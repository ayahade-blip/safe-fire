package com.safefire.monitor.ui.theme

import android.app.Activity
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.SideEffect
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.view.WindowCompat
import com.safefire.monitor.data.ThemeMode

val Ink900 = Color(0xFF0A0E14)
val Ink800 = Color(0xFF10161F)
val Ink700 = Color(0xFF161E29)
val Ink600 = Color(0xFF1E2836)
val Ink500 = Color(0xFF2A3646)
val Slate400 = Color(0xFF62718A)
val Slate300 = Color(0xFF8D9BB0)
val Slate200 = Color(0xFFB9C4D4)
val Paper = Color(0xFFE8EDF5)

val Light50 = Color(0xFFF6F7F9)
val Light100 = Color(0xFFFFFFFF)
val Light200 = Color(0xFFEDF0F5)
val Light300 = Color(0xFFDCE2EB)

/**
 * Light page, raised container and hairline.
 *
 * The page was white and so was every card, which made a Panel invisible on a
 * surface background. Darkening only the page restores the boundary without
 * touching card contrast: onSurface on white stays 17.98:1.
 */
val PageLight = Color(0xFFEDF1F7)
val RaisedLight = Color(0xFFF5F7FB)
val EdgeLight = Color(0xFFC7D0DD)

val Ember = Color(0xFFFF8A3D)
val EmberDeep = Color(0xFFE0631B)
val Beacon = Color(0xFF3D8BFF)

val CalmGreen = Color(0xFF25C685)
val WatchAmber = Color(0xFFF5A524)
val AlertOrange = Color(0xFFFF7A1A)
val ConfirmRed = Color(0xFFF4374B)
val OfflineGrey = Color(0xFF6B7A90)

/**
 * Alarm fills. Large areas only: the banner, a health dot, an icon at 20 dp or
 * more. Never text, which is a separate token below.
 *
 * These do not change between light and dark. A person has to recognise the
 * signal instantly whenever they look, and a red that becomes a different red
 * at noon is a red you relearn twice a day. Contrast is a property of the pair,
 * so one pair works in both themes.
 */
val NormalSignal = Color(0xFF25C685)
val WatchSignal = Color(0xFFF5A524)
val AlertSignal = Color(0xFFFF7A1A)
val ConfirmSignal = Color(0xFFF4374B)

/**
 * OFFLINE gets no hue at all. Offline is the absence of signal, and every grey
 * that reads as a band fails against both near black and white anyway
 * (`OfflineGrey` measures 4.43:1 and 4.36:1). A dark neutral field with a
 * visible border is the honest form, and it is the only band identifiable
 * without colour vision.
 */
val OfflineSignal = Color(0xFF1E2836)

/**
 * The only text colour that sits on a signal fill. White measures 2.04:1 to
 * 3.82:1 on these four and fails everywhere; near black measures 5.06:1 to
 * 9.48:1. This is not a style choice.
 */
val OnBand = Color(0xFF0A0E14)

/**
 * Alarm text on a surface, verified against `surfaceContainer #161E29`, which
 * is the worst surface a coloured label sits on.
 *
 * Confirm and Offline are new: the fills `#F4374B` and `#6B7A90` measure
 * 4.39:1 and 3.84:1 as text and had to be lightened to pass.
 */
val NormalInkDark = Color(0xFF25C685)
val WatchInkDark = Color(0xFFF5A524)
val AlertInkDark = Color(0xFFFF7A1A)
val ConfirmInkDark = Color(0xFFFF7A88)
val OfflineInkDark = Color(0xFFA3B0C4)

/** The same five, verified against white and the light page `#EDF1F7`. */
val NormalInkLight = Color(0xFF0B7A52)
val WatchInkLight = Color(0xFF8A5A00)
val AlertInkLight = Color(0xFFB34700)
val ConfirmInkLight = Color(0xFFC1122A)
val OfflineInkLight = Color(0xFF4F5D72)

// ChannelTemp, ChannelGas and ChannelFlame were removed here. ChannelGas
// #7C6BFF on #161E29 was 4.32:1, below the 4.5:1 AA floor for its own value
// text. The deeper reason is that a permanently saturated channel leaves the
// screen no way to get louder once that channel is actually in trouble, so
// tiles are monochrome at rest and take an alarm ink only while contributing.

/** Detection box strokes. These sit on video, not on a theme surface. */
val BoxFlame = Color(0xFFFF3C28)
val BoxSmoke = Color(0xFF3CA6FF)

val SafeFireTypography = Typography(
    displayLarge = TextStyle(
        fontFamily = FontFamily.Default,
        fontWeight = FontWeight.Bold,
        fontSize = 52.sp,
        lineHeight = 56.sp,
        letterSpacing = (-1.2).sp
    ),
    displayMedium = TextStyle(
        fontFamily = FontFamily.Default,
        fontWeight = FontWeight.Bold,
        fontSize = 38.sp,
        lineHeight = 44.sp,
        letterSpacing = (-0.8).sp
    ),
    headlineMedium = TextStyle(
        fontFamily = FontFamily.Default,
        fontWeight = FontWeight.SemiBold,
        fontSize = 24.sp,
        lineHeight = 30.sp,
        letterSpacing = (-0.4).sp
    ),
    headlineSmall = TextStyle(
        fontFamily = FontFamily.Default,
        fontWeight = FontWeight.SemiBold,
        fontSize = 20.sp,
        lineHeight = 26.sp
    ),
    titleLarge = TextStyle(
        fontFamily = FontFamily.Default,
        fontWeight = FontWeight.SemiBold,
        fontSize = 17.sp,
        lineHeight = 23.sp
    ),
    titleMedium = TextStyle(
        fontFamily = FontFamily.Default,
        fontWeight = FontWeight.Medium,
        fontSize = 15.sp,
        lineHeight = 21.sp
    ),
    bodyLarge = TextStyle(
        fontFamily = FontFamily.Default,
        fontWeight = FontWeight.Normal,
        fontSize = 15.sp,
        lineHeight = 22.sp
    ),
    bodyMedium = TextStyle(
        fontFamily = FontFamily.Default,
        fontWeight = FontWeight.Normal,
        fontSize = 13.5.sp,
        lineHeight = 19.sp
    ),
    /**
     * Zero tracking, and it exists for Arabic. Every label slot carries positive
     * letterSpacing, which on a cursive script pushes apart glyphs that are
     * meant to join. Labels are for numerals and units; translated prose belongs
     * here or in a body slot.
     */
    bodySmall = TextStyle(
        fontFamily = FontFamily.Default,
        fontWeight = FontWeight.Normal,
        fontSize = 12.sp,
        lineHeight = 17.sp,
        letterSpacing = 0.sp
    ),
    labelLarge = TextStyle(
        fontFamily = FontFamily.Default,
        fontWeight = FontWeight.SemiBold,
        fontSize = 13.sp,
        letterSpacing = 0.2.sp
    ),
    labelMedium = TextStyle(
        fontFamily = FontFamily.Default,
        fontWeight = FontWeight.Medium,
        fontSize = 11.5.sp,
        letterSpacing = 0.6.sp
    ),
    labelSmall = TextStyle(
        fontFamily = FontFamily.Default,
        fontWeight = FontWeight.Medium,
        fontSize = 10.5.sp,
        letterSpacing = 0.8.sp
    )
)

/** Radii were literals at twenty odd call sites, so they had drifted apart. */
val SafeFireShapes = Shapes(
    extraSmall = RoundedCornerShape(8.dp),
    small = RoundedCornerShape(12.dp),
    medium = RoundedCornerShape(18.dp),
    large = RoundedCornerShape(22.dp),
    extraLarge = RoundedCornerShape(28.dp)
)

private val DarkScheme = darkColorScheme(
    primary = Ember,
    onPrimary = Color(0xFF241000),
    primaryContainer = Color(0xFF3A2313),
    onPrimaryContainer = Color(0xFFFFD9BE),
    secondary = Beacon,
    onSecondary = Color(0xFF001B3D),
    tertiary = CalmGreen,
    onTertiary = Color(0xFF00281A),
    background = Ink900,
    onBackground = Paper,
    surface = Ink800,
    onSurface = Paper,
    surfaceVariant = Ink600,
    onSurfaceVariant = Slate300,
    surfaceContainer = Ink700,
    surfaceContainerHigh = Ink600,
    outline = Ink500,
    outlineVariant = Ink600,
    error = ConfirmRed,
    // White on this red is 3.82:1. Near black is 5.06:1 and is the same rule the
    // banner follows, so a filled error surface stays readable.
    onError = OnBand
)

private val LightScheme = lightColorScheme(
    primary = EmberDeep,
    onPrimary = Color.White,
    primaryContainer = Color(0xFFFFE1CC),
    onPrimaryContainer = Color(0xFF3A1A00),
    secondary = Color(0xFF1F63C8),
    onSecondary = Color.White,
    tertiary = Color(0xFF0E8F5E),
    onTertiary = Color.White,
    background = PageLight,
    onBackground = Color(0xFF12171F),
    surface = Light100,
    onSurface = Color(0xFF12171F),
    surfaceVariant = Light200,
    onSurfaceVariant = Color(0xFF465363),
    surfaceContainer = Light100,
    surfaceContainerHigh = RaisedLight,
    outline = EdgeLight,
    outlineVariant = Light200,
    error = Color(0xFFD32236),
    onError = Color.White
)

@Composable
fun SafeFireTheme(
    mode: ThemeMode = ThemeMode.SYSTEM,
    content: @Composable () -> Unit
) {
    val darkTheme = when (mode) {
        ThemeMode.SYSTEM -> isSystemInDarkTheme()
        ThemeMode.DARK -> true
        ThemeMode.LIGHT -> false
    }
    val scheme = if (darkTheme) DarkScheme else LightScheme
    val view = LocalView.current

    if (!view.isInEditMode) {
        SideEffect {
            val window = (view.context as Activity).window
            WindowCompat.getInsetsController(window, view)
                .isAppearanceLightStatusBars = !darkTheme
        }
    }

    MaterialTheme(
        colorScheme = scheme,
        shapes = SafeFireShapes,
        typography = SafeFireTypography,
        content = content
    )
}

/**
 * Which ink set applies. This reads the resolved scheme rather than the system
 * setting, because [SafeFireTheme] also honours an explicit ThemeMode and a
 * user who forced light mode at night must not get dark inks.
 */
@Composable
fun isDarkPalette(): Boolean = MaterialTheme.colorScheme.background == Ink900
