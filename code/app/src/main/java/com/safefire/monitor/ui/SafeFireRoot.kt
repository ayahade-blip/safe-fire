package com.safefire.monitor.ui

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.DeveloperBoard
import androidx.compose.material.icons.filled.History
import androidx.compose.material.icons.filled.QueryStats
import androidx.compose.material.icons.filled.Shield
import androidx.compose.material.icons.filled.Videocam
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.navigation.NavDestination.Companion.hierarchy
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.safefire.monitor.R
import com.safefire.monitor.data.AlarmLevel
import com.safefire.monitor.data.AppPrefs
import com.safefire.monitor.data.SafeFireRepository
import com.safefire.monitor.data.Sensitivity
import com.safefire.monitor.ui.screens.AlarmTakeover
import com.safefire.monitor.ui.screens.AnalyticsScreen
import com.safefire.monitor.ui.screens.DevicesScreen
import com.safefire.monitor.ui.screens.EventDetailScreen
import com.safefire.monitor.ui.screens.HistoryScreen
import com.safefire.monitor.ui.screens.LiveScreen
import com.safefire.monitor.ui.screens.SettingsScreen
import com.safefire.monitor.ui.screens.StatusScreen
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.launch
import com.safefire.monitor.ui.components.SafeFireTopBar

private sealed class Dest(val route: String) {
    data object Status : Dest("status")
    data object Live : Dest("live")
    data object History : Dest("history")
    data object Analytics : Dest("analytics")
    data object Devices : Dest("devices")
    data object Settings : Dest("settings")
    data object Detail : Dest("event/{id}") {
        fun of(id: String) = "event/$id"
    }
}

private data class Tab(val dest: Dest, val labelRes: Int, val icon: ImageVector)

