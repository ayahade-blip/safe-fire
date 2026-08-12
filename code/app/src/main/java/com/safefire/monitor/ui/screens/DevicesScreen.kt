package com.safefire.monitor.ui.screens

import androidx.compose.foundation.background
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
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CloudDone
import androidx.compose.material.icons.filled.CloudOff
import androidx.compose.material.icons.filled.CloudQueue
import androidx.compose.material.icons.filled.DeveloperBoard
import androidx.compose.material.icons.filled.Memory
import androidx.compose.material.icons.filled.PhotoCamera
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.safefire.monitor.R
import com.safefire.monitor.data.LinkState
import com.safefire.monitor.data.NodeStatus
import com.safefire.monitor.data.SystemState
import com.safefire.monitor.ui.asRelative
import com.safefire.monitor.ui.components.Panel
import com.safefire.monitor.ui.components.Pill
import com.safefire.monitor.ui.components.SectionLabel
import com.safefire.monitor.ui.theme.CalmGreen
import com.safefire.monitor.ui.theme.OfflineGrey
import com.safefire.monitor.ui.theme.WatchAmber
import kotlinx.coroutines.launch
import com.safefire.monitor.ui.orNoReading
import com.safefire.monitor.data.ChannelHealth
import com.safefire.monitor.data.StreamInfo
import com.safefire.monitor.ui.components.ChannelHealthRow
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.material.icons.filled.Videocam
import androidx.compose.material.icons.filled.VideocamOff

