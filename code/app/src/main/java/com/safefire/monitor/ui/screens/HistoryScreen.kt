package com.safefire.monitor.ui.screens

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
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
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.ChevronRight
import androidx.compose.material.icons.filled.Inbox
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.safefire.monitor.R
import com.safefire.monitor.data.AlarmLevel
import com.safefire.monitor.data.FireEvent
import com.safefire.monitor.ui.DayBucket
import com.safefire.monitor.ui.asClock
import com.safefire.monitor.ui.asClockShort
import com.safefire.monitor.ui.asDay
import com.safefire.monitor.ui.components.EmptyState
import com.safefire.monitor.ui.components.FrameView
import com.safefire.monitor.ui.components.Panel
import com.safefire.monitor.ui.components.Pill
import com.safefire.monitor.ui.components.SectionLabel
import com.safefire.monitor.ui.components.StatRow
import com.safefire.monitor.ui.dayBucket
import com.safefire.monitor.ui.visual
import com.safefire.monitor.ui.orNoReading
import com.safefire.monitor.ui.conclusionText
import com.safefire.monitor.ui.sensorsText
import com.safefire.monitor.ui.visionText
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.TextButton
import androidx.compose.material.icons.filled.DeleteOutline
import com.safefire.monitor.ui.components.EvidenceChip

private enum class Filter(val labelRes: Int, val levels: Set<AlarmLevel>?) {
    ALL(R.string.filter_all, null),
    CONFIRMED(R.string.filter_confirmed, setOf(AlarmLevel.CONFIRMED)),
    ALERT(R.string.filter_alert, setOf(AlarmLevel.ALERT)),
    WATCH(R.string.filter_watch, setOf(AlarmLevel.WATCH))
}

@Composable
fun HistoryScreen(
    events: List<FireEvent>,
    onOpen: (String) -> Unit,
    onAcknowledge: (String) -> Unit,
    contentPadding: PaddingValues
) {
    var filter by remember { mutableStateOf(Filter.ALL) }
    val shown = remember(events, filter) {
        filter.levels?.let { set -> events.filter { it.level in set } } ?: events
    }

    Column(Modifier.fillMaxSize()) {
        Row(
            Modifier
                .fillMaxWidth()
                .horizontalScroll(rememberScrollState())
                .padding(
                    start = 16.dp, end = 16.dp,
                    top = contentPadding.calculateTopPadding() + 4.dp, bottom = 10.dp
                ),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Filter.entries.forEach { f ->
                FilterChip(
                    selected = filter == f,
                    onClick = { filter = f },
                    label = { Text(stringResource(f.labelRes)) },
                    shape = CircleShape,
                    colors = FilterChipDefaults.filterChipColors(
                        selectedContainerColor = MaterialTheme.colorScheme.primary.copy(alpha = 0.18f),
                        selectedLabelColor = MaterialTheme.colorScheme.primary
                    )
                )
            }
        }

        if (shown.isEmpty()) {
            EmptyState(
                icon = Icons.Filled.Inbox,
                title = stringResource(R.string.no_events),
                body = stringResource(R.string.no_events_desc)
            )
            return
        }

        val grouped = remember(shown) { shown.groupBy { it.timestamp.dayBucket() } }

        LazyColumn(
            contentPadding = PaddingValues(
                start = 16.dp, end = 16.dp,
                bottom = contentPadding.calculateBottomPadding() + 24.dp
            ),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            DayBucket.entries.forEach { bucket ->
                val list = grouped[bucket].orEmpty()
                if (list.isEmpty()) return@forEach

                item(key = "hdr_$bucket") {
                    Text(
                        text = stringResource(
                            when (bucket) {
                                DayBucket.TODAY -> R.string.today
                                DayBucket.YESTERDAY -> R.string.yesterday
                                DayBucket.EARLIER -> R.string.earlier
                            }
                        ).uppercase(),
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(top = 8.dp, bottom = 2.dp, start = 4.dp)
                    )
                }
                items(list, key = { it.id }) { e ->
                    EventCard(e, onOpen, onAcknowledge)
                }
            }
        }
    }
}

