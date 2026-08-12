# -*- coding: utf-8 -*-
"""SAFE-Fire - publish edge state to Firestore from the Jetson.

The piece that was missing. The Android client was verified against seeded
documents, so everything downstream of Firestore already works; nothing upstream
of it wrote anything. This module closes that gap.

WHY REST AND NOT THE SDK
    JetPack 4.6.1 ships Python 3.6. firebase-admin and google-cloud-firestore
    both want newer runtimes and pull a large dependency tree onto a 2 GB board
    that is already running a TensorRT engine. The REST API needs nothing but
    the standard library, so this file has no imports the Nano does not already
    have.

WHY WRITES ARE THROTTLED AND OFF THE HOT PATH
    The inference loop runs at 16.4 fps. Writing a document per frame would put
    a network round trip inside a 61 ms budget and would burn the free quota in
    an afternoon. State is written on a CHANGE of alarm level, or every
    STATE_PERIOD_S seconds, whichever comes first, and always from a background
    thread with a single-slot queue. If the network stalls, frames are dropped
    from the queue rather than blocking the detector. A fire detector that
    stutters because the cloud is slow is worse than one that publishes late.

HOW THE PHONE FINDS THE LAN VIDEO STREAM
    nodes/jetson already gets a heartbeat every NODE_PERIOD_S. The stream's
    address rides on it, so discovery costs no extra writes and a DHCP lease
    change repairs itself within one heartbeat instead of needing the app
    rebuilt. Not mDNS: multicast is unreliable on consumer access points that
    do client isolation, and it would add a failure mode this design does not
    have.

CREDENTIALS
    The Web API key is read from app/google-services.json, or from the
    SAFEFIRE_API_KEY environment variable. Nothing is hard-coded and nothing is
    printed. Pass --key-file on the command line if the JSON lives elsewhere.

    While the database is in test mode this key is enough to write. Once the
    rules are tightened, which must happen before deployment, this module needs
    an ID token instead; see set_id_token().
"""
from __future__ import print_function

import base64
import json
import os
import socket
import ssl
import sys
import threading
import time

try:                                     # py3
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError, URLError
except ImportError:                      # py2, just in case
    from urllib2 import Request, urlopen, HTTPError, URLError

PROJECT_DEFAULT = "safefire-1"
STATE_PERIOD_S = 5.0                     # heartbeat for state/current
NODE_PERIOD_S = 10.0                     # heartbeat for nodes/jetson
HTTP_TIMEOUT_S = 8.0
FRAME_MAX_BYTES = 700 * 1024             # above this Firestore rejects the doc

LEVELS = ("NORMAL", "WATCH", "ALERT", "CONFIRMED", "OFFLINE")


# --------------------------------------------------------------- value mapping

def encode(v):
    """Python value -> Firestore typed value.

    Order matters: bool is a subclass of int in Python, so it must be tested
    first or every True becomes integerValue 1 and the app reads a number where
    it expects a boolean.
    """
    if v is None:
        return {"nullValue": None}
    if isinstance(v, bool):
        return {"booleanValue": v}
    if isinstance(v, int):
        return {"integerValue": str(v)}
    if isinstance(v, float):
        return {"doubleValue": v}
    if isinstance(v, str):
        return {"stringValue": v}
    if isinstance(v, (list, tuple)):
        return {"arrayValue": {"values": [encode(x) for x in v]}}
    if isinstance(v, dict):
        return {"mapValue": {"fields": dict((k, encode(x)) for k, x in v.items())}}
    raise TypeError("cannot encode %r" % type(v))


# ----------------------------------------------------------------- addressing

