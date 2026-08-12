# -*- coding: utf-8 -*-
"""SAFE-Fire - the live LAN view, served from frames the detector already has.

The phone shows what the camera sees, over the local network, without a second
camera handle and without taking anything from the inference budget.

WHY THIS SERVER NEVER OPENS THE CAMERA
    nvarguscamerasrc takes an Argus capture session against sensor 0, and the
    Nano's Argus daemon grants one session per sensor. A second VideoCapture on
    the same pipeline fails at isOpened(). safefire_run.py owns the camera; this
    module is handed frames that were already captured and already run through
    the detector, and republishes them. There is no code path in this file that
    opens a device.

WHY THE ENCODE IS ON A THREAD AND NOT IN THE FRAME LOOP
    Measured on this board: doing the resize, JPEG encode and base64 inline on
    the publishing frames cost about 350 ms each. Median and p99 were untouched
    at 61.1 and 63.2 ms, but the MEAN rose from 61.0 to 67.9 and throughput fell
    from 16.4 to 14.7 fps. A handful of very slow frames is exactly the shape a
    fire detector must not have, so publish.py moved that work to a worker.
    This module makes the same trade for the same reason: offer() assigns a
    reference, one encoder thread does the pixels.

ONE ENCODE PER FRAME, WHATEVER THE CLIENT COUNT
    Client threads never encode. They wait on a single JPEG slot and write the
    newest bytes they have not sent yet. Two phones cost the Jetson exactly what
    one phone costs; the second one only costs Wi-Fi.

A SLOW CLIENT IS THE CLIENT'S PROBLEM, NEVER THE DETECTOR'S
    The slot holds one frame, newest wins, so a client that falls behind skips
    what it missed instead of accumulating a backlog. Writes happen outside the
    lock on immutable bytes, the socket has a send timeout, and a client that
    trips it is dropped. MAX_CLIENTS bounds threads and memory on a 2 GB board.
    When the last client leaves, offer() returns on a single integer compare and
    the encoder blocks, so an unwatched stream costs the board nothing.

    Usage
        python3 stream_server.py                  self test, synthetic frames
        python3 stream_server.py --port 8091      same, on another port
        python3 stream_server.py --boxes          burn the boxes in as well
"""
from __future__ import print_function

import argparse
import ctypes
import http.server
import json
import os
import socket
import socketserver
import sys
import threading
import time

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from publish import lan_ip                                   # noqa: E402

BOUNDARY = "safefire"                    # fixed by the app contract, not a taste
PATH_STREAM = "/stream.mjpg"
PATH_SNAPSHOT = "/snapshot.jpg"
PATH_HEALTH = "/health"

PORT_DEFAULT = 8090
SIZE_DEFAULT = (480, 360)                # 4:3, the camera's own shape, see below
QUALITY_DEFAULT = 70
FPS_CAP_DEFAULT = 5.0

# 25 percent of one of four cores. The encoder measures itself and slows down
# rather than exceed this, so the worst case is a slower stream and never a
# slower detector.
CPU_BUDGET_MS_PER_S = 250.0

MAX_CLIENTS = 3                          # bounds threads and sockets on 2 GB
MAX_BOXES = 8                            # the publisher caps at 8 too
CLIENT_STACK_BYTES = 512 * 1024
SOCKET_TIMEOUT_S = 10.0                  # a stalled write must raise, not park
REQUEST_TIMEOUT_S = 15.0
CLIENT_IDLE_LIMIT_S = 20.0               # no frames for this long, drop the client

# The camera is 640x480. publish.py resizes to 640x360, which squashes the
# picture vertically by 0.75 and puts every normalised box in the wrong place.
# The stream keeps 4:3 so the overlay lands on the object.


def _renice(delta):
    """Lower this thread's scheduling priority. The detector always wins.

    A positive nice value needs no privilege. setpriority with PRIO_PROCESS and
    a thread id applies to that thread alone on Linux, where a thread is a task.
    The syscall number is the aarch64 SYS_gettid; if it is wrong on this L4T the
    call fails and we simply do not renice, which is why nothing is raised.
    """
    try:
        libc = ctypes.CDLL("libc.so.6", use_errno=True)
        tid = libc.syscall(178)
        os.setpriority(os.PRIO_PROCESS, tid, delta)
    except Exception:
        pass


