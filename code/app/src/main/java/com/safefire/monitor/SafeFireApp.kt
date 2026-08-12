package com.safefire.monitor

import android.Manifest
import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.media.AudioAttributes
import android.media.RingtoneManager
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.google.firebase.firestore.FirebaseFirestore
import com.google.firebase.firestore.FirebaseFirestoreSettings
import com.google.firebase.firestore.PersistentCacheSettings
import com.safefire.monitor.data.AppPrefs
import com.safefire.monitor.data.SafeFireRepository
import com.safefire.monitor.data.ThemeMode
import com.safefire.monitor.data.firebase.FirestoreRepository
import com.safefire.monitor.data.networkAvailability
import com.safefire.monitor.ui.SafeFireRoot
import com.safefire.monitor.ui.theme.SafeFireTheme
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.SupervisorJob
import com.google.firebase.messaging.FirebaseMessaging

class SafeFireApp : Application() {

    private val appScope = CoroutineScope(SupervisorJob())

    lateinit var repository: SafeFireRepository
        private set

    lateinit var prefs: AppPrefs
        private set

    override fun onCreate() {
        super.onCreate()
        prefs = AppPrefs(this)

        FirebaseFirestore.getInstance().firestoreSettings =
            FirebaseFirestoreSettings.Builder()
                .setLocalCacheSettings(
                    PersistentCacheSettings.newBuilder()
                        .setSizeBytes(FirebaseFirestoreSettings.CACHE_SIZE_UNLIMITED)
                        .build()
                )
                .build()

        repository = FirestoreRepository(appScope, prefs, networkAvailability())
        createChannels()

        // One topic instead of a device token list. HTTP v1 has no multicast,
        // so tokens would mean one request per phone and a devices collection
        // that has to be pruned as tokens rotate. Subscribing is idempotent and
        // survives reinstalls, so it is safe to call on every start.
        FirebaseMessaging.getInstance().subscribeToTopic(ALARM_TOPIC)
    }

    private fun createChannels() {
        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        val alarmSound = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_ALARM)
        val audio = AudioAttributes.Builder()
            .setUsage(AudioAttributes.USAGE_ALARM)
            .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
            .build()

        val confirmed = NotificationChannel(
            CHANNEL_CONFIRMED, "Confirmed alarms", NotificationManager.IMPORTANCE_HIGH
        ).apply {
            description = "Camera and sensors both indicate fire"
            enableVibration(true)
            vibrationPattern = longArrayOf(0, 400, 200, 400, 200, 600)
            setSound(alarmSound, audio)
        }

        val alert = NotificationChannel(
            CHANNEL_ALERT, "Camera alerts", NotificationManager.IMPORTANCE_HIGH
        ).apply {
            description = "The camera detected fire"
            enableVibration(true)
            vibrationPattern = longArrayOf(0, 300, 200, 300)
        }

        val watch = NotificationChannel(
            CHANNEL_WATCH, "Sensor watch", NotificationManager.IMPORTANCE_DEFAULT
        ).apply {
            description = "Sensor readings elevated, no visual confirmation"
        }

        nm.createNotificationChannels(listOf(confirmed, alert, watch))
    }

    companion object {
        /** Must match TOPIC_DEFAULT in JETSON/scripts/notify.py. */
        const val ALARM_TOPIC = "alarms"

        const val CHANNEL_CONFIRMED = "safefire.confirmed"
        const val CHANNEL_ALERT = "safefire.alert"
        const val CHANNEL_WATCH = "safefire.watch"
    }
}

class MainActivity : ComponentActivity() {

    private val notificationPermission =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { }

    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)

        val app = application as SafeFireApp
        val repo = app.repository
        val prefs = app.prefs
        val initialEvent = intent?.getStringExtra("eventId")

        setContent {
            val mode by prefs.themeMode.collectAsStateWithLifecycle(ThemeMode.SYSTEM)
            SafeFireTheme(mode = mode) {
                LaunchedEffect(Unit) {
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                        notificationPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
                    }
                }
                SafeFireRoot(
                    repository = repo,
                    prefs = prefs,
                    initialEventId = initialEvent
                )
            }
        }
    }
}