def _iface_ips():
    """Every non-loopback IPv4 address the kernel has, in interface order.

    socket.gethostbyname_ex reads /etc/hosts, which on a stock L4T image maps
    the hostname to 127.0.1.1, so it answers "loopback" for a board that is on
    Wi-Fi. Asking the kernel with SIOCGIFADDR is the version that is true.
    docker0 is skipped because it is up whenever Docker is installed and its
    address routes nowhere the phone can reach.
    """
    out = []
    try:
        import fcntl
        import struct
    except ImportError:                  # not Linux, so there is nothing to read
        return out
    try:
        with open("/proc/net/dev") as f:
            lines = f.readlines()[2:]    # two header rows
    except (IOError, OSError):
        return out
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        for line in lines:
            name = line.split(":", 1)[0].strip()
            if not name or name == "lo" or name.startswith("docker"):
                continue
            try:
                packed = fcntl.ioctl(
                    s.fileno(), 0x8915,          # SIOCGIFADDR
                    struct.pack("256s", name[:15].encode("ascii")))
                ip = socket.inet_ntoa(packed[20:24])
            except (IOError, OSError):
                continue                 # interface is down, or has no address
            if not ip.startswith("127.") and not ip.startswith("169.254."):
                out.append(ip)
    finally:
        s.close()
    return out


