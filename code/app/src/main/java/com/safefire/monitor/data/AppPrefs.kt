package com.safefire.monitor.data

import android.content.Context
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.net.NetworkRequest
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.floatPreferencesKey
import androidx.datastore.preferences.core.intPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.map

private val Context.store by preferencesDataStore("safefire")

enum class ThemeMode { SYSTEM, LIGHT, DARK }

class AppPrefs(private val ctx: Context) {

    private object K {
        val THEME = stringPreferencesKey("theme_mode")
        val CONF = floatPreferencesKey("thr_conf")
        val TEMP = floatPreferencesKey("thr_temp")
        // Deliberately a NEW key name. DataStore throws if an existing
        // Int key is read as Float, so the ppm key is abandoned, not
        // reused. Gas is a ratio here; ppm was never calibrated.
        val GAS_RISE = floatPreferencesKey("gas_rise_pct")
        val N_CONFIRMED = booleanPreferencesKey("notify_confirmed")
        val N_ALERT = booleanPreferencesKey("notify_alert")
        val N_WATCH = booleanPreferencesKey("notify_watch")
        val HAPTICS = booleanPreferencesKey("haptics")
        val SENS = stringPreferencesKey("sensitivity")
    }

    val themeMode: Flow<ThemeMode> = ctx.store.data.map { p ->
        runCatching { ThemeMode.valueOf(p[K.THEME] ?: "SYSTEM") }
            .getOrDefault(ThemeMode.SYSTEM)
    }

    val haptics: Flow<Boolean> = ctx.store.data.map { it[K.HAPTICS] ?: true }

    val thresholds: Flow<Thresholds> = ctx.store.data.map { p -> p.toThresholds() }

    val sensitivity: Flow<Sensitivity> = ctx.store.data.map { p ->
        runCatching { Sensitivity.valueOf(p[K.SENS] ?: "") }
            .getOrDefault(Sensitivity.DEFAULT)
    }

    suspend fun setSensitivity(s: Sensitivity) {
        ctx.store.edit {
            it[K.SENS] = s.name
            it[K.CONF] = s.conf
        }
    }

    suspend fun setTheme(mode: ThemeMode) {
        ctx.store.edit { it[K.THEME] = mode.name }
    }

    suspend fun setHaptics(on: Boolean) {
        ctx.store.edit { it[K.HAPTICS] = on }
    }

    suspend fun setThresholds(t: Thresholds) {
        ctx.store.edit { p ->
            p[K.CONF] = t.confidence
            p[K.TEMP] = t.surfaceTempC
            p[K.GAS_RISE] = t.gasRisePctAlarm
            p[K.N_CONFIRMED] = t.notifyConfirmed
            p[K.N_ALERT] = t.notifyAlert
            p[K.N_WATCH] = t.notifyWatch
        }
    }

    private fun Preferences.toThresholds(): Thresholds {
        val d = Thresholds()
        return Thresholds(
            confidence = this[K.CONF] ?: d.confidence,
            surfaceTempC = this[K.TEMP] ?: d.surfaceTempC,
            gasRisePctAlarm = this[K.GAS_RISE] ?: d.gasRisePctAlarm,
            notifyConfirmed = this[K.N_CONFIRMED] ?: d.notifyConfirmed,
            notifyAlert = this[K.N_ALERT] ?: d.notifyAlert,
            notifyWatch = this[K.N_WATCH] ?: d.notifyWatch
        )
    }
}

fun Context.networkAvailability(): Flow<Boolean> = callbackFlow {
    val cm = getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager

    fun current(): Boolean {
        val n: Network = cm.activeNetwork ?: return false
        val caps = cm.getNetworkCapabilities(n) ?: return false
        return caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET) &&
                caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED)
    }

    trySend(current())

    val cb = object : ConnectivityManager.NetworkCallback() {
        override fun onAvailable(network: Network) { trySend(current()) }
        override fun onLost(network: Network) { trySend(current()) }
        override fun onCapabilitiesChanged(network: Network, caps: NetworkCapabilities) {
            trySend(current())
        }
    }

    val req = NetworkRequest.Builder()
        .addCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
        .build()
    cm.registerNetworkCallback(req, cb)

    awaitClose { runCatching { cm.unregisterNetworkCallback(cb) } }
}.distinctUntilChanged()
