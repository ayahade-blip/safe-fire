package com.safefire.monitor.ui.components

import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.safefire.monitor.data.AlarmLevel
import com.safefire.monitor.ui.visual

@Composable
fun Panel(
    modifier: Modifier = Modifier,
    accent: Color? = null,
    content: @Composable () -> Unit
) {
    Card(
        modifier = modifier.fillMaxWidth(),
        shape = RoundedCornerShape(22.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceContainer
        ),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp)
    ) {
        Box(
            Modifier
                .fillMaxWidth()
                .then(
                    if (accent != null) {
                        Modifier.border(1.dp, accent.copy(alpha = 0.35f), RoundedCornerShape(22.dp))
                    } else Modifier
                )
        ) { content() }
    }
}

@Composable
fun SectionLabel(text: String, modifier: Modifier = Modifier) {
    Text(
        text = text.uppercase(),
        style = MaterialTheme.typography.labelSmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = modifier.padding(start = 4.dp, bottom = 8.dp)
    )
}

@Composable
fun Pill(
    text: String,
    color: Color,
    modifier: Modifier = Modifier,
    icon: ImageVector? = null,
    filled: Boolean = false
) {
    Row(
        modifier
            .clip(CircleShape)
            .background(if (filled) color else color.copy(alpha = 0.14f))
            .padding(horizontal = 10.dp, vertical = 5.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(5.dp)
    ) {
        if (icon != null) {
            Icon(
                icon, null,
                tint = if (filled) Color.White else color,
                modifier = Modifier.size(13.dp)
            )
        }
        Text(
            text = text,
            style = MaterialTheme.typography.labelMedium,
            color = if (filled) Color.White else color
        )
    }
}

@Composable
fun LiveDot(label: String = "LIVE", color: Color = Color(0xFFFF4D4D)) {
    val t = rememberInfiniteTransition(label = "live")
    val a by t.animateFloat(
        0.35f, 1f,
        infiniteRepeatable(tween(900), RepeatMode.Reverse),
        label = "liveAlpha"
    )
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
        Box(
            Modifier
                .size(7.dp)
                .alpha(a)
                .background(color, CircleShape)
        )
        Text(
            text = label,
            style = MaterialTheme.typography.labelSmall,
            color = Color.White.copy(alpha = 0.92f)
        )
    }
}

@Composable
fun StatRow(label: String, value: String, valueColor: Color? = null) {
    Row(
        Modifier
            .fillMaxWidth()
            .padding(vertical = 7.dp),
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Text(
            label,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        Text(
            value,
            style = MaterialTheme.typography.titleMedium,
            color = valueColor ?: MaterialTheme.colorScheme.onSurface
        )
    }
}

@Composable
fun EmptyState(icon: ImageVector, title: String, body: String) {
    Column(
        Modifier
            .fillMaxWidth()
            .padding(vertical = 56.dp, horizontal = 32.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Icon(
            icon, null,
            tint = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.45f),
            modifier = Modifier.size(44.dp)
        )
        Text(
            title,
            style = MaterialTheme.typography.titleLarge,
            color = MaterialTheme.colorScheme.onSurface,
            modifier = Modifier.padding(top = 14.dp)
        )
        Text(
            body,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(top = 6.dp)
        )
    }
}


@Composable
fun Sparkline(
    values: List<Float>,
    color: Color,
    modifier: Modifier = Modifier,
    threshold: Float? = null,
    height: androidx.compose.ui.unit.Dp = 68.dp
) {
    val gridColor = MaterialTheme.colorScheme.outline

    Canvas(
        modifier
            .fillMaxWidth()
            .height(height)
    ) {
        if (values.size < 2) return@Canvas

        val lo = (values.min()).coerceAtMost(threshold ?: values.min())
        val hi = (values.max()).coerceAtLeast(threshold ?: values.max())
        val span = (hi - lo).takeIf { it > 0.0001f } ?: 1f
        val pad = span * 0.18f
        val minV = lo - pad
        val range = (hi + pad) - minV

        fun px(i: Int) = size.width * i / (values.size - 1).toFloat()
        fun py(v: Float) = size.height * (1f - (v - minV) / range)

        threshold?.let {
            val y = py(it)
            drawLine(
                color = gridColor,
                start = Offset(0f, y),
                end = Offset(size.width, y),
                strokeWidth = 1.dp.toPx(),
                pathEffect = PathEffect.dashPathEffect(floatArrayOf(8f, 10f))
            )
        }

        val line = Path().apply {
            moveTo(px(0), py(values[0]))
            for (i in 1 until values.size) lineTo(px(i), py(values[i]))
        }
        val fill = Path().apply {
            addPath(line)
            lineTo(size.width, size.height)
            lineTo(0f, size.height)
            close()
        }

        drawPath(
            path = fill,
            brush = Brush.verticalGradient(
                listOf(color.copy(alpha = 0.28f), color.copy(alpha = 0f))
            )
        )
        drawPath(
            path = line,
            color = color,
            style = Stroke(width = 2.dp.toPx(), cap = StrokeCap.Round)
        )
        drawCircle(color, radius = 3.2.dp.toPx(), center = Offset(px(values.lastIndex), py(values.last())))
    }
}

@Composable
fun ChannelChart(
    title: String,
    value: String,
    unit: String,
    values: List<Float>,
    color: Color,
    threshold: Float? = null,
    footnote: String? = null
) {
    Panel {
        Column(Modifier.padding(18.dp)) {
            Row(
                Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.Bottom
            ) {
                Column {
                    Text(
                        title,
                        style = MaterialTheme.typography.titleMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Row(verticalAlignment = Alignment.Bottom) {
                        Text(
                            value,
                            style = MaterialTheme.typography.displayMedium,
                            color = MaterialTheme.colorScheme.onSurface
                        )
                        Text(
                            unit,
                            style = MaterialTheme.typography.titleMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.padding(start = 4.dp, bottom = 6.dp)
                        )
                    }
                }
                Box(Modifier.padding(bottom = 6.dp)) {
                    Pill(text = title.take(14), color = color)
                }
            }

            Sparkline(
                values = values,
                color = color,
                threshold = threshold,
                modifier = Modifier.padding(top = 14.dp)
            )

            if (footnote != null) {
                Text(
                    footnote,
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(top = 10.dp)
                )
            }
        }
    }
}

@Composable
fun StatusSkeleton(modifier: Modifier = Modifier) {
    val t = rememberInfiniteTransition(label = "shimmer")
    val a by t.animateFloat(
        0.28f, 0.62f,
        infiniteRepeatable(tween(950), RepeatMode.Reverse),
        label = "shimmerAlpha"
    )

    @Composable
    fun Bar(width: Float, height: Int, shape: RoundedCornerShape = RoundedCornerShape(8.dp)) {
        Box(
            Modifier
                .fillMaxWidth(width)
                .height(height.dp)
                .alpha(a)
                .background(MaterialTheme.colorScheme.surfaceVariant, shape)
        )
    }

    Column(
        modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(14.dp)
    ) {
        Box(
            Modifier
                .padding(top = 24.dp)
                .size(232.dp)
                .alpha(a)
                .background(MaterialTheme.colorScheme.surfaceVariant, CircleShape)
        )
        Bar(0.72f, 16)
        Bar(0.40f, 12)
        Box(
            Modifier
                .padding(top = 10.dp)
                .fillMaxWidth()
                .aspectRatio(16f / 9f)
                .alpha(a)
                .clip(RoundedCornerShape(20.dp))
                .background(MaterialTheme.colorScheme.surfaceVariant)
        )
        Bar(1f, 96, RoundedCornerShape(22.dp))
    }
}
