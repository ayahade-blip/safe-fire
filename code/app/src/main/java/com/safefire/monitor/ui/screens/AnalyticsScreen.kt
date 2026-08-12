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
import androidx.compose.material.icons.filled.QueryStats
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.safefire.monitor.R
import com.safefire.monitor.data.AlarmLevel
import com.safefire.monitor.data.FireEvent
import com.safefire.monitor.data.SensorSample
import com.safefire.monitor.data.Sensitivity
import com.safefire.monitor.data.SystemState
import com.safefire.monitor.ui.components.ChannelChart
import com.safefire.monitor.ui.components.EmptyState
import com.safefire.monitor.ui.components.Panel
import com.safefire.monitor.ui.components.Pill
import com.safefire.monitor.ui.components.SectionLabel
import com.safefire.monitor.ui.components.StatRow
import com.safefire.monitor.ui.theme.AlertOrange
import com.safefire.monitor.ui.theme.CalmGreen
import com.safefire.monitor.ui.theme.ConfirmRed
import com.safefire.monitor.ui.theme.WatchAmber
import com.safefire.monitor.ui.tint
import com.safefire.monitor.ui.orNoReading

@Composable
fun AnalyticsScreen(
    state: SystemState,
    events: List<FireEvent>,
    history: List<SensorSample>,
    sensitivity: Sensitivity,
    contentPadding: PaddingValues
) {
    val week = remember(events) {
        val cutoff = System.currentTimeMillis() - 7L * 24 * 3_600_000
        events.filter { it.timestamp >= cutoff }
    }
    val byTrigger = remember(week) {
        Triple(
            week.count { it.rationale.visionContributed && !it.rationale.sensorsContributed },
            week.count { !it.rationale.visionContributed && it.rationale.sensorsContributed },
            week.count { it.rationale.visionContributed && it.rationale.sensorsContributed }
        )
    }

    Column(
        Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(contentPadding)
            .padding(horizontal = 16.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp)
    ) {
        Spacer(Modifier.height(4.dp))

        SectionLabel(stringResource(R.string.alarms_7d))
        Panel {
            Column(Modifier.padding(18.dp)) {
                Row(verticalAlignment = Alignment.Bottom) {
                    Text(
                        "${week.size}",
                        style = MaterialTheme.typography.displayLarge,
                        color = MaterialTheme.colorScheme.onSurface
                    )
                    Text(
                        stringResource(R.string.alarms_7d).lowercase(),
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(start = 10.dp, bottom = 12.dp)
                    )
                }

                Spacer(Modifier.height(6.dp))
                LevelBars(week)
            }
        }

        SectionLabel(stringResource(R.string.by_trigger))
        Panel {
            Column(Modifier.padding(18.dp)) {
                if (week.isEmpty()) {
                    Text(
                        stringResource(R.string.no_data_yet),
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                } else {
                    TriggerRow(
                        stringResource(R.string.trigger_both),
                        byTrigger.third, week.size, ConfirmRed
                    )
                    TriggerRow(
                        stringResource(R.string.trigger_vision),
                        byTrigger.first, week.size, AlertOrange
                    )
                    TriggerRow(
                        stringResource(R.string.trigger_sensor),
                        byTrigger.second, week.size, WatchAmber
                    )
                }
            }
        }

        SectionLabel(stringResource(R.string.reliability))
        Panel {
            Column(Modifier.padding(18.dp)) {
                Row(
                    Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        stringResource(R.string.op_declared),
                        style = MaterialTheme.typography.titleMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Pill(
                        text = "conf %.2f".format(sensitivity.conf),
                        color = MaterialTheme.colorScheme.primary
                    )
                }
                Spacer(Modifier.height(10.dp))
                StatRow(stringResource(R.string.op_recall), "%.1f %%".format(sensitivity.recall * 100), CalmGreen)
                StatRow(stringResource(R.string.op_fpr_hard), "%.1f %%".format(sensitivity.fprHard))
                StatRow(stringResource(R.string.op_fpr_novel), "%.1f %%".format(sensitivity.fprNovel))
                StatRow(stringResource(R.string.op_fpr_open), "%.1f %%".format(sensitivity.fprOpen))
            }
        }

        SectionLabel(stringResource(R.string.sensor_trends))
        if (history.size < 2) {
            Panel {
                Box(Modifier.fillMaxWidth()) {
                    EmptyState(
                        icon = Icons.Filled.QueryStats,
                        title = stringResource(R.string.no_data_yet),
                        body = stringResource(R.string.no_data_desc)
                    )
                }
            }
        } else {
            ChannelChart(
                title = stringResource(R.string.surface_temp),
                value = state.sensors.surfaceC.orNoReading("%.1f"),
                unit = "°C",
                values = history.mapNotNull { it.surfaceC },
                color = MaterialTheme.colorScheme.primary
            )
            ChannelChart(
                title = stringResource(R.string.gas),
                value = state.sensors.gasRisePct.orNoReading("%.1f", " %"),
                unit = " %",
                values = history.mapNotNull { it.gasRisePct },
                color = MaterialTheme.colorScheme.primary
            )
            ChannelChart(
                title = stringResource(R.string.flame_ir),
                value = state.sensors.flameIr.orNoReading("%.2f"),
                unit = "",
                values = history.mapNotNull { it.flameIr },
                color = MaterialTheme.colorScheme.primary
            )
        }

        SectionLabel(stringResource(R.string.edge_perf))
        Panel {
            Column(Modifier.padding(18.dp)) {
                StatRow("Throughput", "%.1f FPS".format(state.fps))
                StatRow(stringResource(R.string.inference_time), "%.1f ms".format(state.inferenceMs))
                StatRow(stringResource(R.string.model_info), "YOLO26n · TensorRT FP16")
            }
        }

        Spacer(Modifier.height(28.dp))
    }
}

@Composable
private fun LevelBars(events: List<FireEvent>) {
    if (events.isEmpty()) {
        Text(
            stringResource(R.string.no_data_yet),
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        return
    }
    val order = listOf(AlarmLevel.CONFIRMED, AlarmLevel.ALERT, AlarmLevel.WATCH)
    val counts = order.map { lv -> lv to events.count { it.level == lv } }
    val total = counts.sumOf { it.second }.coerceAtLeast(1)

    Row(
        Modifier
            .fillMaxWidth()
            .height(12.dp)
            .clip(CircleShape)
            .background(MaterialTheme.colorScheme.surfaceVariant)
    ) {
        counts.forEach { (lv, n) ->
            if (n > 0) {
                Box(
                    Modifier
                        .fillMaxWidth(n.toFloat() / total)
                        .fillMaxSize()
                        .background(lv.tint())
                )
            }
        }
    }
    Spacer(Modifier.height(12.dp))
    counts.forEach { (lv, n) ->
        Row(
            Modifier
                .fillMaxWidth()
                .padding(vertical = 3.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(
                    Modifier
                        .size(8.dp)
                        .background(lv.tint(), CircleShape)
                )
                Text(
                    lv.name.lowercase().replaceFirstChar { it.uppercase() },
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(start = 8.dp)
                )
            }
            Text(
                "$n",
                style = MaterialTheme.typography.titleMedium,
                color = MaterialTheme.colorScheme.onSurface
            )
        }
    }
}

@Composable
private fun TriggerRow(label: String, count: Int, total: Int, color: Color) {
    val frac = if (total == 0) 0f else count.toFloat() / total
    Column(Modifier.padding(vertical = 7.dp)) {
        Row(
            Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Text(
                label,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            Text(
                "$count",
                style = MaterialTheme.typography.titleMedium,
                color = color
            )
        }
        Spacer(Modifier.height(6.dp))
        Box(
            Modifier
                .fillMaxWidth()
                .height(6.dp)
                .clip(RoundedCornerShape(3.dp))
                .background(MaterialTheme.colorScheme.surfaceVariant)
        ) {
            Box(
                Modifier
                    .fillMaxWidth(frac)
                    .fillMaxSize()
                    .background(color, RoundedCornerShape(3.dp))
            )
        }
    }
}
