package com.safefire.monitor.data

import com.safefire.monitor.R
import kotlin.math.max
import kotlin.math.sin
import kotlin.random.Random
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

interface SafeFireRepository {

    val isDemo: Boolean

    val link: StateFlow<LinkState>

    val lastSync: StateFlow<Long>

    val state: StateFlow<SystemState>

    val history: StateFlow<List<SensorSample>>

    val events: StateFlow<List<FireEvent>>

    val thresholds: StateFlow<Thresholds>

    /** Where the Jetson advertises its video stream, or [StreamInfo.NONE]. */
    val stream: StateFlow<StreamInfo>

    /**
     * Why the last acknowledgement did not reach the cloud, or null.
     *
     * A press that fails silently is indistinguishable from a broken
     * button, and this alarm is the one thing in the app a person must be
     * able to trust they have answered.
     */
    val acknowledgeError: StateFlow<String?>

    fun updateThresholds(value: Thresholds)

    fun acknowledge()

    fun acknowledgeEvent(id: String)

    /** Remove an event for good. The caller confirms first; this does not ask. */
    fun deleteEvent(id: String)

    suspend fun requestFrame()

    fun simulate(level: AlarmLevel)

    fun eventById(id: String): FireEvent?

    val alarms: Flow<FireEvent>
}

class DemoRepository(scope: CoroutineScope) : SafeFireRepository {

    override val isDemo = true

    private val _link = MutableStateFlow(LinkState.LIVE)
    override val link: StateFlow<LinkState> = _link.asStateFlow()

    private val _lastSync = MutableStateFlow(System.currentTimeMillis())
    override val lastSync: StateFlow<Long> = _lastSync.asStateFlow()

    private val rng = Random(42)
    private var tick = 0

    private val _state = MutableStateFlow(normalState())
    override val state: StateFlow<SystemState> = _state.asStateFlow()

    private val _history = MutableStateFlow(seedHistory())
    override val history: StateFlow<List<SensorSample>> = _history.asStateFlow()

    private val _events = MutableStateFlow(seedEvents())
    override val events: StateFlow<List<FireEvent>> = _events.asStateFlow()

    private val _thresholds = MutableStateFlow(Thresholds())
    override val thresholds: StateFlow<Thresholds> = _thresholds.asStateFlow()

    /**
     * Demo mode never advertises a stream. There is no Jetson behind it, and a
     * fake address would make the live screen spend its life reconnecting to a
     * host that does not exist.
     */
    override val stream: StateFlow<StreamInfo> = MutableStateFlow(StreamInfo.NONE)

    /** Demo mode writes nowhere, so nothing can fail to be written. */
    override val acknowledgeError: StateFlow<String?> = MutableStateFlow(null)

    private val _alarms = MutableSharedFlow<FireEvent>(extraBufferCapacity = 4)
    override val alarms = _alarms.asSharedFlow()

    init {
        scope.launch {
            while (true) {
                delay(2_000)
                tick++
                drift()
            }
        }
    }

    private fun drift() {
        val s = _state.value
        if (s.level != AlarmLevel.NORMAL && s.level != AlarmLevel.WATCH) return

        val base = 24.5f
        val wobble = sin(tick / 9f) * 0.7f
        val sample = SensorSample(
            timestamp = System.currentTimeMillis(),
            ambientC = base + wobble + rng.nextFloat() * 0.2f,
            surfaceC = base + 1.6f + wobble + rng.nextFloat() * 0.3f,
            gasRatio = 0.98f - sin(tick / 6f) * 0.05f,
            gasRisePct = (sin(tick / 6f) * 5f + 2f),
            ok = ChannelHealth(true, true, true, true),
            present = true,
            flameIr = 0.02f + rng.nextFloat() * 0.03f
        )
        _history.value = (_history.value + sample).takeLast(HISTORY_POINTS)
        _state.value = s.copy(
            sensors = sample,
            fps = 19.6f + rng.nextFloat() * 0.7f,
            inferenceMs = 48.4f + rng.nextFloat() * 1.4f
        )
    }

    override fun simulate(level: AlarmLevel) {
        val now = System.currentTimeMillis()
        val next = when (level) {
            AlarmLevel.NORMAL -> normalState()
            AlarmLevel.WATCH -> watchState(now)
            AlarmLevel.ALERT -> alertState(now)
            AlarmLevel.CONFIRMED -> confirmedState(now)
            AlarmLevel.OFFLINE -> offlineState(now)
        }
        _state.value = next

        _history.value = (_history.value + next.sensors).takeLast(HISTORY_POINTS)

        if (level.isAlarming || level == AlarmLevel.WATCH) {
            val event = FireEvent(
                id = "evt_${now}",
                timestamp = now,
                level = level,
                detections = next.detections,
                sensors = next.sensors,
                frame = next.frame,
                rationale = next.rationale
            )
            _events.value = listOf(event) + _events.value
            _alarms.tryEmit(event)
        }
    }

