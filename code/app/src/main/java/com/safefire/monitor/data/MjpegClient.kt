package com.safefire.monitor.data

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.os.SystemClock
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.buffer
import kotlinx.coroutines.flow.callbackFlow
import java.io.InputStream
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.atomic.AtomicReference

/**
 * What the live view is currently able to say about the stream.
 *
 * [Live] is the only state that carries a frame. Every other state clears it,
 * because a paused last frame rendered under the word "live" is the same class
 * of lie as printing 0 for a sensor that never answered.
 */
sealed interface StreamStatus {
    /** The Jetson has not advertised an address yet. */
    data object NoAddress : StreamStatus
    data object Connecting : StreamStatus
    data class Live(val fps: Float, val width: Int, val height: Int) : StreamStatus
    data class Reconnecting(val attempt: Int) : StreamStatus
    data class Failed(val reason: String) : StreamStatus
}

data class StreamUpdate(val status: StreamStatus, val frame: Bitmap? = null)

/**
 * Reads `multipart/x-mixed-replace` from the Jetson over the local network.
 *
 * Written against java.net rather than a library because the project has no HTTP
 * dependency and one MJPEG reader does not justify adding one.
 *
 * The socket read is blocking and does not observe coroutine cancellation, so
 * the loop runs on its own thread and cancellation disconnects the connection
 * underneath it. Without that the thread would survive the screen that started
 * it and keep pulling frames from the Jetson for nothing.
 */
object MjpegClient {

    private const val CONNECT_TIMEOUT_MS = 4_000
    /** Longer than the Jetson's slowest observed frame interval, short enough to notice a dead link. */
    private const val READ_TIMEOUT_MS = 8_000
    private const val MAX_PART_BYTES = 4 * 1024 * 1024
    private const val BACKOFF_START_MS = 1_000L
    private const val BACKOFF_MAX_MS = 15_000L

    fun stream(url: String?): Flow<StreamUpdate> = callbackFlow {
        if (url.isNullOrBlank()) {
            trySend(StreamUpdate(StreamStatus.NoAddress))
            awaitClose { }
            return@callbackFlow
        }

        val live = AtomicReference<HttpURLConnection?>(null)
        val stop = AtomicReference(false)

        val worker = Thread({
            var attempt = 0
            var backoff = BACKOFF_START_MS

            while (!stop.get()) {
                trySend(
                    StreamUpdate(
                        if (attempt == 0) StreamStatus.Connecting
                        else StreamStatus.Reconnecting(attempt)
                    )
                )

                var conn: HttpURLConnection? = null
                try {
                    conn = (URL(url).openConnection() as HttpURLConnection).apply {
                        connectTimeout = CONNECT_TIMEOUT_MS
                        readTimeout = READ_TIMEOUT_MS
                        requestMethod = "GET"
                        // The frames are already JPEG; a content encoding here would
                        // only cost the Nano CPU it does not have to spare.
                        setRequestProperty("Accept-Encoding", "identity")
                        setRequestProperty("Connection", "close")
                    }
                    live.set(conn)

                    val code = conn.responseCode
                    if (code != HttpURLConnection.HTTP_OK) {
                        throw IllegalStateException("HTTP $code")
                    }

                    val boundary = boundaryOf(conn.contentType)
                        ?: throw IllegalStateException("no boundary in ${conn.contentType}")

                    // A frame arrived, so the next failure is a fresh one.
                    attempt = 0
                    backoff = BACKOFF_START_MS
                    readParts(conn.inputStream, boundary, stop) { bmp, fps ->
                        trySend(
                            StreamUpdate(
                                StreamStatus.Live(fps, bmp.width, bmp.height),
                                bmp
                            )
                        )
                    }
                    // A clean end of stream still means the picture stopped.
                    if (!stop.get()) throw IllegalStateException("stream ended")
                } catch (t: Throwable) {
                    if (stop.get()) break
                    attempt += 1
                    trySend(StreamUpdate(StreamStatus.Reconnecting(attempt)))
                    if (attempt >= 4) {
                        trySend(
                            StreamUpdate(
                                StreamStatus.Failed(t.message ?: t.javaClass.simpleName)
                            )
                        )
                    }
                    try {
                        Thread.sleep(backoff)
                    } catch (ie: InterruptedException) {
                        break
                    }
                    backoff = minOf(backoff * 2, BACKOFF_MAX_MS)
                } finally {
                    live.set(null)
                    try {
                        conn?.disconnect()
                    } catch (ignored: Throwable) {
                    }
                }
            }
            close()
        }, "mjpeg-reader")

        worker.isDaemon = true
        worker.start()

        awaitClose {
            stop.set(true)
            // Disconnect first: it is what actually unblocks the read. The
            // interrupt only covers the backoff sleep.
            try {
                live.get()?.disconnect()
            } catch (ignored: Throwable) {
            }
            worker.interrupt()
        }
        // Conflated, so a UI slower than the Jetson drops frames instead of
        // queueing them into a growing backlog of stale pictures.
    }.buffer(Channel.CONFLATED)

