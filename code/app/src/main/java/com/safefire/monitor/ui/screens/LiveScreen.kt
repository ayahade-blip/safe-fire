package com.safefire.monitor.ui.screens

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.VideocamOff
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
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.safefire.monitor.R
import com.safefire.monitor.data.Detection
import com.safefire.monitor.data.DetectionClass
import com.safefire.monitor.data.MjpegClient
import com.safefire.monitor.data.StreamInfo
import com.safefire.monitor.data.StreamStatus
import com.safefire.monitor.data.StreamUpdate
import com.safefire.monitor.data.SystemState
import com.safefire.monitor.ui.components.FrameView
import com.safefire.monitor.ui.components.FrameViewerDialog
import com.safefire.monitor.ui.components.Panel
import com.safefire.monitor.ui.components.SectionLabel
import com.safefire.monitor.ui.theme.BoxFlame
import com.safefire.monitor.ui.theme.BoxSmoke
import kotlinx.coroutines.launch
import com.safefire.monitor.ui.components.LiveDot
import com.safefire.monitor.ui.components.SensorStrip
import androidx.compose.ui.text.style.TextOverflow

/**
 * The live view.
 *
 * There are two different pictures in this system and conflating them was the
 * original sin of this screen. Firestore carries a still every few seconds so
 * the app has something to show from anywhere; the Jetson serves MJPEG over the
 * local network at the pipeline's own frame rate. Only the second one is live,
 * and only it is allowed to be called that.
 *
 * The still is kept as the fallback because it is the only picture available
 * when the phone is off the house network, but it is labelled for what it is.
 */