def _dets_header(boxes):
    """label,conf,x,y,w,h per box, semicolon separated, or None when empty.

    Sent as an optional part header so the app can draw boxes that belong to the
    frame it is looking at, instead of to whatever Firestore last wrote. An
    HTTP parser that does not know the header reads past it, so this costs a
    client that ignores it nothing.
    """
    if not boxes:
        return None
    return ";".join("%s,%.3f,%.4f,%.4f,%.4f,%.4f" % b for b in boxes)


def _draw(img, boxes):
    """Burn the boxes into the streamed copy. Off by default.

    The app overlays its own boxes from the header, so drawing here as well
    would double them. This exists for curl, VLC and the browser page, where
    there is nothing to overlay with.
    """
    h, w = img.shape[:2]
    for label, conf, x, y, bw, bh in boxes:
        x1, y1 = int(x * w), int(y * h)
        x2, y2 = int((x + bw) * w), int((y + bh) * h)
        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 200, 255), 2)
        cv2.putText(img, "%s %.2f" % (label, conf), (x1, max(12, y1 - 5)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 200, 255), 1, cv2.LINE_AA)


# --------------------------------------------------------------------- the hub

class FrameHub(object):
    """One latest-frame slot, one encoder, one HTTP server, many readers."""

    def __init__(self, size=SIZE_DEFAULT, quality=QUALITY_DEFAULT,
                 fps_cap=FPS_CAP_DEFAULT, port=PORT_DEFAULT, bind="",
                 net=640, pad=0, src_size=(640, 480), names=None,
                 draw_boxes=False, max_clients=MAX_CLIENTS):
        self.size = (int(size[0]), int(size[1]))
        self.quality = int(quality)
        self.fps_cap = float(fps_cap)
        self.fps_effective = float(fps_cap)
        self.port = int(port)
        self.bind = bind
        self.path = PATH_STREAM
        self.host = None
        self.net = int(net)
        self.pad = int(pad)
        self.src_w, self.src_h = int(src_size[0]), int(src_size[1])
        self.names = list(names) if names else []
        self.draw_boxes = bool(draw_boxes)
        self.max_clients = int(max_clients)

        # Read lock free by offer() on the hot path. Under the GIL that read is
        # atomic; the only consequence of the race is noticing a connect or a
        # disconnect one frame late.
        self.clients = 0

        self._lock = threading.Lock()
        self._in_cond = threading.Condition(self._lock)    # producer -> encoder
        self._out_cond = threading.Condition(self._lock)   # encoder -> clients
        self._raw = None                 # newest frame offered, by reference
        self._raw_dets = None
        self._in_seq = 0
        self._jpeg = None                # newest encoded frame, immutable bytes
        self._jpeg_hdr = None
        self._out_seq = 0
        self._enc_at = []                # completion times, for the served rate

        self._last_offer = 0.0
        self._min_period = 1.0 / max(0.5, self.fps_cap)
        self._started_at = time.time()
        self._stop = threading.Event()
        self._enc = None
        self._srv = None
        self._srv_thread = None
        self.stats = {"accepted": 0, "encoded": 0, "served": 0, "contended": 0,
                      "errors": 0, "client_errors": 0, "rejected": 0,
                      "bytes": 0, "peak_clients": 0,
                      "encode_ms_ema": None, "encode_ms_max": 0.0,
                      "last_error": None}

    # -- lifecycle --------------------------------------------------------

    def start(self):
        """Bind the port and start the two threads.

        The server is constructed first because that is the step that can fail,
        and failing before any thread exists keeps the caller's error path
        trivial: catch, report, run without a stream.
        """
        if self._srv is not None:
            return
        self._stop.clear()
        self._srv = _Server((self.bind, self.port), self)
        self.host = lan_ip()
        self._enc = threading.Thread(target=self._encode_loop)
        self._enc.daemon = True
        self._enc.start()
        self._srv_thread = threading.Thread(
            target=self._srv.serve_forever, kwargs={"poll_interval": 0.3})
        self._srv_thread.daemon = True
        self._srv_thread.start()

    def stop(self):
        """Wake everything that is waiting, then close the listening socket."""
        self._stop.set()
        with self._in_cond:
            self._in_cond.notify_all()
        with self._out_cond:
            self._out_cond.notify_all()
        if self._srv is not None:
            try:
                self._srv.shutdown()          # returns once serve_forever exits
            except Exception:
                pass
            try:
                self._srv.server_close()
            except Exception:
                pass
            self._srv = None
        for t in (self._enc, self._srv_thread):
            if t is not None:
                t.join(timeout=2.0)
        self._enc = self._srv_thread = None
        # Client threads are daemons and poll stopping() once a second, so they
        # unwind on their own rather than being joined one by one here.

    def stopping(self):
        return self._stop.is_set()

    def url(self, host=None):
        return "http://%s:%d%s" % (host or self.host or lan_ip() or "127.0.0.1",
                                   self.port, self.path)

    # -- producer side ----------------------------------------------------

    def offer(self, frame, dets=None):
        """Hand over the frame the detector just finished with.

        This is the only function called from the frame loop, and it is written
        to be boring. Nobody watching: one attribute read and a compare, then
        gone. Somebody watching: a clock read, a compare, and on the frames that
        pass the rate gate a non blocking lock acquire plus three assignments.
        No encode, no image allocation, no socket, nothing that can block.

        The frame is shared by reference, not copied, which is safe because
        nothing downstream writes into it: preprocess() copies out of it into
        the preallocated canvas, and pub.submit() already shares the same
        reference with the publisher's worker. If cap.read() turns out to
        recycle its buffer the worst case is an occasional torn frame in the
        STREAM; the detector already consumed the pixels it needed.
        """
        if self.clients <= 0:
            return False
        now = time.time()
        if now - self._last_offer < self._min_period:
            return False
        # Try, never wait. The lock is only ever held for a few assignments, so
        # a miss means the encoder is mid handover, and dropping one frame from
        # the stream is always cheaper than making the detector queue for it.
        if not self._lock.acquire(False):
            self.stats["contended"] += 1
            return False
        try:
            self._last_offer = now
            self._raw = frame
            self._raw_dets = dets
            self._in_seq += 1
            self.stats["accepted"] += 1
            # We hold the lock this condition wraps, so notify() is legal here
            # even though the acquire did not go through the with statement.
            self._in_cond.notify()
        finally:
            self._lock.release()
        return True

    # -- encoder ----------------------------------------------------------

    def _encode_loop(self):
        _renice(10)
        last = 0
        while not self._stop.is_set():
            with self._in_cond:
                while self._in_seq == last and not self._stop.is_set():
                    self._in_cond.wait(0.5)
                if self._stop.is_set():
                    return
                frame, dets, last = self._raw, self._raw_dets, self._in_seq
                self._raw = None            # do not pin a capture buffer here
                self._raw_dets = None
            if frame is None:
                continue
            boxes = self._norm_boxes(dets)
            t0 = time.time()
            try:
                small = cv2.resize(frame, self.size, interpolation=cv2.INTER_AREA)
                if self.draw_boxes and boxes:
                    _draw(small, boxes)
                ok, buf = cv2.imencode(".jpg", small,
                                       [int(cv2.IMWRITE_JPEG_QUALITY), self.quality])
                if not ok:
                    continue
                jpeg = buf.tobytes()
            except Exception as e:
                self.stats["errors"] += 1
                self.stats["last_error"] = "encode: %s" % e
                continue
            ms = (time.time() - t0) * 1000.0
            hdr = _dets_header(boxes)
            now = time.time()
            with self._out_cond:
                self._jpeg = jpeg           # bytes, immutable, safe to hand out
                self._jpeg_hdr = hdr
                self._out_seq += 1
                self.stats["encoded"] += 1
                self.stats["bytes"] = len(jpeg)
                ema = self.stats["encode_ms_ema"]
                self.stats["encode_ms_ema"] = ms if ema is None else 0.9 * ema + 0.1 * ms
                if ms > self.stats["encode_ms_max"]:
                    self.stats["encode_ms_max"] = ms
                self._enc_at.append(now)
                if len(self._enc_at) > 30:
                    del self._enc_at[0]
                self._out_cond.notify_all()
            self._apply_budget()

    def _apply_budget(self):
        """Derive the frame period from what the encode actually costs.

        The configured cap binds while encoding is cheap. If it turns out
        expensive the budget binds instead and the stream quietly drops to a
        lower rate, which is the whole point: the failure mode is a slower
        video, never a slower detector. /health reports which one is binding.
        """
        ema = self.stats["encode_ms_ema"]
        fps = self.fps_cap
        if ema:
            fps = min(fps, CPU_BUDGET_MS_PER_S / ema)
        fps = max(0.5, fps)
        self.fps_effective = fps
        self._min_period = 1.0 / fps

    def _norm_boxes(self, dets):
        """Detector rows to boxes normalised onto the streamed image.

        Same letterbox correction the publisher uses, so a box sits in the same
        place in the stream as in the cloud snapshot. The canvas is NET wide and
        the frame occupies rows [pad, pad + src_h), so x divides by NET and y
        has the pad removed before dividing by the source height.
        """
        if dets is None or len(dets) == 0:
            return []
        out = []
        for r in dets[:MAX_BOXES]:
            cls = int(r[5])
            label = self.names[cls] if cls < len(self.names) else "obj"
            out.append((label, float(r[4]),
                        float(max(0.0, r[0])) / self.net,
                        float(max(0.0, r[1] - self.pad)) / self.src_h,
                        float(r[2] - r[0]) / self.net,
                        float(r[3] - r[1]) / self.src_h))
        return out

    # -- consumer side ----------------------------------------------------

    def add_client(self):
        with self._lock:
            if self.clients >= self.max_clients:
                self.stats["rejected"] += 1
                return False
            self.clients += 1
            if self.clients > self.stats["peak_clients"]:
                self.stats["peak_clients"] = self.clients
            return True

    def remove_client(self):
        with self._lock:
            if self.clients > 0:
                self.clients -= 1

    def out_seq(self):
        with self._lock:
            return self._out_seq

    def wait_frame(self, last_seq, timeout=1.0):
        """The newest frame this caller has not sent, or None on timeout.

        Latest wins. A client that fell behind gets the current frame and never
        learns about the ones in between, which is the same policy as the
        publisher's single slot queue and is there for the same reason: a
        backlog would show the phone a picture of the past while claiming to be
        live. The bytes are immutable, so the caller writes them to its socket
        with the lock released.
        """
        with self._out_cond:
            if self._out_seq == last_seq:
                self._out_cond.wait(timeout)
            if self._out_seq == last_seq or self._jpeg is None:
                return None
            return self._out_seq, self._jpeg, self._jpeg_hdr

    def count_served(self, n):
        with self._lock:
            self.stats["served"] += n

    def health(self):
        """The document GET /health returns.

        up, fps, w, h and clients are the fields the app reads. The rest is the
        affordability instrumentation: it is how the cost of this channel gets
        reported as its own line rather than disappearing into the detector's
        numbers.
        """
        with self._lock:
            clients = self.clients
            fps = self._fps_locked()
            s = dict(self.stats)
        ema = s["encode_ms_ema"]
        return {
            "up": not self._stop.is_set(),
            "fps": round(fps, 2),
            "w": self.size[0],
            "h": self.size[1],
            "clients": clients,
            "fpsCap": round(self.fps_cap, 2),
            "fpsEffective": round(self.fps_effective, 2),
            "quality": self.quality,
            "accepted": s["accepted"],
            "encoded": s["encoded"],
            "served": s["served"],
            "rejected": s["rejected"],
            "contended": s["contended"],
            "clientErrors": s["client_errors"],
            "errors": s["errors"],
            "bytes": s["bytes"],
            "encodeMsEma": None if ema is None else round(ema, 2),
            "encodeMsMax": round(s["encode_ms_max"], 2),
            "peakClients": s["peak_clients"],
            "uptimeS": int(time.time() - self._started_at),
        }

    def _fps_locked(self):
        """Delivered rate over the last 30 encodes. Zero when nothing is flowing."""
        t = self._enc_at
        if len(t) < 2 or (time.time() - t[-1]) > 3.0:
            return 0.0
        span = t[-1] - t[0]
        return (len(t) - 1) / span if span > 0 else 0.0

    def node_fields(self, up=True):
        """The nodes/jetson fields that advertise this stream.

        publish.py re-detects the address on every heartbeat, so this is only
        the shape. Kept here so the two files agree on the field names.
        """
        ip = lan_ip()
        return {"streamUrl": self.url(ip) if ip else None,
                "streamPort": self.port,
                "lanIp": ip,
                "streamUp": bool(up and ip)}