@Composable
fun DevicesScreen(
    state: SystemState,
    link: LinkState,
    stream: StreamInfo = StreamInfo.NONE,
    lastSync: Long,
    onRequestFrame: suspend () -> Unit,
    contentPadding: PaddingValues
) {
    val ctx = LocalContext.current
    val scope = rememberCoroutineScope()
    var requesting by remember { mutableStateOf(false) }

    Column(
        Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(contentPadding)
            .padding(horizontal = 16.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp)
    ) {
        Spacer(Modifier.height(4.dp))

        SectionLabel(stringResource(R.string.cloud_link))
        val (linkColor, linkIcon, linkDesc) = when (link) {
            LinkState.LIVE -> Triple(CalmGreen, Icons.Filled.CloudDone, R.string.link_live_desc)
            LinkState.CACHED -> Triple(WatchAmber, Icons.Filled.CloudQueue, R.string.link_cached_desc)
            LinkState.OFFLINE -> Triple(OfflineGrey, Icons.Filled.CloudOff, R.string.link_cached_desc)
            LinkState.CONNECTING -> Triple(
                MaterialTheme.colorScheme.secondary,
                Icons.Filled.CloudQueue, R.string.link_connecting_desc
            )
        }
        Panel(accent = if (link == LinkState.LIVE) null else linkColor) {
            Row(
                Modifier
                    .fillMaxWidth()
                    .padding(18.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Box(
                    Modifier
                        .size(38.dp)
                        .background(linkColor.copy(alpha = 0.14f), CircleShape),
                    contentAlignment = Alignment.Center
                ) {
                    if (link == LinkState.CONNECTING) {
                        CircularProgressIndicator(
                            strokeWidth = 2.dp, color = linkColor,
                            modifier = Modifier.size(16.dp)
                        )
                    } else {
                        Icon(linkIcon, null, tint = linkColor, modifier = Modifier.size(20.dp))
                    }
                }
                Column(Modifier.padding(start = 14.dp).weight(1f)) {
                    Text(
                        stringResource(linkDesc),
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurface
                    )
                    if (lastSync > 0) {
                        Text(
                            stringResource(R.string.last_seen) + " · " + lastSync.asRelative(ctx),
                            style = MaterialTheme.typography.labelMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                }
            }
        }

        SectionLabel(stringResource(R.string.device_health))
        state.nodes.sortedBy { if (it.id == "jetson") 0 else 1 }.forEach { node ->
            val isCamera = node.id == "jetson"
            DeviceCard(
                node = node,
                icon = if (isCamera) Icons.Filled.DeveloperBoard else Icons.Filled.Memory,
                metrics = if (isCamera) listOf(
                    Metric(stringResource(R.string.throughput), "%.1f".format(state.fps)),
                    Metric(
                        stringResource(R.string.inference_time),
                        "%.1f ms".format(state.inferenceMs)
                    ),
                    Metric(stringResource(R.string.model_info), "YOLO26n")
                ) else listOf(
                    Metric(
                        stringResource(R.string.surface_temp),
                        state.sensors.surfaceC.orNoReading("%.1f", " °C")
                    ),
                    Metric(
                        stringResource(R.string.gas),
                        state.sensors.gasRatio.orNoReading("%.3f")
                    ),
                    Metric(
                        stringResource(R.string.flame_ir),
                        state.sensors.flameIr.orNoReading("%.2f")
                    )
                ),
                lastSeenText = node.lastSeen.takeIf { it > 0 }?.asRelative(ctx),
                // Channel health belongs to the sensor node and is shown on its
                // own card, which is the whole reason it left the status screen.
                health = if (isCamera) null else state.sensors.ok,
                footer = if (isCamera) {
                    { StreamRow(stream) }
                } else {
                    null
                }
            )
        }

        OutlinedButton(
            onClick = {
                scope.launch {
                    requesting = true
                    onRequestFrame()
                    requesting = false
                }
            },
            enabled = !requesting,
            shape = RoundedCornerShape(14.dp),
            modifier = Modifier.fillMaxWidth()
        ) {
            if (requesting) {
                CircularProgressIndicator(
                    strokeWidth = 2.dp,
                    modifier = Modifier.size(15.dp),
                    color = MaterialTheme.colorScheme.primary
                )
            } else {
                Icon(Icons.Filled.PhotoCamera, null, modifier = Modifier.size(17.dp))
            }
            Text(
                stringResource(R.string.request_frame),
                modifier = Modifier.padding(start = 8.dp)
            )
        }

        Spacer(Modifier.height(28.dp))
    }
}

/**
 * Where the video is being served from, on the card for the device serving it.
 *
 * Absent fields are the normal state before the Jetson has booted, so this says
 * there is no stream rather than showing an address that was never advertised.
 */
@Composable
private fun StreamRow(stream: StreamInfo) {
    val up = stream.up && stream.addressed
    val tint = if (up) CalmGreen else OfflineGrey
    Row(verticalAlignment = Alignment.CenterVertically) {
        Icon(
            if (up) Icons.Filled.Videocam else Icons.Filled.VideocamOff,
            contentDescription = null,
            tint = tint,
            modifier = Modifier.size(18.dp)
        )
        Column(Modifier.padding(start = 12.dp)) {
            Text(
                stringResource(
                    if (up) R.string.live_source_jetson else R.string.live_no_stream
                ),
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurface
            )
            if (stream.lanIp != null && stream.port != null) {
                Text(
                    stream.lanIp + ":" + stream.port.toString(),
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }
}

/** One reading on the device card: the number first, its name underneath. */
internal data class Metric(val label: String, val value: String)

@Composable
private fun DeviceCard(
    node: NodeStatus,
    icon: ImageVector,
    metrics: List<Metric>,
    lastSeenText: String?,
    health: ChannelHealth? = null,
    footer: (@Composable () -> Unit)? = null
) {
    val color: Color = if (node.online) CalmGreen else OfflineGrey
    Panel {
        Column(Modifier.padding(18.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(
                    Modifier
                        .size(42.dp)
                        .background(color.copy(alpha = 0.14f), CircleShape),
                    contentAlignment = Alignment.Center
                ) {
                    Icon(icon, null, tint = color, modifier = Modifier.size(21.dp))
                }
                Column(
                    Modifier
                        .padding(start = 14.dp)
                        .weight(1f)
                ) {
                    Text(
                        node.name,
                        style = MaterialTheme.typography.titleLarge,
                        color = MaterialTheme.colorScheme.onSurface
                    )
                    Text(
                        node.detail,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                    if (lastSeenText != null) {
                        Text(
                            stringResource(R.string.last_seen) + " · " + lastSeenText,
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                }
                Pill(
                    text = stringResource(if (node.online) R.string.online else R.string.offline),
                    color = color
                )
            }

            if (metrics.isNotEmpty()) {
                Spacer(Modifier.height(16.dp))
                // A row of figures rather than a list of key and value lines. The
                // number is what the reader is looking for, so it is what carries
                // the weight, and three side by side read as one instrument.
                Row(
                    Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    metrics.forEach { m ->
                        Column(Modifier.weight(1f)) {
                            Text(
                                m.value,
                                style = MaterialTheme.typography.titleMedium,
                                color = MaterialTheme.colorScheme.onSurface,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis
                            )
                            Text(
                                m.label,
                                style = MaterialTheme.typography.labelSmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                maxLines = 2,
                                overflow = TextOverflow.Ellipsis
                            )
                        }
                    }
                }
            }

            if (health != null) {
                Spacer(Modifier.height(16.dp))
                Box(
                    Modifier
                        .fillMaxWidth()
                        .height(1.dp)
                        .background(MaterialTheme.colorScheme.outline.copy(alpha = 0.4f))
                )
                Spacer(Modifier.height(12.dp))
                ChannelHealthRow(ok = health)
            }

            if (footer != null) {
                Spacer(Modifier.height(14.dp))
                footer()
            }
        }
    }
}