@Composable
fun LiveScreen(
    state: SystemState,
    stream: StreamInfo,
    onRefresh: suspend () -> Unit,
    contentPadding: PaddingValues
) {
    var refreshing by remember { mutableStateOf(false) }
    var zoomed by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    // Keyed on the URL so a Jetson that reboots onto a new address reconnects
    // instead of retrying the old one forever.
    val update: StreamUpdate by remember(stream.url) {
        MjpegClient.stream(stream.url)
    }.collectAsStateWithLifecycle(
        initialValue = StreamUpdate(
            if (stream.addressed) StreamStatus.Connecting else StreamStatus.NoAddress
        )
    )

    val status = update.status
    val watching = status is StreamStatus.Live

    Column(
        Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(contentPadding)
            .padding(horizontal = 16.dp)
    ) {
        // No section label above the video. The screen is already titled Live
        // view in the app bar, and repeating it pushed the picture down for a
        // word the reader had just read.
        Spacer(Modifier.height(4.dp))

        StreamSurface(
            update = update,
            detections = state.detections,
            fallback = {
                Box(Modifier.clickable { zoomed = true }) {
                    FrameView(
                        frame = state.frame,
                        detections = state.detections,
                        timestamp = state.since,
                        frameB64 = state.frameB64
                    )
                }
            }
        )

        StreamStatusLine(status)

        // The readings belong on this screen because a picture cannot say
        // whether the room is hot. Same live sample the status tiles use, and
        // the same rule about absence: a silent channel shows a dash.
        Spacer(Modifier.height(18.dp))
        SectionLabel(stringResource(R.string.live_readings))
        Panel {
            Box(Modifier.padding(horizontal = 16.dp, vertical = 14.dp)) {
                SensorStrip(readings = state.sensors.strip())
            }
        }

        // The hint only helps while there is nothing to watch. Once the picture
        // is running it is just an instruction for a problem that went away.
        if (!watching) {
            Spacer(Modifier.height(12.dp))
            Panel {
                // Panel hands its content no layout scope, so the column is ours.
                Column(Modifier.padding(16.dp)) {
                    Text(
                        stringResource(R.string.live_stream_hint),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    if (stream.lanIp != null) {
                        Spacer(Modifier.height(10.dp))
                        Text(
                            stringResource(R.string.live_source_jetson),
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                        Text(
                            stream.lanIp,
                            style = MaterialTheme.typography.titleSmall,
                            color = MaterialTheme.colorScheme.onSurface
                        )
                    }
                }
            }
        }

        if (zoomed) {
            FrameViewerDialog(
                frame = state.frame,
                detections = state.detections,
                timestamp = state.since,
                frameB64 = state.frameB64,
                onDismiss = { zoomed = false }
            )
        }

        Row(
            Modifier
                .fillMaxWidth()
                .padding(top = 12.dp, bottom = 20.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                stringResource(R.string.tap_to_zoom),
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            OutlinedButton(
                onClick = {
                    scope.launch {
                        refreshing = true
                        onRefresh()
                        refreshing = false
                    }
                },
                enabled = !refreshing,
                shape = RoundedCornerShape(14.dp)
            ) {
                if (refreshing) {
                    CircularProgressIndicator(
                        Modifier.size(16.dp),
                        strokeWidth = 2.dp,
                        color = MaterialTheme.colorScheme.primary
                    )
                } else {
                    Icon(Icons.Filled.Refresh, null, Modifier.size(18.dp))
                }
                Spacer(Modifier.size(8.dp))
                Text(stringResource(R.string.refresh))
            }
        }
    }
}

/**
 * The picture itself.
 *
 * Only a Live status may draw a frame. Reconnecting deliberately falls back to
 * the still rather than freezing the last streamed image, because a frozen
 * frame under a live label is indistinguishable from a working camera pointed
 * at a fire that has not started yet.
 */
@Composable
private fun StreamSurface(
    update: StreamUpdate,
    detections: List<Detection>,
    fallback: @Composable () -> Unit
) {
    val frame = update.frame
    if (update.status is StreamStatus.Live && frame != null) {
        val ratio = if (frame.height > 0) {
            frame.width.toFloat() / frame.height.toFloat()
        } else {
            1f
        }
        Box(
            Modifier
                .fillMaxWidth()
                .aspectRatio(ratio)
                .clip(RoundedCornerShape(20.dp))
                .background(Color.Black)
        ) {
            Image(
                bitmap = frame.asImageBitmap(),
                contentDescription = stringResource(R.string.live_view),
                modifier = Modifier.fillMaxSize(),
                contentScale = ContentScale.Fit
            )
            DetectionOverlay(detections)
            // The badge sits here and nowhere else. On this surface the claim is
            // true: these frames are arriving from the Jetson as they are made.
            Box(Modifier.align(Alignment.TopStart).padding(12.dp)) {
                LiveDot(label = stringResource(R.string.badge_live))
            }
        }
        return
    }

    if (update.status is StreamStatus.Connecting ||
        update.status is StreamStatus.Reconnecting
    ) {
        Box(
            Modifier
                .fillMaxWidth()
                .aspectRatio(1f)
                .clip(RoundedCornerShape(20.dp))
                .background(MaterialTheme.colorScheme.surfaceVariant),
            contentAlignment = Alignment.Center
        ) {
            CircularProgressIndicator(
                Modifier.size(28.dp),
                strokeWidth = 3.dp,
                color = MaterialTheme.colorScheme.primary
            )
        }
        return
    }

    fallback()
}

/** Detection boxes, matching the corner-tick convention already used by FrameView. */
@Composable
private fun DetectionOverlay(detections: List<Detection>) {
    if (detections.isEmpty()) return
    Canvas(Modifier.fillMaxSize()) {
        detections.forEach { d ->
            val colour = if (d.label == DetectionClass.FLAME) BoxFlame else BoxSmoke
            val left = d.x * size.width
            val top = d.y * size.height
            val w = d.w * size.width
            val h = d.h * size.height
            drawRect(
                color = colour,
                topLeft = Offset(left, top),
                size = Size(w, h),
                style = Stroke(width = 3f)
            )
            val tick = minOf(w, h) * 0.18f
            listOf(
                Offset(left, top) to Offset(left + tick, top),
                Offset(left, top) to Offset(left, top + tick),
                Offset(left + w, top) to Offset(left + w - tick, top),
                Offset(left + w, top) to Offset(left + w, top + tick),
                Offset(left, top + h) to Offset(left + tick, top + h),
                Offset(left, top + h) to Offset(left, top + h - tick),
                Offset(left + w, top + h) to Offset(left + w - tick, top + h),
                Offset(left + w, top + h) to Offset(left + w, top + h - tick)
            ).forEach { (a, b) ->
                drawLine(colour, a, b, strokeWidth = 6f)
            }
        }
    }
}

/** One honest line about what the picture above actually is. */
@Composable
private fun StreamStatusLine(status: StreamStatus) {
    val text: String
    val detail: String?
    val tone: Color

    when (status) {
        is StreamStatus.Live -> {
            text = stringResource(R.string.live_source_jetson)
            detail = stringResource(R.string.live_fps, "%.1f".format(status.fps)) +
                "   " +
                stringResource(
                    R.string.live_resolution,
                    status.width.toString(),
                    status.height.toString()
                )
            tone = MaterialTheme.colorScheme.primary
        }
        is StreamStatus.Connecting -> {
            text = stringResource(R.string.live_connecting)
            detail = null
            tone = MaterialTheme.colorScheme.onSurfaceVariant
        }
        is StreamStatus.Reconnecting -> {
            text = stringResource(R.string.live_reconnecting)
            detail = null
            tone = MaterialTheme.colorScheme.onSurfaceVariant
        }
        is StreamStatus.Failed -> {
            text = stringResource(R.string.live_open_failed)
            detail = status.reason
            tone = MaterialTheme.colorScheme.error
        }
        is StreamStatus.NoAddress -> {
            text = stringResource(R.string.live_no_stream)
            detail = null
            tone = MaterialTheme.colorScheme.onSurfaceVariant
        }
    }

    // A slow fade rather than a blink. The eye reads a pulsing indicator as
    // urgency, and the state of a video connection is not an emergency.
    val alpha by animateFloatAsState(
        targetValue = if (status is StreamStatus.Live) 1f else 0.72f,
        label = "streamStatusAlpha"
    )

    // One line, two ends: what the connection is doing on the left, the numbers
    // that only matter once it is working on the right. Stacking them put a
    // second-priority detail directly under the video, where the eye lands.
    Row(
        Modifier
            .fillMaxWidth()
            .padding(top = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            if (status is StreamStatus.NoAddress || status is StreamStatus.Failed) {
                Icon(
                    Icons.Filled.VideocamOff,
                    contentDescription = null,
                    tint = tone,
                    modifier = Modifier.size(15.dp)
                )
                Spacer(Modifier.size(7.dp))
            }
            Text(
                text,
                style = MaterialTheme.typography.labelLarge,
                color = tone.copy(alpha = alpha),
                maxLines = 1,
                overflow = TextOverflow.Ellipsis
            )
        }
        if (detail != null) {
            Text(
                detail,
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = TextAlign.End,
                maxLines = 1
            )
        }
    }
}