# ------------------------------------------------------------------- transport

class _Handler(http.server.BaseHTTPRequestHandler):

    protocol_version = "HTTP/1.1"
    server_version = "SafeFireStream/1.0"
    timeout = REQUEST_TIMEOUT_S

    # BaseHTTPRequestHandler writes a line to stderr for every request. That
    # console belongs to the detector, and a phone reconnecting on a weak link
    # would scroll its output away.
    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == PATH_HEALTH:
            self._health()
        elif path == PATH_STREAM:
            self._stream()
        elif path == PATH_SNAPSHOT:
            self._snapshot()
        elif path in ("/", "/index.html"):
            self._index()
        else:
            self._plain(404, "not found\n")

    # -- replies ----------------------------------------------------------

    def _send(self, code, ctype, body):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store, no-cache, private")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def _plain(self, code, text):
        self._send(code, "text/plain; charset=utf-8", text.encode("utf-8"))

    def _health(self):
        body = json.dumps(self.server.hub.health()).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store, no-cache, private")
        # The app fetches this from a WebView-free client, but a browser tab on
        # the laptop is the fastest way to read it, so do not make it fight CORS.
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def _index(self):
        """A page with one img tag. This is the whole camera-off test rig."""
        hub = self.server.hub
        html = ("<!doctype html><meta charset=utf-8>"
                "<title>SAFE-Fire stream</title>"
                "<body style='margin:0;background:#0A0E14;color:#E8EDF5;"
                "font:14px system-ui,sans-serif;text-align:center'>"
                "<p>SAFE-Fire live view, %d x %d, cap %.1f fps"
                " &middot; <a style='color:#25C685' href='%s'>health</a></p>"
                "<img src='%s' style='max-width:100%%;image-rendering:auto'>"
                "</body>" % (hub.size[0], hub.size[1], hub.fps_cap,
                             PATH_HEALTH, PATH_STREAM))
        self._send(200, "text/html; charset=utf-8", html.encode("utf-8"))

    # -- the stream -------------------------------------------------------

    def _stream(self):
        hub = self.server.hub
        if not hub.add_client():
            self._plain(503, "too many clients\n")
            return
        try:
            # A write that stalls must raise so the finally below gives the
            # client slot back. Without this a phone that walked out of range
            # would hold a slot until the process ended.
            self.connection.settimeout(SOCKET_TIMEOUT_S)
            self.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except Exception:
            pass
        try:
            self.send_response(200)
            self.send_header("Content-Type",
                             "multipart/x-mixed-replace; boundary=%s" % BOUNDARY)
            self.send_header("Cache-Control", "no-store, no-cache, private")
            self.send_header("Pragma", "no-cache")
            # No Content-Length on the response: the body ends when the socket
            # does. Every PART carries one, which is what lets the client read a
            # header then readFully(n) instead of scanning for the boundary
            # inside JPEG entropy data.
            self.send_header("Connection", "close")
            self.end_headers()
            self.close_connection = True
            last = 0
            idle = 0.0
            while not hub.stopping():
                item = hub.wait_frame(last, timeout=1.0)
                if item is None:
                    idle += 1.0
                    if idle >= CLIENT_IDLE_LIMIT_S:
                        break        # detector stopped offering; let it reconnect
                    continue
                idle = 0.0
                last, jpeg, dets = item
                head = ["--%s" % BOUNDARY,
                        "Content-Type: image/jpeg",
                        "Content-Length: %d" % len(jpeg)]
                if dets:
                    head.append("X-SafeFire-Dets: %s" % dets)
                part = ("\r\n".join(head) + "\r\n\r\n").encode("ascii")
                # One write per frame: the part is a burst of segments and a
                # split write would let the tail wait on an ACK.
                self.wfile.write(part + jpeg + b"\r\n")
                hub.count_served(1)
        except Exception:
            # A client hanging up mid frame is normal operation, not an error
            # worth printing over the detector's output.
            hub.stats["client_errors"] += 1
        finally:
            hub.remove_client()

    def _snapshot(self):
        """One fresh frame, for curl. Registers as a client so one gets encoded."""
        hub = self.server.hub
        if not hub.add_client():
            self._plain(503, "too many clients\n")
            return
        try:
            item = None
            last = hub.out_seq()
            deadline = time.time() + 3.0
            while time.time() < deadline and not hub.stopping():
                item = hub.wait_frame(last, timeout=0.5)
                if item is not None:
                    break
            if item is None:
                self._plain(503, "no frame yet\n")
                return
            self._send(200, "image/jpeg", item[1])
        except Exception:
            hub.stats["client_errors"] += 1
        finally:
            hub.remove_client()