    /** `multipart/x-mixed-replace; boundary=safefire`, quoted or not. */
    private fun boundaryOf(contentType: String?): String? {
        val ct = contentType ?: return null
        val marker = ct.indexOf("boundary=", ignoreCase = true)
        if (marker < 0) return null
        var value = ct.substring(marker + "boundary=".length).trim()
        val semi = value.indexOf(';')
        if (semi >= 0) value = value.substring(0, semi).trim()
        value = value.trim('"')
        return value.ifBlank { null }
    }

    /**
     * Walk the parts, handing each decoded frame to [onFrame].
     *
     * Content-Length is honoured when the server sends it, which the Jetson
     * server does. The scan fallback exists so a different MJPEG source still
     * renders rather than showing nothing.
     */
    private fun readParts(
        input: InputStream,
        boundary: String,
        stop: AtomicReference<Boolean>,
        onFrame: (Bitmap, Float) -> Unit
    ) {
        val reader = PartReader(input)
        val delimiter = "--$boundary"
        var frames = 0
        var windowStart = SystemClock.elapsedRealtime()
        var fps = 0f

        while (!stop.get()) {
            // Skip forward to the next part marker.
            var line = reader.readLine() ?: return
            while (!line.startsWith(delimiter)) {
                line = reader.readLine() ?: return
            }
            if (line.startsWith("$delimiter--")) return

            var length = -1
            while (true) {
                val header = reader.readLine() ?: return
                if (header.isEmpty()) break
                val colon = header.indexOf(':')
                if (colon > 0 &&
                    header.substring(0, colon).trim().equals("Content-Length", true)
                ) {
                    length = header.substring(colon + 1).trim().toIntOrNull() ?: -1
                }
            }

            val body = if (length in 1..MAX_PART_BYTES) {
                reader.readExactly(length)
            } else {
                reader.readUntilBoundary(delimiter)
            } ?: return

            val bmp = BitmapFactory.decodeByteArray(body, 0, body.size)
            if (bmp != null) {
                frames += 1
                val now = SystemClock.elapsedRealtime()
                val span = now - windowStart
                if (span >= 1_000) {
                    fps = frames * 1000f / span
                    frames = 0
                    windowStart = now
                }
                onFrame(bmp, fps)
            }
        }
    }

    /**
     * Byte-level reader.
     *
     * A BufferedReader cannot be used here: it decodes characters, and the JPEG
     * payload that follows the headers is not text. Header lines are read one
     * byte at a time, which is cheap because they are short, and the body is
     * read as bytes.
     */
    private class PartReader(private val input: InputStream) {
        private val line = StringBuilder(96)

        fun readLine(): String? {
            line.setLength(0)
            while (true) {
                val b = input.read()
                if (b < 0) return if (line.isEmpty()) null else line.toString()
                if (b == '\n'.code) {
                    if (line.isNotEmpty() && line[line.length - 1] == '\r') {
                        line.setLength(line.length - 1)
                    }
                    return line.toString()
                }
                line.append(b.toChar())
                if (line.length > 8192) return line.toString()
            }
        }

        fun readExactly(n: Int): ByteArray? {
            val out = ByteArray(n)
            var read = 0
            while (read < n) {
                val got = input.read(out, read, n - read)
                if (got < 0) return null
                read += got
            }
            return out
        }

        /** Fallback for a server that omits Content-Length. */
        fun readUntilBoundary(delimiter: String): ByteArray? {
            val needle = ("\r\n" + delimiter).toByteArray(Charsets.ISO_8859_1)
            val out = java.io.ByteArrayOutputStream(64 * 1024)
            var matched = 0
            while (out.size() <= MAX_PART_BYTES) {
                val b = input.read()
                if (b < 0) return null
                if (b == (needle[matched].toInt() and 0xFF)) {
                    matched += 1
                    if (matched == needle.size) return out.toByteArray()
                } else {
                    if (matched > 0) {
                        out.write(needle, 0, matched)
                        matched = 0
                        if (b == (needle[0].toInt() and 0xFF)) matched = 1 else out.write(b)
                    } else {
                        out.write(b)
                    }
                }
            }
            return null
        }
    }
}
