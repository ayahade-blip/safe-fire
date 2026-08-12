package com.safefire.monitor.data.firebase

import android.Manifest
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Intent
import android.content.pm.PackageManager
import androidx.core.app.ActivityCompat
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import com.google.firebase.firestore.DocumentSnapshot
import com.google.firebase.firestore.FirebaseFirestore
import com.google.firebase.firestore.Query
import com.google.firebase.firestore.SetOptions
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import com.safefire.monitor.MainActivity
import com.safefire.monitor.R
import com.safefire.monitor.SafeFireApp
import com.safefire.monitor.data.AlarmLevel
import com.safefire.monitor.data.AppPrefs
import com.safefire.monitor.data.ChannelHealth
import com.safefire.monitor.data.Detection
import com.safefire.monitor.data.DetectionClass
import com.safefire.monitor.data.FireEvent
import com.safefire.monitor.data.FusionRationale
import com.safefire.monitor.data.LinkState
import com.safefire.monitor.data.NodeStatus
import com.safefire.monitor.data.SafeFireRepository
import com.safefire.monitor.data.SensorSample
import com.safefire.monitor.data.StreamInfo
import com.safefire.monitor.data.SystemState
import com.safefire.monitor.data.Thresholds
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class FirestoreRepository(
    scope: CoroutineScope,
    private val prefs: AppPrefs? = null,
    online: Flow<Boolean>? = null
) : SafeFireRepository {

    override val isDemo = false

    private val db = FirebaseFirestore.getInstance()

    private val _link = MutableStateFlow(LinkState.CONNECTING)
    override val link: StateFlow<LinkState> = _link.asStateFlow()

    private val _lastSync = MutableStateFlow(0L)
    override val lastSync: StateFlow<Long> = _lastSync.asStateFlow()

    private var hasNetwork = true
    private val prefsScope: CoroutineScope? = scope

    private val _state = MutableStateFlow(emptyState())
    override val state: StateFlow<SystemState> = _state.asStateFlow()

    private val _history = MutableStateFlow<List<SensorSample>>(emptyList())
    override val history: StateFlow<List<SensorSample>> = _history.asStateFlow()

    private val _events = MutableStateFlow<List<FireEvent>>(emptyList())
    override val events: StateFlow<List<FireEvent>> = _events.asStateFlow()

    private val _thresholds = MutableStateFlow(Thresholds())
    override val thresholds: StateFlow<Thresholds> = _thresholds.asStateFlow()

    private val _stream = MutableStateFlow(StreamInfo.NONE)
    override val stream: StateFlow<StreamInfo> = _stream.asStateFlow()

    private val _acknowledgeError = MutableStateFlow<String?>(null)
    override val acknowledgeError: StateFlow<String?> = _acknowledgeError.asStateFlow()

    private val _alarms = MutableSharedFlow<FireEvent>(extraBufferCapacity = 4)
    override val alarms = _alarms.asSharedFlow()

    private var lastAlarmId: String? = null

    init {
        db.collection("state").document("current")
            .addSnapshotListener { doc, err ->
                if (err != null) { updateLink(null); return@addSnapshotListener }
                if (doc != null && doc.exists()) {
                    _state.value = doc.toSystemState(nodesNow())
                    val cached = doc.metadata.isFromCache
                    if (!cached) _lastSync.value = System.currentTimeMillis()
                    updateLink(cached)
                }
            }

        if (online != null) {
            scope.launch {
                online.collect { up ->
                    hasNetwork = up
                    updateLink(null)
                }
            }
        }
        if (prefs != null) {
            scope.launch { prefs.thresholds.collect { _thresholds.value = it } }
        }

        db.collection("events")
            .orderBy("timestamp", Query.Direction.DESCENDING)
            .limit(100)
            .addSnapshotListener { snap, _ ->
                val list = snap?.documents?.mapNotNull { it.toFireEvent() }.orEmpty()
                _events.value = list
                list.firstOrNull()?.let { newest ->
                    if (lastAlarmId != null && newest.id != lastAlarmId && newest.level.isAlarming) {
                        _alarms.tryEmit(newest)
                    }
                    lastAlarmId = newest.id
                }
            }

        db.collection("readings")
            .orderBy("timestamp", Query.Direction.DESCENDING)
            .limit(120)
            .addSnapshotListener { snap, _ ->
                _history.value = snap?.documents
                    ?.mapNotNull { it.toSensorSample() }
                    ?.reversed()
                    .orEmpty()
            }

        db.collection("nodes").addSnapshotListener { snap, _ ->
            val nodes = snap?.documents?.mapNotNull { it.toNodeStatus() }.orEmpty()
                .sortedBy { if (it.id == "jetson") 0 else 1 }
            if (nodes.isNotEmpty()) _state.value = _state.value.copy(nodes = nodes)

            // The Jetson publishes its own LAN address here because the phone has
            // no way to discover it: the two only ever meet through Firestore.
            // All four fields are absent until the Jetson has booted at least
            // once, which is the normal state and not an error.
            val jetson = snap?.documents?.firstOrNull { it.id == "jetson" }
            _stream.value = if (jetson == null) {
                StreamInfo.NONE
            } else {
                val ip = jetson.getString("lanIp")
                val port = jetson.getLong("streamPort")?.toInt()
                val advertised = jetson.getString("streamUrl")
                StreamInfo(
                    // Prefer what the Jetson actually wrote. Rebuilding it from
                    // ip and port is only a fallback for an older node that
                    // published the parts but not the whole.
                    url = advertised?.takeIf { it.isNotBlank() }
                        ?: if (!ip.isNullOrBlank() && port != null) {
                            "http://$ip:$port/stream.mjpg"
                        } else {
                            null
                        },
                    lanIp = ip,
                    port = port,
                    up = jetson.getBoolean("streamUp") ?: false
                )
            }
        }
    }

    override fun acknowledge() {
        // The screen answers the press now. Waiting for the round trip meant a
        // failed write looked exactly like a dead button: nothing moved and
        // nothing was said.
        _state.value = _state.value.copy(acknowledged = true)
        _acknowledgeError.value = null

        // set with merge, not update. update fails with NOT_FOUND when the
        // document has never been written, which is the ordinary state before
        // the Jetson has run once, and that failure was silent.
        db.collection("state").document("current")
            .set(mapOf("acknowledged" to true), SetOptions.merge())
            .addOnFailureListener { e ->
                // Put it back. An acknowledgement the cloud never received must
                // not keep looking acknowledged here, or the alarm is answered
                // on this phone alone while every other device still waits.
                _state.value = _state.value.copy(acknowledged = false)
                _acknowledgeError.value = e.message ?: e.javaClass.simpleName
            }
        _events.value.firstOrNull()?.let { acknowledgeEvent(it.id) }
    }

    override fun deleteEvent(id: String) {
        // Same lookup the acknowledge path uses: the document id is generated by
        // the edge device and is not the event id, so the field is queried.
        db.collection("events").whereEqualTo("id", id).get()
            .addOnSuccessListener { snap ->
                snap.documents.forEach { it.reference.delete() }
            }
        // Drop it locally too rather than waiting for the listener, so the row
        // leaves the screen the moment the user confirms.
        _events.value = _events.value.filterNot { it.id == id }
    }

    override fun acknowledgeEvent(id: String) {
        db.collection("events").whereEqualTo("id", id).get()
            .addOnSuccessListener { snap ->
                snap.documents.forEach { it.reference.update("acknowledged", true) }
            }
    }

    private fun updateLink(fromCache: Boolean?) {
        _link.value = when {
            !hasNetwork -> LinkState.OFFLINE
            fromCache == true -> LinkState.CACHED
            fromCache == false -> LinkState.LIVE
            _link.value == LinkState.CONNECTING -> LinkState.CONNECTING
            else -> _link.value
        }
    }

    override fun updateThresholds(value: Thresholds) {
        _thresholds.value = value
        prefsScope?.let { s -> prefs?.let { p -> s.launch { p.setThresholds(value) } } }
        db.collection("config").document("thresholds").set(
            mapOf(
                "confidence" to value.confidence,
                "surfaceTempC" to value.surfaceTempC,
                "gasRisePctAlarm" to value.gasRisePctAlarm
            )
        )
    }

    override suspend fun requestFrame() {
        db.collection("commands").document("requestFrame")
            .set(mapOf("at" to System.currentTimeMillis()))
    }

    override fun simulate(level: AlarmLevel) = Unit

    override fun eventById(id: String): FireEvent? = _events.value.firstOrNull { it.id == id }

    private fun nodesNow(): List<NodeStatus> = _state.value.nodes

    private fun DocumentSnapshot.toSystemState(nodes: List<NodeStatus>) = SystemState(
        level = levelOf(getString("level")),
        since = getLong("since") ?: System.currentTimeMillis(),
        detections = detectionsOf(get("detections")),
        frame = frameFor(levelOf(getString("level"))),
        sensors = sensorsOf(get("sensors")),
        nodes = nodes.ifEmpty { placeholderNodes() },
        fps = (getDouble("fps") ?: 0.0).toFloat(),
        inferenceMs = (getDouble("inferenceMs") ?: 0.0).toFloat(),
        rationale = rationaleOf(get("rationale")),
        acknowledged = getBoolean("acknowledged") ?: false,
        frameB64 = getString("frameB64"),
        updatedAt = getLong("updatedAt")
    )

    private fun DocumentSnapshot.toFireEvent(): FireEvent? {
        val level = levelOf(getString("level"))
        return FireEvent(
            id = getString("id") ?: id,
            // The edge wrote "since" and never "timestamp", and Firestore's
            // orderBy also filters for existence of the ordered field, so every
            // event was excluded by the query itself and history was
            // permanently empty. The edge now writes both; fall back to "since"
            // so documents stored before that fix are still readable.
            timestamp = getLong("timestamp") ?: getLong("since") ?: return null,
            level = level,
            detections = detectionsOf(get("detections")),
            sensors = sensorsOf(get("sensors")),
            frame = frameFor(level),
            rationale = rationaleOf(get("rationale")),
            acknowledged = getBoolean("acknowledged") ?: false,
            frameB64 = getString("frameB64")
        )
    }

    private fun DocumentSnapshot.toSensorSample(): SensorSample? {
        val ts = getLong("timestamp") ?: return null
        return SensorSample(
            timestamp = ts,
            sampleAgeMs = getLong("sampleAgeMs"),
            ambientC = getDouble("ambientC")?.toFloat(),
            surfaceC = getDouble("surfaceC")?.toFloat(),
            surfaceRiseC = getDouble("surfaceRiseC")?.toFloat(),
            gasRatio = getDouble("gasRatio")?.toFloat(),
            gasRisePct = getDouble("gasRisePct")?.toFloat(),
            flameIr = getDouble("flameIr")?.toFloat(),
            flameDropMv = getLong("flameDropMv")?.toInt(),
            ok = ChannelHealth(
                ds = getBoolean("okDs") ?: false,
                mlx = getBoolean("okMlx") ?: false,
                mq2 = getBoolean("okMq2") ?: false,
                flame = getBoolean("okFlame") ?: false
            ),
            present = true
        )
    }

    private fun DocumentSnapshot.toNodeStatus(): NodeStatus? {
        val seen = getLong("lastSeen") ?: return null
        val stale = System.currentTimeMillis() - seen > 45_000
        return NodeStatus(
            id = id,
            name = getString("name") ?: id,
            online = (getBoolean("online") ?: false) && !stale,
            lastSeen = seen,
            detail = getString("detail").orEmpty()
        )
    }

    private fun levelOf(raw: String?) = runCatching {
        AlarmLevel.valueOf(raw.orEmpty())
    }.getOrDefault(AlarmLevel.OFFLINE)

    @Suppress("UNCHECKED_CAST")
    private fun detectionsOf(raw: Any?): List<Detection> =
        (raw as? List<Map<String, Any?>>).orEmpty().mapNotNull { m ->
            val label = runCatching {
                DetectionClass.valueOf((m["label"] as? String).orEmpty())
            }.getOrNull() ?: return@mapNotNull null
            Detection(
                label = label,
                confidence = (m["confidence"] as? Number)?.toFloat() ?: 0f,
                x = (m["x"] as? Number)?.toFloat() ?: 0f,
                y = (m["y"] as? Number)?.toFloat() ?: 0f,
                w = (m["w"] as? Number)?.toFloat() ?: 0f,
                h = (m["h"] as? Number)?.toFloat() ?: 0f
            )
        }

    @Suppress("UNCHECKED_CAST")
    private fun sensorsOf(raw: Any?): SensorSample {
        // No map at all means the node is silent. Returning NONE, whose fields
        // are null and whose present flag is false, is what lets the UI print a
        // dash. The previous version defaulted every field to 0, so a dead node
        // rendered as a real reading of 0 C with no gas.
        val m = (raw as? Map<String, Any?>) ?: return SensorSample.NONE
        fun f(k: String) = (m[k] as? Number)?.toFloat()
        fun i(k: String) = (m[k] as? Number)?.toInt()
        fun b(k: String) = m[k] as? Boolean ?: false
        return SensorSample(
            timestamp = (m["timestamp"] as? Number)?.toLong() ?: System.currentTimeMillis(),
            sampleAgeMs = (m["sampleAgeMs"] as? Number)?.toLong(),
            nodeLevel = (m["nodeLevel"] as? String)?.let { s ->
                runCatching { AlarmLevel.valueOf(s) }.getOrNull()
            },
            ambientC = f("ambientC"),
            surfaceC = f("surfaceC"),
            surfaceRiseC = f("surfaceRiseC"),
            gasRatio = f("gasRatio"),
            gasRisePct = f("gasRisePct"),
            flameIr = f("flameIr"),
            flameMinMv = i("flameMinMv"),
            flameDropMv = i("flameDropMv"),
            flameP2pMv = i("flameP2pMv"),
            calAgeS = (m["calAgeS"] as? Number)?.toLong(),
            ok = ChannelHealth(b("okDs"), b("okMlx"), b("okMq2"), b("okFlame")),
            // The edge sends nodeOnline=false with every channel null when the
            // serial link is quiet, so a map can arrive that still means "no
            // reading". Treat that as absent rather than as data.
            present = (m["nodeOnline"] as? Boolean) ?: true
        )
    }

    @Suppress("UNCHECKED_CAST")
    private fun rationaleOf(raw: Any?): FusionRationale {
        val m = (raw as? Map<String, Any?>).orEmpty()
        return FusionRationale(
            visionSaid = m["visionSaid"] as? String ?: "",
            sensorsSaid = m["sensorsSaid"] as? String ?: "",
            conclusion = m["conclusion"] as? String ?: "",
            visionContributed = m["visionContributed"] as? Boolean ?: false,
            sensorsContributed = m["sensorsContributed"] as? Boolean ?: false
        )
    }

    private fun frameFor(level: AlarmLevel) = when (level) {
        AlarmLevel.CONFIRMED -> R.drawable.frame_confirmed
        AlarmLevel.ALERT -> R.drawable.frame_flame
        else -> R.drawable.frame_normal
    }

    private fun placeholderNodes() = listOf(
        NodeStatus("jetson", "Jetson Nano", false, 0L, "Waiting for heartbeat"),
        NodeStatus("esp32", "ESP32 node", false, 0L, "Waiting for heartbeat")
    )

    private fun emptyState() = SystemState(
        level = AlarmLevel.OFFLINE,
        since = System.currentTimeMillis(),
        detections = emptyList(),
        frame = R.drawable.frame_normal,
        sensors = SensorSample.NONE,
        nodes = placeholderNodes(),
        fps = 0f,
        inferenceMs = 0f,
        rationale = FusionRationale(
            "Waiting for the first frame.", "Waiting for the sensor node.",
            "Connecting.", visionContributed = false, sensorsContributed = false
        ),
        acknowledged = true
    )
}

