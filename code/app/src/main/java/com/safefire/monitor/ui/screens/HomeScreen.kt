package com.safefire.monitor.ui.screens

import android.content.Context
import android.os.Build
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CloudOff
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Schedule
import androidx.compose.material.icons.filled.SensorsOff
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.safefire.monitor.R
import com.safefire.monitor.data.AlarmLevel
import com.safefire.monitor.data.LinkState
import com.safefire.monitor.data.SensorSample
import com.safefire.monitor.data.SystemState
import com.safefire.monitor.data.Thresholds
import com.safefire.monitor.ui.NO_READING
import com.safefire.monitor.ui.asClock
import com.safefire.monitor.ui.components.FrameView
import com.safefire.monitor.ui.components.AlertHeader
import com.safefire.monitor.ui.components.Panel
import com.safefire.monitor.ui.components.SectionLabel
import com.safefire.monitor.ui.components.SensorTile
import com.safefire.monitor.ui.orNoReading
import com.safefire.monitor.ui.theme.tone
import com.safefire.monitor.ui.visual
import com.safefire.monitor.ui.conclusionText
import com.safefire.monitor.data.FireEvent
import com.safefire.monitor.ui.components.SensorIcons
import com.safefire.monitor.ui.components.SensorStrip
import androidx.compose.foundation.layout.width
import com.safefire.monitor.ui.components.EvidenceChip
import com.safefire.monitor.ui.asRelative
import androidx.compose.runtime.remember
import com.safefire.monitor.ui.components.SystemShield
import com.safefire.monitor.ui.asDay

/**
 * The node's own limits, copied from nodeLevel() in safefire_node.ino.
 *
 * Thresholds carries the gas limit and nothing else, so these two live here
 * until it carries them too. They are not a second opinion about the fire: they
 * are the same numbers the firmware already decided with, because two rules
 * would let the tile and the level disagree about the same sample.
 */
private const val SURFACE_RISE_ALARM_C = 2.0f
private const val FLAME_DROP_ALARM_MV = 150