private val tabs = listOf(
    Tab(Dest.Status, R.string.nav_status, Icons.Filled.Shield),
    Tab(Dest.Live, R.string.nav_live, Icons.Filled.Videocam),
    Tab(Dest.History, R.string.nav_history, Icons.Filled.History),
    Tab(Dest.Analytics, R.string.nav_analytics, Icons.Filled.QueryStats),
    Tab(Dest.Devices, R.string.nav_devices, Icons.Filled.DeveloperBoard)
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SafeFireRoot(
    repository: SafeFireRepository,
    prefs: AppPrefs? = null,
    initialEventId: String? = null
) {
    val nav = rememberNavController()
    val scope = rememberCoroutineScope()

    val state by repository.state.collectAsStateWithLifecycle()
    val link by repository.link.collectAsStateWithLifecycle()
    val lastSync by repository.lastSync.collectAsStateWithLifecycle()
    val haptics by (prefs?.haptics ?: flowOf(true)).collectAsStateWithLifecycle(true)
    val sensitivity by (prefs?.sensitivity ?: flowOf(Sensitivity.DEFAULT))
        .collectAsStateWithLifecycle(Sensitivity.DEFAULT)

    var takeoverDismissed by remember { mutableStateOf(false) }
    val takeover = state.level == AlarmLevel.CONFIRMED &&
            !state.acknowledged && !takeoverDismissed
    LaunchedEffect(state.level, state.acknowledged) {
        if (state.level != AlarmLevel.CONFIRMED || state.acknowledged) {
            takeoverDismissed = false
        }
    }

    LaunchedEffect(initialEventId) {
        if (initialEventId != null && repository.eventById(initialEventId) != null) {
            nav.navigate("event/$initialEventId")
        }
    }

    if (takeover) {
        AlarmTakeover(
            state = state,
            haptics = haptics,
            onAcknowledge = { repository.acknowledge() },
            onDetails = { takeoverDismissed = true }
        )
        return
    }
    val events by repository.events.collectAsStateWithLifecycle()
    val history by repository.history.collectAsStateWithLifecycle()
    val thresholds by repository.thresholds.collectAsStateWithLifecycle()
    val stream by repository.stream.collectAsStateWithLifecycle()
    val ackError by repository.acknowledgeError.collectAsStateWithLifecycle()

    val backStack by nav.currentBackStackEntryAsState()
    val route = backStack?.destination?.route
    val onDetail = route?.startsWith("event/") == true

    // The bar used to be washed with a 12 percent tint of the alarm colour. It
    // was invisible at a glance and a stain up close, and the new bar carries
    // the same fact properly: a coloured status dot, and a hairline along its
    // bottom edge that appears only for a real alarm.

    Scaffold(
        topBar = {
            if (!onDetail) {
                // Settings is the only screen that is entered rather than
                // switched to, so it is the only one that owes a way back.
                val backAction: (() -> Unit)? = if (route == Dest.Settings.route) {
                    { nav.popBackStack() }
                } else {
                    null
                }
                SafeFireTopBar(
                    title = stringResource(
                        when (route) {
                            Dest.Live.route -> R.string.live_view
                            Dest.History.route -> R.string.event_history
                            Dest.Analytics.route -> R.string.nav_analytics
                            Dest.Devices.route -> R.string.nav_devices
                            Dest.Settings.route -> R.string.settings
                            else -> R.string.app_name
                        }
                    ),
                    // A level nobody has refreshed is not a status. The bar says
                    // offline rather than repeating whatever the edge froze on.
                    level = if (state.stale) AlarmLevel.OFFLINE else state.level,
                    lastSync = lastSync,
                    onSettings = { nav.navigate(Dest.Settings.route) },
                    onBack = backAction
                )
            }
        },
        bottomBar = {
            if (!onDetail && route != Dest.Settings.route) {
                NavigationBar(
                    containerColor = MaterialTheme.colorScheme.surface,
                    tonalElevation = 0.dp
                ) {
                    tabs.forEach { tab ->
                        val selected = backStack?.destination?.hierarchy
                            ?.any { it.route == tab.dest.route } == true
                        NavigationBarItem(
                            selected = selected,
                            onClick = {
                                nav.navigate(tab.dest.route) {
                                    popUpTo(nav.graph.findStartDestination().id) {
                                        saveState = true
                                    }
                                    launchSingleTop = true
                                    restoreState = true
                                }
                            },
                            icon = {
                                Icon(tab.icon, null, modifier = Modifier.size(21.dp))
                            },
                            label = { Text(stringResource(tab.labelRes)) },
                            colors = NavigationBarItemDefaults.colors(
                                selectedIconColor = MaterialTheme.colorScheme.primary,
                                selectedTextColor = MaterialTheme.colorScheme.primary,
                                indicatorColor = MaterialTheme.colorScheme.primary.copy(alpha = 0.14f)
                            )
                        )
                    }
                }
            }
        }
    ) { padding ->
        Box(Modifier.fillMaxSize()) {
            val inner = PaddingValues(
                top = 0.dp,
                bottom = padding.calculateBottomPadding()
            )
            Column(
                Modifier
                    .fillMaxSize()
                    .padding(top = padding.calculateTopPadding())
            ) {
            NavHost(navController = nav, startDestination = Dest.Status.route) {

                composable(Dest.Status.route) {
                    StatusScreen(
                        state = state,
                        link = link,
                        events = events,
                        ackError = ackError,
                        onOpenLive = { nav.navigate(Dest.Live.route) },
                        onAcknowledge = { repository.acknowledge() },
                        contentPadding = inner
                    )
                }

                composable(Dest.Live.route) {
                    LiveScreen(
                        state = state,
                        stream = stream,
                        onRefresh = { repository.requestFrame() },
                        contentPadding = inner
                    )
                }

                composable(Dest.History.route) {
                    HistoryScreen(
                        events = events,
                        onOpen = { id -> nav.navigate(Dest.Detail.of(id)) },
                        onAcknowledge = { repository.acknowledgeEvent(it) },
                        contentPadding = inner
                    )
                }

                composable(Dest.Analytics.route) {
                    AnalyticsScreen(
                        state = state,
                        events = events,
                        history = history,
                        sensitivity = sensitivity,
                        contentPadding = inner
                    )
                }

                composable(Dest.Devices.route) {
                    DevicesScreen(
                        state = state,
                        link = link,
                        stream = stream,
                        lastSync = lastSync,
                        onRequestFrame = { repository.requestFrame() },
                        contentPadding = inner
                    )
                }

                composable(Dest.Settings.route) {
                    SettingsScreen(
                        prefs = prefs,
                        sensitivity = sensitivity,
                        isDemo = repository.isDemo,
                        onSimulate = { level ->
                            scope.launch {
                                repository.simulate(level)
                                nav.navigate(Dest.Status.route) {
                                    popUpTo(nav.graph.findStartDestination().id)
                                    launchSingleTop = true
                                }
                            }
                        },
                        contentPadding = inner
                    )
                }

                composable(Dest.Detail.route) { entry ->
                    val id = entry.arguments?.getString("id")
                    val event = id?.let { repository.eventById(it) }
                    if (event == null) {
                        LaunchedEffect(Unit) { nav.popBackStack() }
                    } else {
                        EventDetailScreen(
                            event = event,
                            onBack = { nav.popBackStack() },
                            onAcknowledge = { repository.acknowledgeEvent(it) },
                            onDelete = {
                                repository.deleteEvent(it)
                                nav.popBackStack()
                            }
                        )
                    }
                }
            }
            }
        }
    }
}