class _Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    """Python 3.6 has no ThreadingHTTPServer; this is what 3.7 later added."""

    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, addr, hub):
        self.hub = hub
        http.server.HTTPServer.__init__(self, addr, _Handler)

    def process_request(self, request, client_address):
        # 512 KB is ample for a socket writer and keeps three client threads to
        # 1.5 MB of reserved stack. stack_size is process global, so it is put
        # back at once: the publisher's TLS path and the serial reader must keep
        # the default.
        prev = None
        try:
            prev = threading.stack_size(CLIENT_STACK_BYTES)
        except (ValueError, RuntimeError):
            prev = None
        try:
            socketserver.ThreadingMixIn.process_request(self, request, client_address)
        finally:
            if prev is not None:
                try:
                    threading.stack_size(prev)
                except (ValueError, RuntimeError):
                    pass

    def handle_error(self, request, client_address):
        # Same reason as log_message: a dropped phone is not an incident.
        pass


# ------------------------------------------------------------------- self test

def _pattern(w, h, i, bg):
    """A synthetic frame with something that moves.

    A still test card cannot tell a working stream from a frozen one, and a
    frozen stream is the exact failure this server has to be checked for.
    """
    img = bg.copy()
    t = i * 0.06
    cx = int(w * (0.5 + 0.38 * np.sin(t)))
    cy = int(h * (0.5 + 0.28 * np.cos(t * 0.7)))
    cv2.circle(img, (cx, cy), 46, (40, 90, 245), -1)
    cv2.circle(img, (cx, cy), 46, (255, 255, 255), 2)
    bar = int((i * 7) % w)
    cv2.line(img, (bar, 0), (bar, h), (255, 220, 120), 3)
    cv2.putText(img, "SAFE-Fire synthetic  frame %d" % i, (14, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
    cv2.putText(img, time.strftime("%H:%M:%S"), (14, h - 16),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
    return img, cx, cy


def _fake_dets(cx, cy, pad, i):
    """One box around the moving blob, in the detector's canvas coordinates.

    Rows are [x1, y1, x2, y2, confidence, class], letterboxed the same way the
    real pipeline letterboxes, so the normalisation in _norm_boxes is exercised
    rather than bypassed.
    """
    return np.array([[cx - 52, cy - 52 + pad, cx + 52, cy + 52 + pad,
                      0.55 + 0.4 * abs(np.sin(i * 0.05)), 0.0]], np.float32)


def _selftest(a):
    src_w, src_h, net = 640, 480, 640
    pad = (net - src_h) // 2
    bg = np.zeros((src_h, src_w, 3), np.uint8)
    bg[:, :, 0] = np.linspace(20, 90, src_w).astype(np.uint8)     # a blue ramp
    bg[:, :, 1] = 24
    bg[:, :, 2] = 30

    hub = FrameHub(size=(a.width, a.height), quality=a.quality, fps_cap=a.fps,
                   port=a.port, net=net, pad=pad, src_size=(src_w, src_h),
                   names=["FLAME", "SMOKE"], draw_boxes=a.boxes)
    hub.start()
    host = hub.host or "127.0.0.1"
    print("SAFE-Fire stream self test. No camera is opened by this script.")
    print()
    print("  stream    %s" % hub.url())
    print("  browser   http://%s:%d/" % (host, hub.port))
    print("  health    http://%s:%d%s" % (host, hub.port, PATH_HEALTH))
    print("  snapshot  http://%s:%d%s" % (host, hub.port, PATH_SNAPSHOT))
    print()
    print("  curl -s http://127.0.0.1:%d%s" % (hub.port, PATH_HEALTH))
    print("  curl -s http://127.0.0.1:%d%s -o /tmp/s.jpg" % (hub.port, PATH_SNAPSHOT))
    print()
    print("feeding %.1f synthetic fps, serving at most %.1f. Ctrl-C to stop."
          % (a.src_fps, a.fps))
    print()

    period = 1.0 / max(0.1, a.src_fps)
    i = 0
    t_start = time.time()
    try:
        while True:
            if a.seconds and time.time() - t_start > a.seconds:
                break
            t0 = time.time()
            frame, cx, cy = _pattern(src_w, src_h, i, bg)
            dets = None if a.no_dets else _fake_dets(cx, cy, pad, i)
            hub.offer(frame, dets)
            i += 1
            if i % int(max(1.0, a.src_fps) * 10) == 0:
                hl = hub.health()
                print("  clients %d  encoded %d  %.2f fps  %s bytes  encode %s ms"
                      % (hl["clients"], hl["encoded"], hl["fps"],
                         hl["bytes"], hl["encodeMsEma"]))
            rest = period - (time.time() - t0)
            if rest > 0:
                time.sleep(rest)
    except KeyboardInterrupt:
        print("\nstopping")
    finally:
        hub.stop()

    hl = hub.health()
    print()
    print("offered %d   accepted %d   encoded %d   served %d   contended %d"
          % (i, hl["accepted"], hl["encoded"], hl["served"], hl["contended"]))
    print("encode  ema %s ms   max %s ms   last frame %s bytes"
          % (hl["encodeMsEma"], hl["encodeMsMax"], hl["bytes"]))
    if hl["encoded"] and hl["encoded"] > hl["accepted"]:
        print("MORE ENCODES THAN FRAMES ACCEPTED, which must never happen")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="SAFE-Fire MJPEG stream server, self test with no camera")
    ap.add_argument("--port", type=int, default=PORT_DEFAULT)
    ap.add_argument("--width", type=int, default=SIZE_DEFAULT[0])
    ap.add_argument("--height", type=int, default=SIZE_DEFAULT[1])
    ap.add_argument("--quality", type=int, default=QUALITY_DEFAULT)
    ap.add_argument("--fps", type=float, default=FPS_CAP_DEFAULT,
                    help="cap on frames served per second")
    ap.add_argument("--src-fps", type=float, default=16.0,
                    help="rate the fake detector offers frames at")
    ap.add_argument("--seconds", type=float, default=None)
    ap.add_argument("--boxes", action="store_true",
                    help="burn the boxes into the streamed image")
    ap.add_argument("--no-dets", action="store_true",
                    help="do not attach synthetic detections")
    sys.exit(_selftest(ap.parse_args()))
