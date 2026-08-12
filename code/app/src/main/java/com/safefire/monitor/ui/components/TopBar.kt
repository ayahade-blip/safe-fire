package com.safefire.monitor.ui.components

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.tween
import androidx.compose.animation.expandVertically
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.shrinkVertically
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.safefire.monitor.R
import com.safefire.monitor.data.AlarmLevel
import com.safefire.monitor.ui.asRelative
import com.safefire.monitor.ui.theme.tone
import com.safefire.monitor.ui.visual

/**
 * The bar at the top of every screen.
 *
 * The old one printed the screen's own name and nothing else, which the selected
 * tab in the bottom bar was already saying, and hung a bare gear at the right
 * edge. Its whole height carried no information.
 *
 * This one keeps the name, since it anchors where you are, and gives the second
 * line to the two facts that had no home outside the Devices screen: what the
 * system currently says, and how long ago the phone last heard anything. Both
 * matter on every screen, not only on the one showing the shield.
 *
 * Colour is used once and only when it means something. Instead of tinting the
 * whole surface, which read as a stain, an alarm shows as the status dot and a
 * hairline along the bottom edge.
 */
@Composable
fun SafeFireTopBar(
    title: String,
    level: AlarmLevel,
    lastSync: Long,
    onSettings: () -> Unit,
    modifier: Modifier = Modifier,
    onBack: (() -> Unit)? = null
) {
    val ctx = LocalContext.current
    val scheme = MaterialTheme.colorScheme
    val tone = level.tone()
    val v = level.visual()

    val accent by animateColorAsState(
        tone.signal,
        tween(450, easing = FastOutSlowInEasing),
        label = "topAccent"
    )

    Column(
        modifier
            .fillMaxWidth()
            .background(scheme.background)
            .statusBarsPadding()
    ) {
        Row(
            Modifier
                .fillMaxWidth()
                .padding(start = 20.dp, end = 14.dp, top = 12.dp, bottom = 12.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            if (onBack != null) {
                CircleAction(
                    icon = Icons.AutoMirrored.Filled.ArrowBack,
                    description = stringResource(R.string.back),
                    onClick = onBack
                )
                Spacer(Modifier.width(14.dp))
            }

            Column(Modifier.weight(1f)) {
                Text(
                    text = title,
                    style = MaterialTheme.typography.headlineSmall,
                    color = scheme.onBackground,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
                Spacer(Modifier.height(3.dp))
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(7.dp)
                ) {
                    // OFFLINE stays hollow. It is the absence of a signal, and
                    // filling it in would make "nothing is watching" look like a
                    // reading of its own.
                    Box(
                        Modifier
                            .size(8.dp)
                            .clip(CircleShape)
                            .then(
                                if (level == AlarmLevel.OFFLINE) {
                                    Modifier.border(1.5.dp, tone.ink, CircleShape)
                                } else {
                                    Modifier.background(tone.ink)
                                }
                            )
                    )
                    Text(
                        text = statusLine(v.title, lastSync, ctx),
                        style = MaterialTheme.typography.labelMedium,
                        color = scheme.onSurfaceVariant,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                }
            }

            if (onBack == null) {
                CircleAction(
                    icon = Icons.Filled.Settings,
                    description = stringResource(R.string.settings),
                    onClick = onSettings
                )
            }
        }

        // A hairline, not a wash. It appears only for a real alarm, which is the
        // only time the frame of the app should be saying anything at all.
        AnimatedVisibility(
            visible = level.isAlarming,
            enter = fadeIn() + expandVertically(),
            exit = fadeOut() + shrinkVertically()
        ) {
            Box(
                Modifier
                    .fillMaxWidth()
                    .height(3.dp)
                    .background(accent)
            )
        }
    }
}

/** The level, and how long ago the phone last heard anything. */
@Composable
private fun statusLine(
    levelWord: String,
    lastSync: Long,
    ctx: android.content.Context
): String = if (lastSync > 0L) {
    levelWord + "  ·  " + lastSync.asRelative(ctx)
} else {
    levelWord
}

/**
 * An icon that reads as a button.
 *
 * A bare glyph at the edge of a bar is ambiguous: it could be decoration. The
 * tonal circle costs nothing and makes the target obvious, and it gives the
 * 48 dp touch area the glyph on its own did not have.
 */
@Composable
private fun CircleAction(
    icon: ImageVector,
    description: String,
    onClick: () -> Unit
) {
    Box(
        Modifier
            .size(42.dp)
            .clip(CircleShape)
            .background(MaterialTheme.colorScheme.surfaceContainerHigh)
            .clickable(onClick = onClick),
        contentAlignment = Alignment.Center
    ) {
        Icon(
            imageVector = icon,
            contentDescription = description,
            tint = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.size(19.dp)
        )
    }
}
