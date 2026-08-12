package com.safefire.monitor.ui.components

import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.tween
import androidx.compose.animation.expandVertically
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.shrinkVertically
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.safefire.monitor.R
import com.safefire.monitor.data.AlarmLevel
import com.safefire.monitor.data.ChannelHealth
import com.safefire.monitor.ui.NO_READING
import com.safefire.monitor.ui.asClock
import com.safefire.monitor.ui.theme.NormalSignal
import com.safefire.monitor.ui.theme.tone
import com.safefire.monitor.ui.visual
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.material.icons.filled.Air
import androidx.compose.material.icons.filled.LocalFireDepartment
import androidx.compose.material.icons.filled.Thermostat
import androidx.compose.material.icons.filled.Whatshot
import androidx.compose.material.icons.filled.Videocam
import androidx.compose.material.icons.filled.Sensors
import androidx.compose.ui.graphics.Color
import androidx.compose.foundation.Canvas
import androidx.compose.material.icons.filled.GppBad
import androidx.compose.material.icons.filled.GppGood
import androidx.compose.material.icons.filled.GppMaybe
import androidx.compose.material.icons.filled.Shield
import androidx.compose.ui.text.style.TextAlign

/**
 * Secondary runs inside the band.
 *
 * The spec asked for 0.72, which measures 3.73:1 on the CONFIRMED fill and
 * fails AA for a 12 sp line. 0.88 is the lowest value that still passes on the
 * worst fill (4.66:1) while reading as quieter than the level word.
 */
private const val BAND_TEXT_ALPHA = 0.88f

/** Tile radius, held here so the clip and the dashed fault edge cannot drift. */
private val TileRadius = 18.dp



/**
 * The shield: protected now, and how the last day went.
 *
 * Two facts are carried at once because collapsing them loses the one that
 * matters. [level] is the state right now and drives the fill. [worst24h] is the
 * highest level reached inside the window and drives the ring. A fire happening
 * this second and one that ended yesterday must not produce the same picture,
 * and a node that has gone silent must never be able to look green.
 */
@Composable
fun SystemShield(
    level: AlarmLevel,
    worst24h: AlarmLevel?,
    alerts24h: Int,
    since: Long,
    unanswered: Boolean,
    onAcknowledge: () -> Unit,
    modifier: Modifier = Modifier
) {
    val tone = level.tone()
    val v = level.visual()
    val scheme = MaterialTheme.colorScheme

    val fill by animateColorAsState(
        tone.signal,
        tween(450, easing = FastOutSlowInEasing),
        label = "shieldFill"
    )
    val ringColour = worst24h?.tone()?.signal ?: scheme.outline.copy(alpha = 0.45f)

    Column(
        modifier.fillMaxWidth(),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Box(contentAlignment = Alignment.Center) {
            // The ring is the window, drawn outside the badge so it cannot be
            // read as part of the badge's own colour.
            Canvas(Modifier.size(148.dp)) {
                drawCircle(
                    color = ringColour,
                    radius = size.minDimension / 2f - 3.dp.toPx(),
                    style = Stroke(width = 5.dp.toPx())
                )
            }
            Box(
                Modifier
                    .size(118.dp)
                    .background(fill.copy(alpha = 0.16f), CircleShape)
                    .then(
                        if (tone.border == null) Modifier
                        else Modifier.border(2.dp, tone.border, CircleShape)
                    ),
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    imageVector = level.shieldIcon(),
                    contentDescription = null,
                    tint = tone.ink,
                    modifier = Modifier.size(62.dp)
                )
            }
        }

        Spacer(Modifier.height(16.dp))
        Text(
            text = v.title,
            style = MaterialTheme.typography.headlineSmall,
            color = tone.ink,
            textAlign = TextAlign.Center,
            maxLines = 2,
            overflow = TextOverflow.Ellipsis
        )
        Spacer(Modifier.height(5.dp))
        Text(
            // OFFLINE says why. On its own the word reads as a network problem,
            // when what it means here is that nothing has been checked.
            text = if (level == AlarmLevel.OFFLINE) {
                v.description
            } else {
                stringResource(R.string.banner_since, since.asClock())
            },
            style = MaterialTheme.typography.labelMedium,
            color = scheme.onSurfaceVariant,
            textAlign = TextAlign.Center
        )

        Spacer(Modifier.height(14.dp))
        // The window, in words, because a ring alone cannot say how many.
        Text(
            text = if (alerts24h == 0) {
                stringResource(R.string.shield_clear_24h)
            } else {
                stringResource(R.string.shield_alerts_24h, alerts24h.toString())
            },
            style = MaterialTheme.typography.bodyMedium,
            color = if (worst24h == null) scheme.onSurfaceVariant else worst24h.tone().ink,
            textAlign = TextAlign.Center
        )
        Text(
            text = stringResource(R.string.shield_ring_legend),
            style = MaterialTheme.typography.labelSmall,
            color = scheme.onSurfaceVariant,
            textAlign = TextAlign.Center,
            modifier = Modifier.padding(top = 3.dp)
        )

        AnimatedVisibility(
            visible = unanswered,
            enter = fadeIn() + expandVertically(),
            exit = fadeOut() + shrinkVertically()
        ) {
            Button(
                onClick = onAcknowledge,
                colors = ButtonDefaults.buttonColors(
                    containerColor = tone.signal,
                    contentColor = tone.onBand
                ),
                shape = MaterialTheme.shapes.medium,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 18.dp)
                    .height(52.dp)
            ) {
                Icon(Icons.Filled.CheckCircle, null, modifier = Modifier.size(19.dp))
                Text(
                    text = stringResource(R.string.banner_acknowledge),
                    style = MaterialTheme.typography.titleMedium,
                    modifier = Modifier.padding(start = 8.dp)
                )
            }
        }
    }
}