    override fun acknowledge() {
        _state.value = _state.value.copy(acknowledged = true)
        _events.value = _events.value.mapIndexed { i, e ->
            if (i == 0) e.copy(acknowledged = true) else e
        }
    }

    override fun acknowledgeEvent(id: String) {
        _events.value = _events.value.map { if (it.id == id) it.copy(acknowledged = true) else it }
    }

    override fun deleteEvent(id: String) {
        _events.value = _events.value.filterNot { it.id == id }
    }

    override fun updateThresholds(value: Thresholds) {
        _thresholds.value = value
    }

    override suspend fun requestFrame() {
        delay(450)
        _state.value = _state.value.copy(since = System.currentTimeMillis())
    }

    override fun eventById(id: String): FireEvent? = _events.value.firstOrNull { it.id == id }

    private fun nodes(cameraOnline: Boolean = true, sensorOnline: Boolean = true) = listOf(
        NodeStatus(
            id = "jetson",
            name = "Jetson Nano",
            online = cameraOnline,
            lastSeen = System.currentTimeMillis(),
            detail = if (cameraOnline) "YOLO26n · TensorRT FP16" else "No heartbeat"
        ),
        NodeStatus(
            id = "esp32",
            name = "ESP32 node",
            online = sensorOnline,
            lastSeen = System.currentTimeMillis(),
            detail = if (sensorOnline) "MLX90614 · MQ-2 · flame IR" else "No heartbeat"
        )
    )

    private fun normalState() = SystemState(
        level = AlarmLevel.NORMAL,
        since = System.currentTimeMillis(),
        detections = emptyList(),
        frame = R.drawable.frame_normal,
        sensors = demoSample(System.currentTimeMillis(), 24.6f, 26.1f, 0.99f, 0.03f),
        nodes = nodes(),
        fps = 19.9f,
        inferenceMs = 49.1f,
        rationale = FusionRationale(
            visionSaid = "No flame or smoke above 0.50 confidence. A lamp is in frame and was correctly ignored.",
            sensorsSaid = "Surface 26.1 °C, gas ratio 0.99, both inside the normal band.",
            conclusion = "Nothing to report.",
            visionContributed = false,
            sensorsContributed = false
        ),
        acknowledged = true
    )

    private fun watchState(now: Long) = SystemState(
        level = AlarmLevel.WATCH,
        since = now,
        detections = emptyList(),
        frame = R.drawable.frame_normal,
        sensors = demoSample(now, 29.4f, 47.8f, 0.71f, 0.11f),
        nodes = nodes(),
        fps = 19.8f,
        inferenceMs = 49.3f,
        rationale = FusionRationale(
            visionSaid = "Camera is clear. Highest score in frame was 0.11, well under the 0.50 threshold.",
            sensorsSaid = "Gas fell to 0.71 of its clean-air baseline and surface temperature is rising 3.1 °C per minute.",
            conclusion = "Sensors alone cannot raise a fire alarm, so the system moves to Watch and keeps looking. " +
                    "If the camera confirms, this becomes a full alarm immediately.",
            visionContributed = false,
            sensorsContributed = true
        ),
        acknowledged = false
    )

    private fun alertState(now: Long) = SystemState(
        level = AlarmLevel.ALERT,
        since = now,
        detections = listOf(
            Detection(DetectionClass.FLAME, 0.87f, 0.38f, 0.22f, 0.30f, 0.62f)
        ),
        frame = R.drawable.frame_flame,
        sensors = demoSample(now, 25.9f, 31.4f, 0.94f, 0.06f),
        nodes = nodes(),
        fps = 19.7f,
        inferenceMs = 49.6f,
        rationale = FusionRationale(
            visionSaid = "Flame detected at 0.87 confidence, held across 4 consecutive frames.",
            sensorsSaid = "Sensors still normal — the fire is out of the node's reach.",
            conclusion = "The camera alarms on its own. Sensors are never allowed to veto a visual detection, " +
                    "which is what protects against a fire far from the sensor node.",
            visionContributed = true,
            sensorsContributed = false
        ),
        acknowledged = false
    )

    private fun confirmedState(now: Long) = SystemState(
        level = AlarmLevel.CONFIRMED,
        since = now,
        detections = listOf(
            Detection(DetectionClass.FLAME, 0.93f, 0.30f, 0.46f, 0.24f, 0.34f),
            Detection(DetectionClass.SMOKE, 0.78f, 0.06f, 0.16f, 0.86f, 0.52f)
        ),
        frame = R.drawable.frame_confirmed,
        sensors = demoSample(now, 38.2f, 71.5f, 0.48f, 0.42f),
        nodes = nodes(),
        fps = 19.5f,
        inferenceMs = 50.2f,
        rationale = FusionRationale(
            visionSaid = "Flame at 0.93 and smoke at 0.78, both sustained.",
            sensorsSaid = "Surface temperature 71.5 °C, gas ratio 0.48, flame IR channel active.",
            conclusion = "Both independent channels agree. Highest priority alarm, sent immediately.",
            visionContributed = true,
            sensorsContributed = true
        ),
        acknowledged = false
    )