class SafeFireMessagingService : FirebaseMessagingService() {

    override fun onMessageReceived(message: RemoteMessage) {
        val data = message.data
        val level = runCatching {
            AlarmLevel.valueOf(data["level"].orEmpty())
        }.getOrDefault(AlarmLevel.WATCH)

        val channel = when (level) {
            AlarmLevel.CONFIRMED -> SafeFireApp.CHANNEL_CONFIRMED
            AlarmLevel.ALERT -> SafeFireApp.CHANNEL_ALERT
            else -> SafeFireApp.CHANNEL_WATCH
        }

        // Composed here rather than sent. The sentence the edge writes into the
        // event is English, so pushing it would put English on an Arabic phone
        // for the one message that has to be understood instantly. The payload
        // carries only what cannot be derived: the level and which event it is.
        val title = getString(
            when (level) {
                AlarmLevel.CONFIRMED -> R.string.level_confirmed
                AlarmLevel.ALERT -> R.string.level_alert
                AlarmLevel.OFFLINE -> R.string.level_offline
                else -> R.string.level_watch
            }
        )
        val body = getString(
            when (level) {
                AlarmLevel.CONFIRMED -> R.string.conclusion_confirmed
                AlarmLevel.ALERT -> R.string.conclusion_alert
                AlarmLevel.OFFLINE -> R.string.conclusion_offline
                else -> R.string.conclusion_watch
            }
        )

        val intent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP
            putExtra("eventId", data["eventId"])
        }
        val pending = PendingIntent.getActivity(
            this, 0, intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val notification = NotificationCompat.Builder(this, channel)
            .setSmallIcon(R.drawable.ic_launcher_foreground)
            .setContentTitle(title)
            .setContentText(body)
            .setStyle(NotificationCompat.BigTextStyle().bigText(body))
            .setPriority(
                if (level.isAlarming) NotificationCompat.PRIORITY_MAX
                else NotificationCompat.PRIORITY_DEFAULT
            )
            .setCategory(NotificationCompat.CATEGORY_ALARM)
            .setAutoCancel(true)
            .setContentIntent(pending)
            .build()

        if (ActivityCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS)
            == PackageManager.PERMISSION_GRANTED
        ) {
            NotificationManagerCompat.from(this)
                .notify(level.ordinal, notification)
        }
    }

    override fun onNewToken(token: String) {
        com.google.firebase.firestore.FirebaseFirestore.getInstance()
            .collection("devices").document(token)
            .set(mapOf("token" to token, "updated" to System.currentTimeMillis()))
    }

    @Suppress("unused")
    private fun nm() = getSystemService(NotificationManager::class.java)
}
