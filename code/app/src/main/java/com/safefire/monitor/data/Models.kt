package com.safefire.monitor.data

import androidx.annotation.DrawableRes

enum class AlarmLevel(val rank: Int) {
    OFFLINE(-1),
    NORMAL(0),
    WATCH(1),
    ALERT(2),
    CONFIRMED(3);

    val isAlarming: Boolean get() = rank >= ALERT.rank
}

enum class DetectionClass { FLAME, SMOKE }

enum class LinkState {
    CONNECTING,
    LIVE,
    CACHED,
    OFFLINE
}

data class Detection(
    val label: DetectionClass,
    val confidence: Float,
    val x: Float,
    val y: Float,
    val w: Float,
    val h: Float
)

/** Which of the node's four channels answered on the last sample. */
data class ChannelHealth(
    val ds: Boolean = false,
    val mlx: Boolean = false,
    val mq2: Boolean = false,
    val flame: Boolean = false
) {
    val anyUp: Boolean get() = ds || mlx || mq2 || flame
}

/**
 * One sample from the ESP32 node.
 *
 * Every channel is nullable, and null means "not measured" rather than zero.
 * The previous version defaulted each missing value to 0, which made a dead
 * node indistinguishable from a room at 0 degrees with no gas. That is exactly
 * the failure this project accuses the field of, so it does not belong here.
 *
 * There is deliberately no gasPpm. The MQ-2 datasheet defines R0 as the
 * resistance in 1000 ppm LPG while the node baselines in clean air, so the
 * published ppm curves do not apply to this ratio, and any number would be a
 * fabricated unit. [gasRatio] is the measurement: 1.0 is clean air, lower means
 * more gas. [gasRisePct] is the same quantity stated for a reader.
 */
data class SensorSample(
    val timestamp: Long,
    val sampleAgeMs: Long? = null,
    val nodeLevel: AlarmLevel? = null,
    val ambientC: Float? = null,
    val surfaceC: Float? = null,
    val surfaceRiseC: Float? = null,
    val gasRatio: Float? = null,
    val gasRisePct: Float? = null,
    val flameIr: Float? = null,
    val flameMinMv: Int? = null,
    val flameDropMv: Int? = null,
    val flameP2pMv: Int? = null,
    val calAgeS: Long? = null,
    val ok: ChannelHealth = ChannelHealth(),
    /** False when no sensors map reached us at all: the node is silent. */
    val present: Boolean = false
) {
    /** Older than this and it is history, not a reading. */
    val stale: Boolean get() = (sampleAgeMs ?: Long.MAX_VALUE) > STALE_AFTER_MS

    companion object {
        const val STALE_AFTER_MS = 15_000L

        /** No node, no data. Rendered as dashes, never as values. */
        val NONE = SensorSample(timestamp = 0L, present = false)

        /** Kept so older call sites still compile; it is the same absence. */
        val EMPTY = NONE
    }
}

data class NodeStatus(
    val id: String,
    val name: String,
    val online: Boolean,
    val lastSeen: Long,
    val detail: String
)

/**
 * Where the Jetson says its video stream is, if it has said so at all.
 *
 * Every field is nullable for the same reason the sensor channels are: before
 * the Jetson boots nothing here is known, and a guessed address would send the
 * app knocking on a host that was never there.
 */
data class StreamInfo(
    val url: String? = null,
    val lanIp: String? = null,
    val port: Int? = null,
    val up: Boolean = false
) {
    val addressed: Boolean get() = !url.isNullOrBlank()

    companion object {
        val NONE = StreamInfo()
    }
}

data class FusionRationale(
    val visionSaid: String,
    val sensorsSaid: String,
    val conclusion: String,
    val visionContributed: Boolean,
    val sensorsContributed: Boolean
)

data class FireEvent(
    val id: String,
    val timestamp: Long,
    val level: AlarmLevel,
    val detections: List<Detection>,
    val sensors: SensorSample,
    @DrawableRes val frame: Int,
    val rationale: FusionRationale,
    val acknowledged: Boolean = false,
    val frameB64: String? = null
) {
    val topConfidence: Float get() = detections.maxOfOrNull { it.confidence } ?: 0f
}

data class SystemState(
    val level: AlarmLevel,
    val since: Long,
    val detections: List<Detection>,
    @DrawableRes val frame: Int,
    val sensors: SensorSample,
    val nodes: List<NodeStatus>,
    val fps: Float,
    val inferenceMs: Float,
    val rationale: FusionRationale,
    val acknowledged: Boolean,
    val frameB64: String? = null,
    /** When the edge last wrote this document, in epoch millis. */
    val updatedAt: Long? = null
) {
    /**
     * True when this level is old enough to be history rather than status.
     *
     * The edge heartbeats every five seconds. Twelve missed beats is not a
     * blip, it is a device that has stopped. A frozen level is worse than no
     * level: a stale ALERT teaches the reader to ignore the colour, and a stale
     * NORMAL says the house is fine when nothing has looked at it in hours.
     *
     * Absent stamps fall back to the sample clock, then to unknown, and unknown
     * counts as stale. Nothing else is safe to assume.
     */
    val stale: Boolean
        get() {
            val stamp = updatedAt ?: sensors.timestamp.takeIf { it > 0L } ?: return true
            return System.currentTimeMillis() - stamp > STATE_STALE_AFTER_MS
        }

    companion object {
        const val STATE_STALE_AFTER_MS = 60_000L
    }
}

data class Thresholds(
    val confidence: Float = 0.50f,
    val surfaceTempC: Float = 55f,
    /**
     * Percentage fall of Rs/R0 below the clean-air baseline that counts as gas.
     * This replaced a ppm threshold, which set a limit in a unit the system had
     * already decided it could not honestly produce.
     */
    val gasRisePctAlarm: Float = 15f,
    val notifyConfirmed: Boolean = true,
    val notifyAlert: Boolean = true,
    val notifyWatch: Boolean = false
)

enum class Sensitivity(
    val conf: Float,
    val recall: Float,
    val fprHard: Float,
    val fprNovel: Float,
    val fprOpen: Float
) {
    SENSITIVE(0.30f, 0.885f, 1.8f, 3.57f, 3.25f),

    STANDARD(0.50f, 0.840f, 1.2f, 1.53f, 2.75f),

    QUIET(0.70f, 0.736f, 0.4f, 1.02f, 1.25f);

    companion object {
        val DEFAULT = STANDARD

        fun nearest(conf: Float): Sensitivity =
            entries.minBy { kotlin.math.abs(it.conf - conf) }
    }
}