/** The shield's own face, so the state survives greyscale and a colour deficit. */
@Composable
private fun AlarmLevel.shieldIcon(): ImageVector = when (this) {
    AlarmLevel.NORMAL -> Icons.Filled.GppGood
    AlarmLevel.WATCH -> Icons.Filled.GppMaybe
    AlarmLevel.ALERT -> Icons.Filled.GppBad
    AlarmLevel.CONFIRMED -> Icons.Filled.GppBad
    // Not a verdict about safety. Nothing was checked, so the shield is blank.
    AlarmLevel.OFFLINE -> Icons.Filled.Shield
}

/**
 * The alert card's header: the level word and its time, once, in colour.
 *
 * Full bleed inside the card, so the colour identifies the record without
 * becoming a field that competes with the frame and the readings below it.
 */
@Composable
fun AlertHeader(level: AlarmLevel, timestamp: Long, modifier: Modifier = Modifier) {
    val tone = level.tone()
    val v = level.visual()
    Row(
        modifier
            .fillMaxWidth()
            .background(tone.signal)
            .then(
                if (tone.border == null) Modifier
                else Modifier.border(1.dp, tone.border)
            )
            .padding(horizontal = 18.dp, vertical = 15.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Icon(v.icon, null, tint = tone.onBand, modifier = Modifier.size(21.dp))
        Spacer(Modifier.width(11.dp))
        Text(
            text = v.title,
            style = MaterialTheme.typography.titleLarge,
            color = tone.onBand,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
            modifier = Modifier.weight(1f)
        )
        Text(
            text = timestamp.asClock(),
            style = MaterialTheme.typography.labelLarge,
            color = tone.onBand.copy(alpha = BAND_TEXT_ALPHA),
            maxLines = 1
        )
    }
}

/**
 * One channel, monochrome until it has something to say.
 *
 * A tile takes an alarm ink only while that channel is contributing to the
 * current level. If temperature were permanently orange and gas permanently
 * violet, the screen would already be at full saturation when the fire arrives
 * and would have no way left to get louder.
 *
 * [value] arrives formatted, dashes included. This never formats a number and
 * never decides what is missing, because two places deciding that is two
 * answers.
 */
@Composable
fun SensorTile(
    label: String,
    value: String,
    unit: String? = null,
    caption: String? = null,
    icon: ImageVector? = null,
    contributing: Boolean = false,
    level: AlarmLevel = AlarmLevel.NORMAL,
    healthy: Boolean = true,
    modifier: Modifier = Modifier
) {
    val scheme = MaterialTheme.colorScheme
    val tone = level.tone()
    val faultInk = AlarmLevel.OFFLINE.tone().ink
    val shape = RoundedCornerShape(TileRadius)

    // A dead channel cannot be contributing to anything, whatever the caller
    // was told upstream.
    val elevated = contributing && healthy
    val missing = value == NO_READING

    // Colour moves, geometry never does. A tile that grew by a digit would
    // reflow the whole page below it, and motion on this screen is reserved for
    // the fire.
    val fill by animateColorAsState(
        if (elevated) tone.signal.copy(alpha = 0.12f) else scheme.surfaceContainer,
        tween(300), label = "tileFill"
    )
    val valueColor by animateColorAsState(
        when {
            !healthy -> faultInk
            elevated -> tone.ink
            // A dash is an honest reading, not a fault, so it keeps the plain
            // value colour and says why underneath.
            else -> scheme.onSurface
        },
        tween(300), label = "tileValue"
    )
    val edge by animateColorAsState(
        if (elevated) tone.ink.copy(alpha = 0.55f) else scheme.outline.copy(alpha = 0.45f),
        tween(300), label = "tileEdge"
    )

    Column(
        modifier
            .height(112.dp)
            .clip(shape)
            .background(fill)
            .then(
                if (healthy) {
                    Modifier.border(1.dp, edge, shape)
                } else {
                    // Down reads as a broken edge, which survives greyscale and
                    // distance in a way a colour swap does not.
                    Modifier.drawBehind {
                        val w = 1.dp.toPx()
                        drawRoundRect(
                            color = faultInk,
                            topLeft = Offset(w / 2f, w / 2f),
                            size = Size(size.width - w, size.height - w),
                            cornerRadius = CornerRadius(TileRadius.toPx() - w / 2f),
                            style = Stroke(
                                width = w,
                                pathEffect = PathEffect.dashPathEffect(floatArrayOf(6f, 6f))
                            )
                        )
                    }
                }
            )
            .padding(14.dp)
    ) {
        Row(
            Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            // The icon says which instrument this is before the label is read,
            // and it follows the value's colour so a contributing channel is one
            // object rather than a coloured number next to a grey glyph.
            if (icon != null) {
                Icon(
                    imageVector = icon,
                    contentDescription = null,
                    tint = if (healthy) valueColor.copy(alpha = 0.85f) else faultInk,
                    modifier = Modifier
                        .size(16.dp)
                        .padding(end = 0.dp)
                )
                Spacer(Modifier.width(6.dp))
            }
            // Never dimmed by alpha: 11.5 sp at 70 percent drops to 3.60:1 on
            // the tile, so de-emphasis is carried by the edge and the value.
            Text(
                text = label,
                style = MaterialTheme.typography.labelMedium,
                color = scheme.onSurfaceVariant,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
                modifier = Modifier.weight(1f)
            )
            Box(
                Modifier
                    .size(6.dp)
                    .background(
                        if (healthy) NormalSignal.copy(alpha = 0.6f) else faultInk,
                        CircleShape
                    )
            )
        }

        Spacer(Modifier.height(6.dp))

        Row(verticalAlignment = Alignment.Bottom) {
            Text(
                text = value,
                style = MaterialTheme.typography.headlineMedium,
                color = valueColor,
                maxLines = 1
            )
            // A unit with no measurement behind it is the visual grammar of a
            // number, which is the one thing this screen must not fake.
            if (unit != null && healthy && !missing) {
                Spacer(Modifier.width(4.dp))
                Text(
                    text = unit,
                    style = MaterialTheme.typography.labelMedium,
                    color = scheme.onSurfaceVariant,
                    modifier = Modifier.padding(bottom = 3.dp)
                )
            }
        }

        Spacer(Modifier.weight(1f))

        val footer = when {
            !healthy -> stringResource(R.string.channel_down)
            missing -> stringResource(R.string.reading_missing_hint)
            else -> caption
        }
        if (footer != null) {
            Text(
                text = footer,
                style = MaterialTheme.typography.bodySmall,
                color = if (healthy) scheme.onSurfaceVariant else faultInk,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis
            )
        }
    }
}

/**
 * Which of the node's four channels answered, in four words.
 *
 * This is about the instrument, not about the fire, so it stays neutral even
 * when a channel is down: a missing sensor is an absence and borrowing an alarm
 * hue for it would spend colour the alarm still needs.
 */
@Composable
fun ChannelHealthRow(ok: ChannelHealth, modifier: Modifier = Modifier) {
    Row(
        modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(10.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        ChannelHealthChip(stringResource(R.string.health_ds), ok.ds, Modifier.weight(1f))
        ChannelHealthChip(stringResource(R.string.health_mlx), ok.mlx, Modifier.weight(1f))
        ChannelHealthChip(stringResource(R.string.health_mq2), ok.mq2, Modifier.weight(1f))
        ChannelHealthChip(stringResource(R.string.health_flame), ok.flame, Modifier.weight(1f))
    }
}

@Composable
private fun ChannelHealthChip(label: String, up: Boolean, modifier: Modifier = Modifier) {
    val faultInk = AlarmLevel.OFFLINE.tone().ink
    Row(
        modifier,
        horizontalArrangement = Arrangement.spacedBy(6.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        // Filled against hollow, so up and down differ in form and not only in
        // colour.
        Box(
            Modifier
                .size(7.dp)
                .then(
                    if (up) {
                        Modifier.background(NormalSignal.copy(alpha = 0.75f), CircleShape)
                    } else {
                        Modifier.border(1.dp, faultInk, CircleShape)
                    }
                )
        )
        Text(
            text = label,
            style = MaterialTheme.typography.labelMedium,
            color = if (up) MaterialTheme.colorScheme.onSurfaceVariant else faultInk,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis
        )
    }
}


/**
 * Which channel raised this, shown as the two channels themselves.
 *
 * The interesting fact is not only which one fired but that there are two and
 * they are independent, so both are always drawn and the one that did not
 * contribute stays visible as an unlit outline. A single text label saying
 * "camera" would hide that a second channel existed and disagreed.
 */
@Composable
fun EvidenceChip(
    visionContributed: Boolean,
    sensorsContributed: Boolean,
    level: AlarmLevel,
    modifier: Modifier = Modifier
) {
    val tone = level.tone()
    Row(
        modifier,
        horizontalArrangement = Arrangement.spacedBy(6.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        EvidenceBadge(
            icon = Icons.Filled.Videocam,
            label = stringResource(R.string.evidence_camera),
            active = visionContributed,
            signal = tone.signal,
            ink = tone.ink
        )
        EvidenceBadge(
            icon = Icons.Filled.Sensors,
            label = stringResource(R.string.evidence_sensors),
            active = sensorsContributed,
            signal = tone.signal,
            ink = tone.ink
        )
    }
}

@Composable
private fun EvidenceBadge(
    icon: ImageVector,
    label: String,
    active: Boolean,
    signal: Color,
    ink: Color
) {
    val scheme = MaterialTheme.colorScheme
    val content = if (active) ink else scheme.onSurfaceVariant
    Row(
        Modifier
            .clip(CircleShape)
            .background(if (active) signal.copy(alpha = 0.16f) else Color.Transparent)
            .then(
                if (active) Modifier
                else Modifier.border(1.dp, scheme.outline.copy(alpha = 0.5f), CircleShape)
            )
            .padding(horizontal = 10.dp, vertical = 5.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Icon(icon, null, tint = content, modifier = Modifier.size(13.dp))
        Spacer(Modifier.width(5.dp))
        Text(
            label,
            style = MaterialTheme.typography.labelSmall,
            color = content,
            maxLines = 1
        )
    }
}

/**
 * One glyph per channel, defined once.
 *
 * The tiles on the status screen and the strip on the live screen both read from
 * here. If the gas channel were a different glyph in the two places, the reader
 * would have to learn the instrument twice.
 */
object SensorIcons {
    val Air: ImageVector = Icons.Filled.Thermostat
    val Surface: ImageVector = Icons.Filled.Whatshot
    val Gas: ImageVector = Icons.Filled.Air
    val Infrared: ImageVector = Icons.Filled.LocalFireDepartment
}

/**
 * The four channels in one line, for a screen whose subject is the picture.
 *
 * Same values and the same absence rule as the tiles, at a size that does not
 * compete with the video above it. A channel that sent nothing shows a dash
 * here too, never a zero.
 */
@Composable
fun SensorStrip(
    readings: List<Triple<ImageVector, String, Boolean>>,
    modifier: Modifier = Modifier
) {
    Row(
        modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        readings.forEach { (icon, text, healthy) ->
            val ink = if (healthy) {
                MaterialTheme.colorScheme.onSurface
            } else {
                AlarmLevel.OFFLINE.tone().ink
            }
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(
                    imageVector = icon,
                    contentDescription = null,
                    tint = ink.copy(alpha = 0.75f),
                    modifier = Modifier.size(15.dp)
                )
                Spacer(Modifier.width(5.dp))
                Text(
                    text = text,
                    style = MaterialTheme.typography.labelLarge,
                    color = ink,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
            }
        }
    }
}