    private fun offlineState(now: Long) = normalState().copy(
        level = AlarmLevel.OFFLINE,
        since = now,
        nodes = nodes(cameraOnline = false),
        fps = 0f,
        inferenceMs = 0f,
        rationale = FusionRationale(
            visionSaid = "No frames received for 45 seconds.",
            sensorsSaid = "Sensor node still reporting, all bands normal.",
            conclusion = "Detection is degraded. The sensor channel keeps watch on its own until the camera returns.",
            visionContributed = false,
            sensorsContributed = false
        ),
        acknowledged = false
    )

    private fun seedHistory(): List<SensorSample> {
        val now = System.currentTimeMillis()
        return (0 until HISTORY_POINTS).map { i ->
            val t = now - (HISTORY_POINTS - i) * 30_000L
            val wob = sin(i / 9f)
            SensorSample(
                timestamp = t,
                ambientC = 24.4f + wob * 0.8f,
                surfaceC = 26.0f + wob * 1.1f,
                gasRatio = 0.99f - wob * 0.04f,
                gasRisePct = wob * 4f,
                ok = ChannelHealth(true, true, true, true),
                present = true,
                flameIr = max(0f, 0.03f + wob * 0.01f)
            )
        }
    }

    private fun seedEvents(): List<FireEvent> {
        val now = System.currentTimeMillis()
        val hour = 3_600_000L
        return listOf(
            FireEvent(
                id = "evt_seed_1",
                timestamp = now - 2 * hour,
                level = AlarmLevel.ALERT,
                detections = listOf(Detection(DetectionClass.FLAME, 0.82f, 0.36f, 0.24f, 0.30f, 0.58f)),
                sensors = demoSample(now - 2 * hour, 26.1f, 33.0f, 0.93f, 0.07f),
                frame = R.drawable.frame_flame,
                rationale = FusionRationale(
                    "Flame at 0.82 across 3 frames.",
                    "Sensors normal, fire outside their range.",
                    "Camera-only alarm raised.",
                    visionContributed = true,
                    sensorsContributed = false
                ),
                acknowledged = true
            ),
            FireEvent(
                id = "evt_seed_2",
                timestamp = now - 7 * hour,
                level = AlarmLevel.WATCH,
                detections = emptyList(),
                sensors = demoSample(now - 7 * hour, 28.8f, 44.2f, 0.74f, 0.09f),
                frame = R.drawable.frame_normal,
                rationale = FusionRationale(
                    "Camera clear, top score 0.09.",
                    "Gas fell to 0.74 of baseline while cooking.",
                    "Watch only. No visual confirmation, so no alarm was raised.",
                    visionContributed = false,
                    sensorsContributed = true
                ),
                acknowledged = true
            ),
            FireEvent(
                id = "evt_seed_3",
                timestamp = now - 27 * hour,
                level = AlarmLevel.CONFIRMED,
                detections = listOf(
                    Detection(DetectionClass.SMOKE, 0.74f, 0.05f, 0.14f, 0.88f, 0.46f),
                    Detection(DetectionClass.FLAME, 0.90f, 0.55f, 0.52f, 0.20f, 0.30f)
                ),
                sensors = demoSample(now - 27 * hour, 36.5f, 68.9f, 0.52f, 0.38f),
                frame = R.drawable.frame_smoke,
                rationale = FusionRationale(
                    "Smoke 0.74 and flame 0.90.",
                    "Surface 68.9 °C, gas ratio 0.52.",
                    "Both channels agreed. Confirmed alarm.",
                    visionContributed = true,
                    sensorsContributed = true
                ),
                acknowledged = true
            )
        )
    }

    private companion object {
        const val HISTORY_POINTS = 120
    }
}

/**
 * Build a plausible demo sample in the real shape.
 *
 * Gas is a ratio, never a ppm figure, so demo mode cannot teach a unit
 * the hardware has deliberately decided it cannot honestly produce.
 */
private fun demoSample(
    ts: Long, ambient: Float, surface: Float, ratio: Float, ir: Float
): SensorSample = SensorSample(
    timestamp = ts,
    sampleAgeMs = 0L,
    ambientC = ambient,
    surfaceC = surface,
    surfaceRiseC = surface - ambient,
    gasRatio = ratio,
    gasRisePct = (1f - ratio) * 100f,
    flameIr = ir,
    ok = ChannelHealth(true, true, true, true),
    present = true
)