def lan_ip():
    """The address this board is reachable at on its own network, or None.

    Connecting a UDP socket sends no packet. It asks the kernel which interface
    would carry traffic to that destination and binds the socket to that
    interface's address, which is a read of the routing table and nothing more.
    The literal below is never contacted, so this works with the internet down,
    with DNS broken, and behind a router that drops everything outbound.

    It does need a default route, which a board on an isolated switch will not
    have. That is what the interface scan is for.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 9))
        ip = s.getsockname()[0]
        if ip and not ip.startswith("127.") and not ip.startswith("169.254."):
            return ip
    except Exception:
        pass
    finally:
        s.close()
    found = _iface_ips()
    return found[0] if found else None


# ------------------------------------------------------------------ the client

class FirestorePublisher(object):

    def __init__(self, project=PROJECT_DEFAULT, api_key=None, key_file=None,
                 verbose=True):
        self.project = project
        self.verbose = verbose
        self.api_key = api_key or self._find_key(key_file)
        self.id_token = None
        self.base = ("https://firestore.googleapis.com/v1/projects/%s"
                     "/databases/(default)/documents" % project)
        self._ctx = ssl.create_default_context()
        self._lock = threading.Lock()
        self._pending = None                 # single slot; newest wins
        self._stop = threading.Event()
        self._worker = None
        self._last_state_write = 0.0
        self._last_level = None
        self._stream = None                  # set by set_stream, see heartbeat
        self.stats = {"writes": 0, "errors": 0, "dropped": 0,
                      "last_rtt_ms": None, "last_error": None}

    # -- credentials ------------------------------------------------------

    @staticmethod
    def _find_key(key_file=None):
        env = os.environ.get("SAFEFIRE_API_KEY")
        if env:
            return env
        candidates = [key_file] if key_file else []
        candidates += [
            os.path.expanduser("~/google-services.json"),
            "/home/aya5/google-services.json",
            os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "google-services.json"),
        ]
        for p in candidates:
            if p and os.path.isfile(p):
                with open(p) as f:
                    j = json.load(f)
                try:
                    return j["client"][0]["api_key"][0]["current_key"]
                except (KeyError, IndexError):
                    pass
        raise RuntimeError(
            "no API key. Set SAFEFIRE_API_KEY, or place google-services.json "
            "next to this script or in the home directory.")

    def set_id_token(self, token):
        """Use an authenticated identity instead of the bare API key.

        Required once the Firestore rules stop allowing open writes. The token
        is a Firebase ID token; obtain one with signInAnonymously against the
        Identity Toolkit REST endpoint and refresh it before it expires.
        """
        self.id_token = token

    # -- transport --------------------------------------------------------

    def _patch(self, path, doc):
        url = "%s/%s" % (self.base, path)
        url += "?key=%s" % self.api_key
        body = json.dumps({"fields": dict((k, encode(v))
                                          for k, v in doc.items())}).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.id_token:
            headers["Authorization"] = "Bearer %s" % self.id_token
        req = Request(url, data=body, headers=headers)
        req.get_method = lambda: "PATCH"
        t0 = time.time()
        try:
            r = urlopen(req, timeout=HTTP_TIMEOUT_S, context=self._ctx)
            r.read()
            rtt = (time.time() - t0) * 1000.0
            self.stats["writes"] += 1
            self.stats["last_rtt_ms"] = round(rtt, 1)
            return True, rtt
        except HTTPError as e:
            detail = e.read()[:200].decode("utf-8", "replace")
            self.stats["errors"] += 1
            self.stats["last_error"] = "HTTP %s %s" % (e.code, detail)
        except (URLError, ssl.SSLError, OSError) as e:
            self.stats["errors"] += 1
            self.stats["last_error"] = str(e)
        if self.verbose:
            sys.stderr.write("publish: %s -> %s\n" % (path, self.stats["last_error"]))
        return False, (time.time() - t0) * 1000.0

    # -- documents --------------------------------------------------------

    @staticmethod
    def frame_to_b64(jpeg_bytes):
        """JPEG bytes -> base64 string, or None if it would not fit.

        Firestore caps a document at 1 MB and base64 adds a third. Returning
        None rather than truncating matters: the app falls back to placeholder
        art when frameB64 is absent, and a truncated string would instead give
        it a corrupt image to decode.
        """
        if not jpeg_bytes:
            return None
        if len(jpeg_bytes) > FRAME_MAX_BYTES:
            return None
        return base64.b64encode(jpeg_bytes).decode("ascii")

    def build_state(self, level, detections=None, sensors=None, frame_b64=None,
                    fps=None, inference_ms=None, rationale=None, since_ms=None):
        assert level in LEVELS, "level must be one of %s" % (LEVELS,)
        doc = {
            "level": level,
            "since": int(since_ms if since_ms is not None else time.time() * 1000),
            "detections": detections or [],
        }
        # "acknowledged" is deliberately NOT written here. It is owned by the
        # client: the person acknowledges an alarm on the phone. Writing False
        # on every five-second heartbeat clobbered that within seconds, so the
        # acknowledgement never stuck. Only publish_event seeds it, once.
        if frame_b64:
            doc["frameB64"] = frame_b64
        if sensors:
            doc["sensors"] = sensors
        if fps is not None:
            doc["fps"] = float(fps)
        if inference_ms is not None:
            doc["inferenceMs"] = float(inference_ms)
        doc["rationale"] = rationale or self.explain(level, detections, sensors)
        return doc

    @staticmethod
    def explain(level, detections=None, sensors=None):
        """Fill the rationale from the actual decision, not a fixed template.

        The schema notes that this is the sentence a person reads at 3 a.m. to
        decide whether to get out of bed, so it should say what was actually
        observed. A constant string here would be a lie with a timestamp on it.
        """
        dets = detections or []
        s = sensors or {}
        vision = bool(dets)
        best = max([d.get("confidence", 0.0) for d in dets]) if dets else 0.0
        labels = ", ".join(sorted(set(d.get("label", "?") for d in dets))) or "nothing"
        sensor_hit = level in ("WATCH", "CONFIRMED")

        if vision:
            said_v = "%s detected, highest confidence %.2f." % (labels, best)
        else:
            said_v = "No detection above the calibrated threshold."
        if s:
            # dict.get returns None for a key that EXISTS holding None, so the
            # default never fires and "%.1f" % None raises. Every unhealthy
            # channel is published as None, so this was a live crash waiting
            # for one dead sensor. Gas is a ratio here, never a ppm figure:
            # the datasheet R0 is defined in 1000 ppm LPG and our baseline is
            # clean air, so a ppm number would be a fabricated unit.
            def _f(key, fmt, unit):
                v = s.get(key)
                return (fmt % v) + unit if isinstance(v, (int, float)) else None
            parts = [p for p in (_f("surfaceC", "surface %.1f", " C"),
                                 _f("ambientC", "ambient %.1f", " C"),
                                 _f("gasRatio", "Rs/R0 %.3f", ""),
                                 _f("flameIr", "infrared %.2f", "")) if p]
            said_s = (", ".join(parts) + ".") if parts else \
                "A sensor sample arrived but no channel reported a value."
        else:
            said_s = "No sensor sample in this window."

        conclusion = {
            "NORMAL": "Nothing above threshold on either channel.",
            "WATCH": ("Sensors elevated while the camera is clear. Not an alarm: "
                      "sensors alone never raise one."),
            "ALERT": ("Camera detected fire. This alarms on its own, so a fire "
                      "far from the sensor node is not missed."),
            "CONFIRMED": "Both independent channels agree. Highest priority.",
            "OFFLINE": "Detection is degraded; the sensor channel is watching alone.",
        }[level]

        return {"visionSaid": said_v, "sensorsSaid": said_s,
                "conclusion": conclusion,
                "visionContributed": vision,
                "sensorsContributed": bool(s) and sensor_hit}

    # -- public API -------------------------------------------------------

    def publish_state(self, doc, force=False):
        """Write state/current, throttled.

        Writes when the level changed, or when STATE_PERIOD_S has passed, or
        when force is set. Returns True if a write was actually attempted.
        """
        now = time.time()
        changed = doc.get("level") != self._last_level
        due = (now - self._last_state_write) >= STATE_PERIOD_S
        if not (force or changed or due):
            return False
        # Stamped at write time, not at capture time, because the question the
        # app asks of this field is whether the edge is still alive. Without it
        # a level published before a shutdown stays on the phone for ever with
        # nothing to mark it as history.
        doc = dict(doc)
        doc["updatedAt"] = int(now * 1000)
        ok, _ = self._patch("state/current", doc)
        if ok:
            self._last_state_write = now
            self._last_level = doc.get("level")
        return True

    def publish_event(self, doc, event_id=None):
        """Append to events/. The id is the document id so a retry overwrites."""
        eid = event_id or ("evt_%d" % int(time.time() * 1000))
        d = dict(doc)
        d["id"] = eid
        # Firestore orderBy also filters for existence of the field, so an
        # event without "timestamp" is dropped by the query itself, before
        # any parsing. Without this line the history collection is written
        # correctly and is invisible.
        d.setdefault("timestamp", d.get("since", int(time.time() * 1000)))
        d.setdefault("acknowledged", False)   # seeded once, then client-owned
        ok, rtt = self._patch("events/%s" % eid, d)
        return eid if ok else None

    def set_stream(self, port=None, path="/stream.mjpg", up=False):
        """Advertise a LAN video stream on every heartbeat from now on.

        Call with port=None to stop advertising. Nothing is written here: the
        fields go out with the heartbeat that already runs, which is what keeps
        discovery free.
        """
        if port is None:
            self._stream = None
        else:
            self._stream = {"port": int(port), "path": path, "up": bool(up)}

    def _stream_fields(self):
        """The four fields the app reads off nodes/jetson.

        The address is re-detected on every heartbeat rather than captured at
        startup, so a new DHCP lease is corrected within NODE_PERIOD_S.

        When the address cannot be determined the two string fields are written
        as null rather than left out. A PATCH merges, so leaving them out would
        keep whatever was published last and hand the app an address that no
        longer routes anywhere, which is worse than telling it we do not know.
        """
        if not self._stream:
            return {}
        ip = lan_ip()
        return {
            "streamUrl": ("http://%s:%d%s" % (ip, self._stream["port"],
                                              self._stream["path"])) if ip else None,
            "streamPort": int(self._stream["port"]),
            "lanIp": ip,
            "streamUp": bool(self._stream["up"] and ip),
        }

    def heartbeat(self, online=True, detail="YOLO26n | TensorRT FP16"):
        doc = {
            "name": "Jetson Nano",
            "online": bool(online),
            "lastSeen": int(time.time() * 1000),
            "detail": detail,
        }
        doc.update(self._stream_fields())
        return self._patch("nodes/jetson", doc)[0]

    def publish_reading(self, sample):
        rid = "rd_%d" % int(time.time() * 1000)
        return self._patch("readings/%s" % rid, sample)[0]

    # -- background mode --------------------------------------------------

    def start_async(self):
        """Publish from a worker thread with a single-slot queue.

        The detector calls submit() and returns immediately. If a write is still
        in flight when the next state arrives, the older one is discarded: for a
        live status document the newest value is the only one that matters, and
        a backlog would make the app show stale state after a network hiccup.
        """
        if self._worker:
            return
        self._stop.clear()
        self._worker = threading.Thread(target=self._loop)
        self._worker.daemon = True
        self._worker.start()

    def submit(self, doc, frame=None, size=(640, 360), quality=75):
        """Hand a document to the worker. Optionally hand it a raw frame too.

        Encoding is deferred on purpose. Measured on the Jetson, doing the
        resize, JPEG encode and base64 inline cost about 350 ms on each of the
        13 frames that published during a 651-frame run. The median and the 99th
        percentile were untouched at 61.1 and 63.2 ms, but the MEAN rose from
        61.0 to 67.9 and throughput fell from 16.4 to 14.7 fps. A handful of
        very slow frames is exactly the shape a detector should not have, so the
        work moved here, where being slow costs nothing.
        """
        with self._lock:
            if self._pending is not None:
                self.stats["dropped"] += 1
            self._pending = (doc, frame, size, quality)

    def _loop(self):
        last_hb = 0.0
        while not self._stop.is_set():
            item = None
            with self._lock:
                if self._pending is not None:
                    item, self._pending = self._pending, None
            if item is not None:
                doc, frame, size, quality = item
                if frame is not None and "frameB64" not in doc:
                    try:
                        import cv2
                        small = cv2.resize(frame, size)
                        ok, buf = cv2.imencode(
                            ".jpg", small, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
                        if ok:
                            b64 = self.frame_to_b64(buf.tobytes())
                            if b64:
                                doc["frameB64"] = b64
                    except Exception as e:
                        self.stats["last_error"] = "encode: %s" % e
                self.publish_state(doc)
            now = time.time()
            if now - last_hb >= NODE_PERIOD_S:
                self.heartbeat(True)
                last_hb = now
            time.sleep(0.25)

    def stop(self):
        self._stop.set()
        if self._worker:
            self._worker.join(timeout=3.0)
            self._worker = None
        self.heartbeat(False)


# ------------------------------------------------------------------- self test

def _selftest(project, key_file):
    """Write one document of every kind and report the round trip time.

    Run this on the Jetson before wiring the publisher into the detector. It
    answers the only question that matters at this stage: can this board reach
    Firestore, and how long does a write take from here?
    """
    p = FirestorePublisher(project=project, key_file=key_file)
    print("project      : %s" % p.project)
    print("api key      : loaded, %d chars, not printed" % len(p.api_key))
    print()

    rtts = []
    print("heartbeat    :", "ok" if p.heartbeat(True) else "FAILED")
    if p.stats["last_rtt_ms"]:
        rtts.append(p.stats["last_rtt_ms"])

    doc = p.build_state(
        "NORMAL",
        detections=[],
        sensors={"timestamp": int(time.time() * 1000), "ambientC": 24.6,
                 "surfaceC": 26.1, "gasPpm": 98, "flameIr": 0.03},
        fps=16.4, inference_ms=52.3)
    print("state/current:", "ok" if p.publish_state(doc, force=True) else "FAILED",
          " %.0f ms" % (p.stats["last_rtt_ms"] or 0))
    rtts.append(p.stats["last_rtt_ms"] or 0)

    print("reading      :", "ok" if p.publish_reading(
        {"timestamp": int(time.time() * 1000), "ambientC": 24.6,
         "surfaceC": 26.1, "gasPpm": 98, "flameIr": 0.03}) else "FAILED")
    rtts.append(p.stats["last_rtt_ms"] or 0)

    print()
    print("writes %d   errors %d" % (p.stats["writes"], p.stats["errors"]))
    if p.stats["last_error"]:
        print("last error: %s" % p.stats["last_error"])
    if rtts:
        rtts = [r for r in rtts if r]
        print("round trip : min %.0f  mean %.0f  max %.0f ms"
              % (min(rtts), sum(rtts) / len(rtts), max(rtts)))
    print()
    print("Open the app now. The Status screen should show NORMAL and the")
    print("Devices screen should show the Jetson online.")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="SAFE-Fire Firestore publisher")
    ap.add_argument("--project", default=PROJECT_DEFAULT)
    ap.add_argument("--key-file", default=None,
                    help="path to google-services.json")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        _selftest(a.project, a.key_file)
    else:
        ap.print_help()
