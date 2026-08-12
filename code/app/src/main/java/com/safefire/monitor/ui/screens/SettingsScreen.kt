package com.safefire.monitor.ui.screens

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
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.BrightnessAuto
import androidx.compose.material.icons.filled.DarkMode
import androidx.compose.material.icons.filled.LightMode
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.safefire.monitor.R
import com.safefire.monitor.data.AlarmLevel
import com.safefire.monitor.data.AppPrefs
import com.safefire.monitor.data.Sensitivity
import com.safefire.monitor.data.ThemeMode
import com.safefire.monitor.data.Thresholds
import com.safefire.monitor.ui.components.Panel
import com.safefire.monitor.ui.components.Pill
import com.safefire.monitor.ui.components.SectionLabel
import com.safefire.monitor.ui.components.StatRow
import com.safefire.monitor.ui.theme.CalmGreen
import com.safefire.monitor.ui.theme.WatchAmber
import com.safefire.monitor.ui.tint
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(
    prefs: AppPrefs?,
    sensitivity: Sensitivity,
    isDemo: Boolean,
    onSimulate: (AlarmLevel) -> Unit,
    contentPadding: PaddingValues
) {
    val scope = rememberCoroutineScope()
    val themeMode by (prefs?.themeMode ?: flowOf(ThemeMode.SYSTEM))
        .collectAsStateWithLifecycle(ThemeMode.SYSTEM)
    val hapticsOn by (prefs?.haptics ?: flowOf(true))
        .collectAsStateWithLifecycle(true)
    val thresholds by (prefs?.thresholds ?: flowOf(Thresholds()))
        .collectAsStateWithLifecycle(Thresholds())

    Column(
        Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(contentPadding)
            .padding(horizontal = 16.dp)
    ) {
        Spacer(Modifier.height(4.dp))

        SectionLabel(stringResource(R.string.appearance))
        Panel {
            Column(Modifier.padding(18.dp)) {
                SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
                    val opts = listOf(
                        ThemeMode.SYSTEM to R.string.theme_system,
                        ThemeMode.LIGHT to R.string.theme_light,
                        ThemeMode.DARK to R.string.theme_dark
                    )
                    opts.forEachIndexed { i, (m, label) ->
                        SegmentedButton(
                            selected = themeMode == m,
                            onClick = { scope.launch { prefs?.setTheme(m) } },
                            shape = SegmentedButtonDefaults.itemShape(i, opts.size),
                            icon = {
                                Icon(
                                    when (m) {
                                        ThemeMode.SYSTEM -> Icons.Filled.BrightnessAuto
                                        ThemeMode.LIGHT -> Icons.Filled.LightMode
                                        ThemeMode.DARK -> Icons.Filled.DarkMode
                                    },
                                    null, modifier = Modifier.size(16.dp)
                                )
                            }
                        ) { Text(stringResource(label)) }
                    }
                }
                Spacer(Modifier.height(6.dp))
                ToggleRow(stringResource(R.string.haptics), hapticsOn) { on ->
                    scope.launch { prefs?.setHaptics(on) }
                }
            }
        }

        Spacer(Modifier.height(16.dp))

        SectionLabel(stringResource(R.string.sensitivity))
        Panel {
            Column(Modifier.padding(18.dp)) {
                Text(
                    stringResource(R.string.sens_validated),
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                Spacer(Modifier.height(14.dp))

                SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
                    val opts = listOf(
                        Sensitivity.SENSITIVE to R.string.sens_sensitive,
                        Sensitivity.STANDARD to R.string.sens_standard,
                        Sensitivity.QUIET to R.string.sens_quiet
                    )
                    opts.forEachIndexed { i, (s, label) ->
                        SegmentedButton(
                            selected = sensitivity == s,
                            onClick = { scope.launch { prefs?.setSensitivity(s) } },
                            shape = SegmentedButtonDefaults.itemShape(i, opts.size)
                        ) { Text(stringResource(label)) }
                    }
                }

                Spacer(Modifier.height(14.dp))
                StatRow(stringResource(R.string.op_threshold), "%.2f".format(sensitivity.conf))
                StatRow(
                    stringResource(R.string.op_recall),
                    "%.1f %%".format(sensitivity.recall * 100), CalmGreen
                )
                StatRow(stringResource(R.string.op_fpr_hard), "%.1f %%".format(sensitivity.fprHard))
                StatRow(stringResource(R.string.op_fpr_novel), "%.1f %%".format(sensitivity.fprNovel))
                StatRow(stringResource(R.string.op_fpr_open), "%.1f %%".format(sensitivity.fprOpen))

                if (sensitivity == Sensitivity.STANDARD) {
                    Spacer(Modifier.height(12.dp))
                    Pill(
                        text = stringResource(R.string.op_declared),
                        color = MaterialTheme.colorScheme.primary
                    )
                }
            }
        }

        Spacer(Modifier.height(16.dp))

        SectionLabel(stringResource(R.string.notifications))
        Panel {
            Column(Modifier.padding(horizontal = 18.dp, vertical = 8.dp)) {
                ToggleRow(stringResource(R.string.notify_confirmed), thresholds.notifyConfirmed) {
                    scope.launch { prefs?.setThresholds(thresholds.copy(notifyConfirmed = it)) }
                }
                ToggleRow(stringResource(R.string.notify_alert), thresholds.notifyAlert) {
                    scope.launch { prefs?.setThresholds(thresholds.copy(notifyAlert = it)) }
                }
                ToggleRow(stringResource(R.string.notify_watch), thresholds.notifyWatch) {
                    scope.launch { prefs?.setThresholds(thresholds.copy(notifyWatch = it)) }
                }
            }
        }

        if (isDemo) {
            Spacer(Modifier.height(16.dp))
            SectionLabel(stringResource(R.string.data_source))
            Panel(accent = WatchAmber) {
                Column(Modifier.padding(18.dp)) {
                    Pill(text = stringResource(R.string.demo_mode), color = WatchAmber)
                    Text(
                        stringResource(R.string.demo_mode_desc),
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(top = 10.dp)
                    )
                    Spacer(Modifier.height(12.dp))
                    Text(
                        stringResource(R.string.simulate),
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Row(
                        Modifier.padding(top = 6.dp),
                        horizontalArrangement = Arrangement.spacedBy(4.dp)
                    ) {
                        listOf(
                            AlarmLevel.NORMAL to "Normal",
                            AlarmLevel.WATCH to "Watch",
                            AlarmLevel.ALERT to "Alert",
                            AlarmLevel.CONFIRMED to "Confirmed"
                        ).forEach { (level, label) ->
                            Box {
                                TextButton(
                                    onClick = { onSimulate(level) },
                                    contentPadding = PaddingValues(horizontal = 6.dp)
                                ) { Pill(text = label, color = level.tint()) }
                            }
                        }
                    }
                }
            }
        }

        Spacer(Modifier.height(16.dp))
        SectionLabel(stringResource(R.string.about))
        Panel {
            Column(Modifier.padding(18.dp)) {
                Text(
                    stringResource(R.string.about_desc),
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                Spacer(Modifier.height(10.dp))
                StatRow(stringResource(R.string.model_info), "YOLO26n · 2.51 M params")
                StatRow(stringResource(R.string.edge_device), "Jetson Nano · TensorRT FP16")
                StatRow("Version", "1.0")
            }
        }

        Spacer(Modifier.height(30.dp))
    }
}

@Composable
private fun ToggleRow(label: String, checked: Boolean, onChange: (Boolean) -> Unit) {
    Row(
        Modifier
            .fillMaxWidth()
            .padding(vertical = 6.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(
            label,
            style = MaterialTheme.typography.bodyLarge,
            color = MaterialTheme.colorScheme.onSurface
        )
        Switch(checked = checked, onCheckedChange = onChange)
    }
}