@Composable
private fun EventCard(
    event: FireEvent,
    onOpen: (String) -> Unit,
    onAcknowledge: (String) -> Unit
) {
    val v = event.level.visual()

    Panel(modifier = Modifier.clickable { onOpen(event.id) }) {
      Column(Modifier.fillMaxWidth()) {
        Row(
            Modifier
                .fillMaxWidth()
                .padding(12.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Box(
                Modifier
                    .size(74.dp, 56.dp)
                    .clip(RoundedCornerShape(12.dp))
                    .background(Color.Black)
            ) {
                Image(
                    painter = painterResource(event.frame),
                    contentDescription = null,
                    contentScale = ContentScale.Crop,
                    modifier = Modifier.fillMaxSize()
                )
                Box(
                    Modifier
                        .fillMaxSize()
                        .background(v.color.copy(alpha = 0.18f))
                )
            }

            Column(
                Modifier
                    .weight(1f)
                    .padding(start = 12.dp)
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(v.icon, null, tint = v.color, modifier = Modifier.size(15.dp))
                    Text(
                        v.title,
                        style = MaterialTheme.typography.titleMedium,
                        color = MaterialTheme.colorScheme.onSurface,
                        modifier = Modifier.padding(start = 6.dp)
                    )
                }
                Spacer(Modifier.height(3.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text(
                        event.timestamp.asClockShort(),
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    if (event.detections.isNotEmpty()) {
                        Text(
                            "· %.2f".format(event.topConfidence),
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                }
                if (event.acknowledged) {
                    Spacer(Modifier.height(5.dp))
                    Pill(
                        text = stringResource(R.string.acknowledged),
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }

            Icon(
                Icons.Filled.ChevronRight, null,
                tint = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.size(20.dp)
            )
            Spacer(Modifier.width(2.dp))
        }

        // Acknowledging used to be reachable only after opening the event, while
        // the list showed a pill that looked pressable and was not. The action
        // now sits where that label was and reads as a control.
        Row(
            Modifier
                .fillMaxWidth()
                .padding(start = 12.dp, end = 6.dp, bottom = 8.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            if (!event.acknowledged && event.level.isAlarming) {
                FilledTonalButton(
                    onClick = { onAcknowledge(event.id) },
                    shape = CircleShape,
                    contentPadding = PaddingValues(horizontal = 16.dp, vertical = 4.dp)
                ) {
                    Icon(Icons.Filled.CheckCircle, null, modifier = Modifier.size(16.dp))
                    Text(
                        stringResource(R.string.acknowledge),
                        style = MaterialTheme.typography.labelLarge,
                        modifier = Modifier.padding(start = 7.dp)
                    )
                }
            }
            Spacer(Modifier.weight(1f))
            // What raised it, on the card, so the list can be read without
            // opening anything. Deleting is not here on purpose: a destructive
            // control next to every row invites the accident it enables.
            EvidenceChip(
                visionContributed = event.rationale.visionContributed,
                sensorsContributed = event.rationale.sensorsContributed,
                level = event.level
            )
        }
      }
    }

}

/**
 * Deleting an event destroys a record on every device, so it asks first.
 *
 * The wording says what is lost rather than asking whether the reader is sure,
 * because being sure is not the thing they need to know.
 */
@Composable
private fun ConfirmDeleteDialog(onConfirm: () -> Unit, onDismiss: () -> Unit) {
    AlertDialog(
        onDismissRequest = onDismiss,
        icon = { Icon(Icons.Filled.DeleteOutline, null) },
        title = { Text(stringResource(R.string.delete_event_title)) },
        text = { Text(stringResource(R.string.delete_event_body)) },
        confirmButton = {
            TextButton(onClick = onConfirm) {
                Text(
                    stringResource(R.string.delete_event),
                    color = MaterialTheme.colorScheme.error
                )
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text(stringResource(R.string.action_cancel))
            }
        }
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun EventDetailScreen(
    event: FireEvent,
    onBack: () -> Unit,
    onAcknowledge: (String) -> Unit,
    onDelete: (String) -> Unit
) {
    var confirmingDelete by remember { mutableStateOf(false) }
    val v = event.level.visual()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.event_detail)) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(
                            Icons.AutoMirrored.Filled.ArrowBack,
                            stringResource(R.string.back)
                        )
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = Color.Transparent
                )
            )
        }
    ) { inner ->
        Column(
            Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(inner)
                .padding(horizontal = 16.dp)
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(v.icon, null, tint = v.color, modifier = Modifier.size(26.dp))
                Column(Modifier.padding(start = 10.dp)) {
                    Text(
                        v.title,
                        style = MaterialTheme.typography.headlineSmall,
                        color = MaterialTheme.colorScheme.onSurface
                    )
                    Text(
                        "${event.timestamp.asDay()} · ${event.timestamp.asClock()}",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }

            Spacer(Modifier.height(16.dp))

            FrameView(
                frame = event.frame,
                detections = event.detections,
                timestamp = event.timestamp,
                showChrome = false,
                frameB64 = event.frameB64
            )

            Spacer(Modifier.height(18.dp))
            SectionLabel(stringResource(R.string.why_triggered))

            Panel(accent = v.color) {
                Column(
                    Modifier.padding(18.dp),
                    verticalArrangement = Arrangement.spacedBy(14.dp)
                ) {
                    Evidence(
                        stringResource(R.string.vision_channel),
                        visionText(event.rationale.visionContributed, event.level),
                        event.rationale.visionContributed,
                        v.color
                    )
                    Evidence(
                        stringResource(R.string.sensor_channel),
                        event.sensors.sensorsText(),
                        event.rationale.sensorsContributed,
                        v.color
                    )
                    Box(
                        Modifier
                            .fillMaxWidth()
                            .height(1.dp)
                            .background(MaterialTheme.colorScheme.outline.copy(alpha = 0.5f))
                    )
                    Text(
                        event.level.conclusionText(),
                        style = MaterialTheme.typography.bodyLarge,
                        color = MaterialTheme.colorScheme.onSurface
                    )
                }
            }

            Spacer(Modifier.height(16.dp))
            SectionLabel(stringResource(R.string.sensor_snapshot))

            Panel {
                Column(Modifier.padding(18.dp)) {
                    StatRow(stringResource(R.string.surface_temp), event.sensors.surfaceC.orNoReading("%.1f", " °C"))
                    StatRow(stringResource(R.string.temperature), event.sensors.ambientC.orNoReading("%.1f", " °C"))
                    StatRow(stringResource(R.string.gas), event.sensors.gasRatio.orNoReading("%.3f"))
                    StatRow(stringResource(R.string.flame_ir), event.sensors.flameIr.orNoReading("%.2f"))
                    if (event.detections.isNotEmpty()) {
                        StatRow(
                            stringResource(R.string.confidence),
                            "%.2f".format(event.topConfidence),
                            valueColor = v.color
                        )
                    }
                }
            }

            Spacer(Modifier.height(18.dp))

            if (!event.acknowledged) {
                OutlinedButton(
                    onClick = { onAcknowledge(event.id) },
                    shape = CircleShape,
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Icon(Icons.Filled.CheckCircle, null, modifier = Modifier.size(18.dp))
                    Text(
                        stringResource(R.string.acknowledge),
                        modifier = Modifier.padding(start = 8.dp)
                    )
                }
                Spacer(Modifier.height(10.dp))
            }

            // Destructive, so it is the quietest control on the screen and the
            // furthest from the one the reader came here to press.
            TextButton(
                onClick = { confirmingDelete = true },
                modifier = Modifier.fillMaxWidth()
            ) {
                Icon(
                    Icons.Filled.DeleteOutline, null,
                    tint = MaterialTheme.colorScheme.error,
                    modifier = Modifier.size(18.dp)
                )
                Text(
                    stringResource(R.string.delete_event),
                    color = MaterialTheme.colorScheme.error,
                    modifier = Modifier.padding(start = 8.dp)
                )
            }

            Spacer(Modifier.height(30.dp))
        }
    }

    if (confirmingDelete) {
        ConfirmDeleteDialog(
            onConfirm = {
                confirmingDelete = false
                onDelete(event.id)
            },
            onDismiss = { confirmingDelete = false }
        )
    }
}

@Composable
private fun Evidence(title: String, body: String, active: Boolean, color: Color) {
    Row(verticalAlignment = Alignment.Top) {
        Box(
            Modifier
                .padding(top = 5.dp, end = 12.dp)
                .size(8.dp)
                .background(if (active) color else MaterialTheme.colorScheme.outline, CircleShape)
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
