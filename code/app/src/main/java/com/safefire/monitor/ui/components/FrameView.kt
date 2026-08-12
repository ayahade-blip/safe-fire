package com.safefire.monitor.ui.components

import android.graphics.BitmapFactory
import android.util.Base64
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.gestures.detectTransformGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.ZoomIn
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import com.safefire.monitor.data.Detection
import com.safefire.monitor.data.DetectionClass
import com.safefire.monitor.ui.asClock
import com.safefire.monitor.ui.theme.BoxFlame
import com.safefire.monitor.ui.theme.BoxSmoke

@Composable
fun FrameView(
    frame: Int,
    detections: List<Detection>,
    timestamp: Long,
    modifier: Modifier = Modifier,
    showChrome: Boolean = true,
    cornerRadius: Int = 20,
    frameB64: String? = null
) {
    val live: ImageBitmap? = remember(frameB64) {
        frameB64?.let {
            runCatching {
                val bytes = Base64.decode(it, Base64.DEFAULT)
                BitmapFactory.decodeByteArray(bytes, 0, bytes.size)?.asImageBitmap()
            }.getOrNull()
        }
    }

    BoxWithConstraints(
        modifier
            .fillMaxWidth()
            .aspectRatio(16f / 9f)
            .clip(RoundedCornerShape(cornerRadius.dp))
            .background(Color.Black)
    ) {
        val frameW = maxWidth
        val frameH = maxHeight

        if (live != null) {
            Image(
                bitmap = live,
                contentDescription = null,
                contentScale = ContentScale.Crop,
                modifier = Modifier.fillMaxSize()
            )
        } else {
            Image(
                painter = painterResource(frame),
                contentDescription = null,
                contentScale = ContentScale.Crop,
                modifier = Modifier.fillMaxSize()
            )
        }

        Box(
            Modifier
                .fillMaxSize()
                .background(
                    Brush.verticalGradient(
                        0.0f to Color.Transparent,
                        0.62f to Color.Transparent,
                        1.0f to Color.Black.copy(alpha = 0.62f)
                    )
                )
        )

        Canvas(Modifier.fillMaxSize()) {
            detections.forEach { d ->
                val color = if (d.label == DetectionClass.FLAME) BoxFlame else BoxSmoke
                val left = d.x * size.width
                val top = d.y * size.height
                val w = d.w * size.width
                val h = d.h * size.height
                val stroke = size.minDimension * 0.007f

                drawRoundRect(
                    color = color,
                    topLeft = Offset(left, top),
                    size = Size(w, h),
                    cornerRadius = CornerRadius(8f, 8f),
                    style = Stroke(width = stroke)
                )

                val tick = minOf(w, h) * 0.20f
                listOf(
                    Offset(left, top) to Offset(left + tick, top),
                    Offset(left, top) to Offset(left, top + tick),
                    Offset(left + w, top) to Offset(left + w - tick, top),
                    Offset(left + w, top) to Offset(left + w, top + tick),
                    Offset(left, top + h) to Offset(left + tick, top + h),
                    Offset(left, top + h) to Offset(left, top + h - tick),
                    Offset(left + w, top + h) to Offset(left + w - tick, top + h),
                    Offset(left + w, top + h) to Offset(left + w, top + h - tick)
                ).forEach { (a, b) -> drawLine(color, a, b, strokeWidth = stroke * 2.2f) }
            }
        }

        detections.forEach { d ->
            val color = if (d.label == DetectionClass.FLAME) BoxFlame else BoxSmoke
            val labelY = (d.y * frameH.value - 17f).coerceAtLeast(0f)
            Text(
                text = "${d.label.name.lowercase()} ${"%.2f".format(d.confidence)}",
                color = Color.White,
                fontSize = 10.5.sp,
                fontWeight = FontWeight.SemiBold,
                modifier = Modifier
                    .offset(x = (d.x * frameW.value).dp, y = labelY.dp)
                    .background(color, RoundedCornerShape(4.dp))
                    .padding(horizontal = 6.dp, vertical = 2.dp)
            )
        }

        if (showChrome) {
            Row(
                Modifier
                    .align(Alignment.BottomStart)
                    .fillMaxWidth()
                    .padding(horizontal = 12.dp, vertical = 10.dp),
                // The badge that used to sit here said LIVE over a frame
                // that arrives every few seconds. The timestamp next to it was
                // already telling the truth, so only the badge had to go.
                horizontalArrangement = Arrangement.End,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = timestamp.asClock(),
                    color = Color.White.copy(alpha = 0.92f),
                    style = MaterialTheme.typography.labelMedium
                )
            }
        }
    }
}

@Composable
fun FrameViewerDialog(
    frame: Int,
    detections: List<Detection>,
    timestamp: Long,
    frameB64: String?,
    onDismiss: () -> Unit
) {
    var scale by remember { mutableFloatStateOf(1f) }
    var offsetX by remember { mutableFloatStateOf(0f) }
    var offsetY by remember { mutableFloatStateOf(0f) }

    fun reset() { scale = 1f; offsetX = 0f; offsetY = 0f }

    Dialog(
        onDismissRequest = onDismiss,
        properties = DialogProperties(usePlatformDefaultWidth = false)
    ) {
        Box(
            Modifier
                .fillMaxSize()
                .background(Color.Black.copy(alpha = 0.96f))
                .pointerInput(Unit) {
                    detectTapGestures(
                        onDoubleTap = { if (scale > 1f) reset() else scale = 2.5f }
                    )
                }
                .pointerInput(Unit) {
                    detectTransformGestures { _, pan, zoom, _ ->
                        scale = (scale * zoom).coerceIn(1f, 6f)
                        if (scale > 1f) {
                            offsetX += pan.x
                            offsetY += pan.y
                        } else {
                            offsetX = 0f; offsetY = 0f
                        }
                    }
                },
            contentAlignment = Alignment.Center
        ) {
            Box(
                Modifier.graphicsLayer(
                    scaleX = scale, scaleY = scale,
                    translationX = offsetX, translationY = offsetY
                )
            ) {
                FrameView(
                    frame = frame,
                    detections = detections,
                    timestamp = timestamp,
                    showChrome = false,
                    cornerRadius = 0,
                    frameB64 = frameB64
                )
            }

            IconButton(
                onClick = onDismiss,
                modifier = Modifier
                    .align(Alignment.TopEnd)
                    .padding(14.dp)
            ) {
                Icon(Icons.Filled.Close, null, tint = Color.White)
            }

            Text(
                text = timestamp.asClock(),
                style = MaterialTheme.typography.labelMedium,
                color = Color.White.copy(alpha = 0.75f),
                modifier = Modifier
                    .align(Alignment.BottomCenter)
                    .padding(bottom = 26.dp)
            )

            if (scale <= 1f) {
                Icon(
                    Icons.Filled.ZoomIn, null,
                    tint = Color.White.copy(alpha = 0.55f),
                    modifier = Modifier
                        .align(Alignment.BottomStart)
                        .padding(20.dp)
                )
            }
        }
    }
}