@Composable
fun StatusScreen(
    state: SystemState,
    link: LinkState = LinkState.LIVE,
    events: List<FireEvent> = emptyList(),
    ackError: String? = null,
    onOpenLive: () -> Unit,
    onAcknowledge: () -> Unit,
    contentPadding: PaddingValues,
    thresholds: Thresholds = Thresholds()
) {
    // Only the live sample is read here, and only to say whether the node is
    // still talking. Which channel is driving what is now asked of the event,
    // inside EventReadings, because that is the sample this screen displays.
    val s = state.sensors
    val window = remember(events) { summarise24h(events) }
    val lastEvent = events.firstOrNull()

    LazyColumn(
        contentPadding = contentPadding,
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
    ) {
        item(key = "shield") {
            SystemShield(
                // Fill is now, and three different things can make now unknown.
                //
                // A level nobody has refreshed is not a verdict about the house,
                // so a frozen document draws as OFFLINE rather than keeping the
                // colour it stopped on.
                //
                // A silent node draws as OFFLINE too. Measured with the node
                // unplugged: the edge publishes NORMAL, correctly, because the
                // camera is watching and the ladder lets vision alarm alone. But
                // a green shield is read across a room as "all four channels
                // agree", and half the sensing was absent. Green has to mean
                // everything is watching, or it means nothing.
                // Order matters, and this order is the safety argument.
                // A frozen document is never a verdict. A live alarm is never
                // masked by a missing node, because the camera alarms alone by
                // design and a red shield hidden behind a grey one is the worst
                // failure this screen could have. Only a quiet, live, one-eyed
                // system draws grey.
                level = when {
                    state.stale -> AlarmLevel.OFFLINE
                    state.level.isAlarming -> state.level
                    !state.sensors.present -> AlarmLevel.OFFLINE
                    else -> state.level
                },
                worst24h = window.worst,
                alerts24h = window.count,
                since = state.since,
                // From the raw state, not the drawn one, so an alarm can still
                // be answered while the link is unreliable.
                unanswered = state.level.isAlarming && !state.acknowledged,
                onAcknowledge = onAcknowledge,
                modifier = Modifier.padding(horizontal = 20.dp, vertical = 22.dp)
            )
        }

        item(key = "notices") {
            Column(
                Modifier.padding(horizontal = 16.dp, vertical = 10.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                LinkNotice(link)
                // A press that never reached the cloud is the one failure this
                // screen must not hide, because the reader believes the alarm
                // has been answered everywhere.
                if (ackError != null) {
                    Notice(
                        icon = Icons.Filled.CloudOff,
                        title = stringResource(R.string.ack_failed),
                        body = stringResource(R.string.ack_failed_body),
                        ink = AlarmLevel.ALERT.tone().ink
                    )
                }
                // The node being silent means nothing is watching right now,
                // which outranks anything else this screen has to say.
                SampleNotice(s)
            }
        }

        item(key = "lastAlert") {
            LastAlertSection(
                event = lastEvent,
                thresholds = thresholds,
                onOpenLive = onOpenLive,
                modifier = Modifier.padding(horizontal = 16.dp)
            )
        }

        item(key = "tail") { Spacer(Modifier.height(28.dp)) }
    }
}

/** How the last day went, in the two numbers the shield needs. */
private data class Window24h(val worst: AlarmLevel?, val count: Int)

/**
 * Summarise the window.
 *
 * Every recorded event is WATCH or above, since nothing below that is written,
 * so the count is simply how many landed inside the window and the worst is the
 * highest level among them. Null means the day was quiet, which the shield draws
 * as a plain outline rather than as a colour.
 */
private fun summarise24h(events: List<FireEvent>): Window24h {
    val cutoff = System.currentTimeMillis() - 24L * 60L * 60L * 1000L
    val recent = events.filter { it.timestamp >= cutoff }
    return Window24h(
        worst = recent.maxByOrNull { it.level.rank }?.level,
        count = recent.size
    )
}

/**
 * Everything about the alert that was actually raised.
 *
 * The frame and the readings both come from the event, never from the live
 * state. Showing what the room is doing now under a heading about what happened
 * then is the quiet kind of wrong that a reader has no way to detect.
 */
@Composable
private fun LastAlertSection(
    event: FireEvent?,
    thresholds: Thresholds,
    onOpenLive: () -> Unit,
    modifier: Modifier = Modifier
) {
    val ctx = LocalContext.current

    Column(modifier) {
        SectionLabel(stringResource(R.string.last_alert))

        if (event == null) {
            Panel {
                Column(Modifier.padding(20.dp)) {
                    Text(
                        stringResource(R.string.no_alert_yet),
                        style = MaterialTheme.typography.titleMedium,
                        color = MaterialTheme.colorScheme.onSurface
                    )
                    Spacer(Modifier.height(6.dp))
                    Text(
                        stringResource(R.string.no_alert_yet_body),
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
            return@Column
        }

        Panel {
            Column {
                // The level word and the time live here and nowhere else on this
                // screen. They used to appear twice, once in a full width band
                // and again three lines below it.
                AlertHeader(level = event.level, timestamp = event.timestamp)

                Column(Modifier.padding(18.dp)) {
                    Text(
                        event.timestamp.asDay() + " · " + event.timestamp.asRelative(ctx),
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Spacer(Modifier.height(10.dp))
                    Text(
                        event.level.conclusionText(),
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurface
                    )

                    Spacer(Modifier.height(16.dp))
                    Text(
                        stringResource(R.string.based_on),
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Spacer(Modifier.height(8.dp))
                    EvidenceChip(
                        visionContributed = event.rationale.visionContributed,
                        sensorsContributed = event.rationale.sensorsContributed,
                        level = event.level
                    )
                }
            }
        }

        Spacer(Modifier.height(18.dp))
        SectionLabel(stringResource(R.string.alert_snapshot))
        // The event's own frame. Tapping it goes to the live view, because the
        // question a person asks after seeing what happened is what is happening.
        Box(Modifier.clickable { onOpenLive() }) {
            FrameView(
                frame = event.frame,
                detections = event.detections,
                timestamp = event.timestamp,
                frameB64 = event.frameB64
            )
        }

        Spacer(Modifier.height(18.dp))
        SectionLabel(stringResource(R.string.readings_at_alert))
        EventReadings(
            sample = event.sensors,
            level = event.level,
            sensorsContributed = event.rationale.sensorsContributed,
            thresholds = thresholds
        )
    }
}

/**
 * The four channels as they read when the alert was raised.
 *
 * Health comes from the event's own flags, and staleness is not asked about: a
 * snapshot cannot be out of date with respect to itself.
 */
@Composable
private fun EventReadings(
    sample: SensorSample,
    level: AlarmLevel,
    sensorsContributed: Boolean,
    thresholds: Thresholds
) {
    val driving = contributingChannels(
        s = sample,
        level = level,
        sensorsContributed = sensorsContributed,
        t = thresholds
    )
    val celsius = stringResource(R.string.unit_celsius)
    val percent = stringResource(R.string.unit_percent)

    val airValue = sample.ambientC.orNoReading("%.1f")
    val surfaceValue = sample.surfaceC.orNoReading("%.1f")
    val gasValue = sample.gasRisePct.orNoReading("%+.0f")
    val irValue = sample.flameIr.orNoReading("%.2f")

    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            SensorTile(
                label = stringResource(R.string.tile_air),
                icon = SensorIcons.Air,
                value = airValue,
                unit = celsius.takeIf { airValue != NO_READING },
                contributing = driving.air,
                level = level,
                healthy = sample.ok.ds,
                modifier = Modifier.weight(1f)
            )
            SensorTile(
                label = stringResource(R.string.tile_surface),
                icon = SensorIcons.Surface,
                value = surfaceValue,
                unit = celsius.takeIf { surfaceValue != NO_READING },
                caption = sample.surfaceRiseC?.let {
                    stringResource(R.string.tile_surface_cap, "%+.1f ".format(it) + celsius)
                },
                contributing = driving.surface,
                level = level,
                healthy = sample.ok.mlx,
                modifier = Modifier.weight(1f)
            )
        }
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            SensorTile(
                label = stringResource(R.string.tile_gas),
                icon = SensorIcons.Gas,
                value = gasValue,
                unit = percent.takeIf { gasValue != NO_READING },
                caption = sample.gasRatio?.let {
                    stringResource(R.string.tile_gas_cap, "%.3f".format(it))
                },
                contributing = driving.gas,
                level = level,
                healthy = sample.ok.mq2,
                modifier = Modifier.weight(1f)
            )
            SensorTile(
                label = stringResource(R.string.tile_infrared),
                icon = SensorIcons.Infrared,
                value = irValue,
                unit = null,
                caption = sample.flameDropMv?.let {
                    stringResource(R.string.tile_infrared_cap, it.toString())
                },
                contributing = driving.flame,
                level = level,
                healthy = sample.ok.flame,
                modifier = Modifier.weight(1f)
            )
        }
    }
}

@Composable
internal fun SensorSample.strip(): List<Triple<ImageVector, String, Boolean>> {
    val celsius = stringResource(R.string.unit_celsius)
    return listOf(
        Triple(SensorIcons.Air, ambientC.orNoReading("%.1f", celsius), ok.ds),
        Triple(SensorIcons.Surface, surfaceC.orNoReading("%.1f", celsius), ok.mlx),
        Triple(SensorIcons.Gas, gasRisePct.orNoReading("%.1f", " %"), ok.mq2),
        Triple(SensorIcons.Infrared, flameIr.orNoReading("%.2f"), ok.flame)
    )
}

/** Four booleans, one per tile, so the call sites read as plainly as the rule. */
private data class Contributing(
    /**
     * The DS18B20 is not in the node's decision at all, so air never drives the
     * level. It stays here as a field rather than as an omission, because a
     * reader of this screen should be able to see that it was considered.
     */
    val air: Boolean = false,
    val surface: Boolean = false,
    val gas: Boolean = false,
    val flame: Boolean = false
)

/**
 * Which sensor channels are pushing the level up right now.
 *
 * This mirrors nodeLevel() in safefire_node.ino one to one: gas when Rs/R0 has
 * fallen far enough, surface when it has risen above its own baseline, infrared
 * when the photodiode has dropped. Nothing lights up unless the fusion already
 * agreed the sensor side contributed, so a camera-only ALERT leaves all four
 * tiles quiet instead of painting the whole grid for a fire the node never saw.
 *
 * A stale or absent sample drives nothing. It is still shown, but a reading that
 * is too old to be current is also too old to justify a colour.
 */
private fun contributingChannels(
    s: SensorSample,
    level: AlarmLevel,
    sensorsContributed: Boolean,
    t: Thresholds
): Contributing {
    val trusted = s.present && !s.stale && sensorsContributed &&
            level != AlarmLevel.NORMAL && level != AlarmLevel.OFFLINE
    if (!trusted) return Contributing()

    return Contributing(
        surface = s.ok.mlx && (s.surfaceRiseC ?: 0f) > SURFACE_RISE_ALARM_C,
        gas = s.ok.mq2 && (s.gasRisePct ?: 0f) > t.gasRisePctAlarm,
        flame = s.ok.flame && (s.flameDropMv ?: 0) > FLAME_DROP_ALARM_MV
    )
}

/**
 * Silent and stale are different failures and are worded differently on purpose.
 * A twelve second old temperature is still information; the same number printed
 * as if it were current is not.
 */
@Composable
private fun SampleNotice(s: SensorSample) {
    when {
        !s.present -> Notice(
            icon = Icons.Filled.SensorsOff,
            title = stringResource(R.string.node_silent),
            body = stringResource(R.string.node_silent_hint),
            ink = AlarmLevel.OFFLINE.tone().ink
        )
        s.stale -> Notice(
            icon = Icons.Filled.Schedule,
            title = stringResource(R.string.sensors_stale),
            body = stringResource(
                R.string.sensors_stale_age,
                ((s.sampleAgeMs ?: 0L) / 1000L).toInt()
            ),
            ink = AlarmLevel.WATCH.tone().ink
        )
    }
}

/** The phone to cloud hop, which fails separately from the node to Jetson one. */
@Composable
private fun LinkNotice(link: LinkState) {
    val label: Int? = when (link) {
        LinkState.CONNECTING -> R.string.link_connecting
        // Deliberately silent. Saved data is still the last true reading,
        // and a banner for it added a line of chrome to every quiet moment.
        LinkState.CACHED -> null
        LinkState.OFFLINE -> R.string.link_offline
        LinkState.LIVE -> null
    }
    if (label != null) {
        Notice(
            icon = Icons.Filled.CloudOff,
            title = stringResource(label),
            body = null,
            ink = AlarmLevel.OFFLINE.tone().ink
        )
    }
}

@Composable
private fun Notice(icon: ImageVector, title: String, body: String?, ink: Color) {
    Row(
        Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.Top,
        horizontalArrangement = Arrangement.spacedBy(10.dp)
    ) {
        Icon(
            icon, null,
            tint = ink,
            modifier = Modifier
                .padding(top = 2.dp)
                .size(16.dp)
        )
        Column {
            Text(
                title,
                style = MaterialTheme.typography.labelLarge,
                color = ink
            )
            if (body != null) {
                Text(
                    body,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(top = 2.dp)
                )
            }
        }
    }
}

@Composable
private fun ChannelLine(title: String, body: String, active: Boolean, color: Color) {
    Row(verticalAlignment = Alignment.Top) {
        Box(
            Modifier
                .padding(top = 5.dp, end = 12.dp)
                .size(8.dp)
                .background(
                    if (active) color else MaterialTheme.colorScheme.outline,
                    CircleShape
                )
        )
        Column {
            Text(
                title,
                style = MaterialTheme.typography.labelLarge,
                color = if (active) color else MaterialTheme.colorScheme.onSurfaceVariant
            )
            Text(
                body,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.86f),
                modifier = Modifier.padding(top = 2.dp)
            )
        }
    }
}

@Composable
fun AlarmTakeover(
    state: SystemState,
    haptics: Boolean,
    onAcknowledge: () -> Unit,
    onDetails: () -> Unit
) {
    val v = state.level.visual()
    val tone = state.level.tone()
    val ctx = LocalContext.current

    val pulse = rememberInfiniteTransition(label = "alarm")
    val glow by pulse.animateFloat(
        0.10f, 0.30f,
        infiniteRepeatable(tween(700), RepeatMode.Reverse), label = "glow"
    )
    val beat by pulse.animateFloat(
        0.94f, 1.06f,
        infiniteRepeatable(tween(700), RepeatMode.Reverse), label = "beat"
    )

    DisposableEffect(haptics) {
        val vib = ctx.vibrator()
        if (haptics && vib != null && vib.hasVibrator()) {
            val pattern = longArrayOf(0, 450, 250, 450, 250, 700, 900)
            runCatching {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    vib.vibrate(VibrationEffect.createWaveform(pattern, 0))
                } else {
                    @Suppress("DEPRECATION")
                    vib.vibrate(pattern, 0)
                }
            }
        }
        onDispose { runCatching { vib?.cancel() } }
    }

    Box(
        Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
            .background(
                Brush.verticalGradient(
                    listOf(tone.signal.copy(alpha = glow), Color.Transparent)
                )
            )
    ) {
        Column(
            Modifier
                .fillMaxSize()
                .padding(horizontal = 24.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center
        ) {
            Box(
                Modifier
                    .scale(beat)
                    .size(112.dp)
                    .background(tone.signal.copy(alpha = 0.16f), CircleShape),
                contentAlignment = Alignment.Center
            ) {
                Icon(v.icon, null, tint = tone.ink, modifier = Modifier.size(60.dp))
            }

            Text(
                v.title,
                style = MaterialTheme.typography.displayMedium,
                color = tone.ink,
                textAlign = TextAlign.Center,
                modifier = Modifier.padding(top = 22.dp)
            )
            Text(
                v.description,
                style = MaterialTheme.typography.bodyLarge,
                color = MaterialTheme.colorScheme.onBackground.copy(alpha = 0.82f),
                textAlign = TextAlign.Center,
                modifier = Modifier.padding(top = 10.dp)
            )
            Text(
                state.since.asClock(),
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(top = 6.dp)
            )

            Spacer(Modifier.height(24.dp))

            FrameView(
                frame = state.frame,
                detections = state.detections,
                timestamp = state.since,
                showChrome = false,
                frameB64 = state.frameB64
            )

            Spacer(Modifier.height(30.dp))

            // White on the confirm fill measures 3.82:1 and fails AA. The band
            // text token is near black for exactly this reason.
            Button(
                onClick = onAcknowledge,
                colors = ButtonDefaults.buttonColors(
                    containerColor = tone.signal,
                    contentColor = tone.onBand
                ),
                shape = RoundedCornerShape(18.dp),
                modifier = Modifier
                    .fillMaxWidth()
                    .height(60.dp)
            ) {
                Text(
                    stringResource(R.string.acknowledge),
                    style = MaterialTheme.typography.titleLarge
                )
            }

            TextButton(
                onClick = onDetails,
                modifier = Modifier.padding(top = 6.dp)
            ) {
                Text(
                    stringResource(R.string.event_detail),
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }
}

private fun Context.vibrator(): Vibrator? = runCatching {
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
        (getSystemService(Context.VIBRATOR_MANAGER_SERVICE) as VibratorManager).defaultVibrator
    } else {
        @Suppress("DEPRECATION")
        getSystemService(Context.VIBRATOR_SERVICE) as Vibrator
    }
}.getOrNull()

