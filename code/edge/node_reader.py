# -*- coding: utf-8 -*-
"""SAFE-Fire - read the sensor node over USB serial, and fuse with vision.

Runs on the Jetson. Two jobs:

    1. keep the latest sensor sample from the ESP32, without ever blocking the
       inference loop
    2. apply the alarm ladder, which is the policy the thesis argues for and the
       Android client already encodes

THE POLICY IS ASYMMETRIC ON PURPOSE
    Sensors may RAISE the level. They may never lower one the camera raised.
    A fire on the far side of a room reaches the camera long before the plume
    reaches a point sensor: in four controlled smoke trials the gas channel
    missed one entirely, reading clean air for 42 s while a source burned 10 cm
    away, because room airflow carried the plume past it. A policy that required
    sensor agreement would have suppressed that alarm.

    So:
        camera fires, sensors quiet   -> ALERT       (alarm, on vision alone)
        camera fires, sensors agree   -> CONFIRMED   (highest priority)
        camera quiet, sensors elevated-> WATCH       (NOT an alarm)
        neither                       -> NORMAL

STALE DATA IS NOT DATA
    If the node stops talking, the last sample is discarded rather than reused.
    A silent node must not keep voting with a reading from two minutes ago, in
    either direction. Past NODE_STALE_S the node contributes nothing and its
    absence is reported.

    Usage
        python3 node_reader.py --monitor              live, from the node
        python3 node_reader.py --replay log.txt       parse a captured log
"""
from __future__ import print_function

import argparse
import json
import sys
import threading
import time

BAUD = 115200
NODE_STALE_S = 10.0
PORT_CANDIDATES = ("/dev/ttyUSB0", "/dev/ttyUSB1", "/dev/ttyACM0", "/dev/ttyACM1")

LEVELS = ("NORMAL", "WATCH", "ALERT", "CONFIRMED", "OFFLINE")


class NodeReader(object):
    """Latest-sample-wins reader for the ESP32 sensor node."""

    def __init__(self, port=None, baud=BAUD, verbose=False):
        self.port = port
        self.baud = baud
        self.verbose = verbose
        self.sample = None            # last good parsed sample
        self.sample_at = 0.0          # monotonic seconds when it arrived
        self.stats = {"lines": 0, "parsed": 0, "bad": 0, "comments": 0}
        self._ser = None
        self._stop = threading.Event()
        self._thread = None
        self._lock = threading.Lock()

    # -- port ------------------------------------------------------------

    def open(self):
        try:
            import serial
        except ImportError:
            raise RuntimeError("pyserial is missing:  pip3 install pyserial")
        last = None
        for p in ([self.port] if self.port else PORT_CANDIDATES):
            if not p:
                continue
            try:
                # DTR and RTS must be deasserted BEFORE the port opens.
                #
                # On an ESP32 DevKit those two lines drive the auto-reset
                # circuit: DTR through a transistor to EN, RTS to GPIO0.
                # pyserial asserts both by default, which pulls GPIO0 low and
                # leaves the board sitting in the bootloader, saying nothing at
                # all. Measured on this rig with probe_serial.py:
                #
                #     dtr=0 rts=0   1553 bytes in 6 s   <- correct
                #     dtr=1 rts=0    528 bytes
                #     dtr=0 rts=1      0 bytes          <- held in bootloader
                #     dtr=1 rts=1   1228 bytes
                #
                # Setting the attributes before open() avoids emitting the
                # pulse at all, rather than resetting and hoping.
                s = serial.Serial()
                s.port = p
                s.baudrate = self.baud
                s.timeout = 1.0
                s.dtr = False
                s.rts = False
                s.open()
                self._ser = s
                self.port = p
                break
            except Exception as e:
                last = e
        if not self._ser:
            raise RuntimeError("no serial port. Tried %s. Last error: %s"
                               % (", ".join(PORT_CANDIDATES), last))
        # The node prints a human table by default. 'j' switches it to JSON.
        # Give it a moment: if the board did reset, a byte sent during the
        # reset is lost.
        time.sleep(2.0)
        self._ser.reset_input_buffer()
        self._ser.write(b"j")
        self._ser.flush()
        return self.port

    # -- parsing ---------------------------------------------------------

    def feed(self, line):
        """Consume one line. Returns the parsed sample, or None."""
        self.stats["lines"] += 1
        line = line.strip()
        if not line:
            return None
        if line.startswith("#"):
            self.stats["comments"] += 1
            if self.verbose:
                print(line)
            return None
        if not line.startswith("{"):
            # The human table, or a partial line from a mid-transmission open.
            return None
        try:
            s = json.loads(line)
        except ValueError:
            self.stats["bad"] += 1
            return None
        if "level" not in s or "ok" not in s:
            self.stats["bad"] += 1
            return None
        self.stats["parsed"] += 1
        with self._lock:
            self.sample = s
            self.sample_at = time.time()
        return s

    # -- background ------------------------------------------------------

    def start(self):
        if self._thread:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop)
        self._thread.daemon = True
        self._thread.start()

    def _loop(self):
        buf = b""
        while not self._stop.is_set():
            try:
                chunk = self._ser.read(256)
            except Exception:
                time.sleep(0.5)
                continue
            if not chunk:
                continue
            buf += chunk
            while b"\n" in buf:
                raw, buf = buf.split(b"\n", 1)
                self.feed(raw.decode("utf-8", "replace"))

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        if self._ser:
            try:
                self._ser.close()
            except Exception:
                pass

    # -- access ----------------------------------------------------------

    def latest(self):
        """The current sample, or None if there is none or it has gone stale."""
        with self._lock:
            s, at = self.sample, self.sample_at
        if s is None or (time.time() - at) > NODE_STALE_S:
            return None
        return s

    def age(self):
        with self._lock:
            return None if self.sample_at == 0 else time.time() - self.sample_at

    def health(self):
        """Per-channel health from the last sample, or all-unknown if stale."""
        s = self.latest()
        if not s:
            return {"ds": None, "mlx": None, "mq2": None, "flame": None}
        ok = s.get("ok") or {}
        return dict((k, bool(ok.get(k))) for k in ("ds", "mlx", "mq2", "flame"))


# ------------------------------------------------------------------- fusion

def to_app_sensors(sample, age_s=None):
    """Map a node sample onto the field names the Firestore schema expects.

    gasPpm stays null. The MQ-2 datasheet defines R0 in 1000 ppm LPG while our
    baseline is clean air, so the published ppm curves do not apply to this
    ratio and emitting a number would be a fabricated unit. gasRatio is the
    measurement; the client should render that.

    age_s is how long ago the sample arrived, from NodeReader.age(). It is a
    property of the link and not of the sample, so it has to be passed in. The
    app reads it as sampleAgeMs and treats a missing value as infinitely old,
    which meant every reading was flagged out of date while the node was
    perfectly healthy.
    """
    if not sample:
        # An absent sensors map made a dead node look like a room at 0 C with
        # no gas, because the client defaulted every missing number to zero.
        # Say "no reading" explicitly instead.
        return {"timestamp": int(time.time() * 1000), "nodeOnline": False,
                "sampleAgeMs": None, "ambientC": None, "surfaceC": None,
                "surfaceRiseC": None, "gasRatio": None, "gasRisePct": None,
                "flameIr": None, "flameDropMv": None, "flameMinMv": None,
                "nodeLevel": None, "calAgeS": None,
                "okDs": False, "okMlx": False, "okMq2": False, "okFlame": False}
    ok = sample.get("ok") or {}

    # The firmware computes millis()/1000 - baseEpoch in unsigned arithmetic. A
    # baseline captured a few seconds ahead of that clock underflows to about
    # 4.29e9 instead of going negative, which the app would render as a
    # calibration age of 136 years. Measured on the bench: calAgeS 4294967292,
    # which is 2**32 - 4. Anything past a plausible uptime is not an age.
    cal = sample.get("calAgeS")
    if cal is not None and (cal < 0 or cal > 365 * 24 * 3600):
        cal = None

    return {
        "timestamp": int(time.time() * 1000),
        "nodeOnline": True,
        # How old the reading is. Null here made the app call every sample
        # stale, since an unknown age cannot be assumed to be recent.
        "sampleAgeMs": None if age_s is None else int(age_s * 1000),
        "ambientC": sample.get("ambientC"),
        "surfaceC": sample.get("surfaceC"),
        "surfaceRiseC": sample.get("surfaceRiseC"),
        "gasRatio": sample.get("gasRatio"),
        "gasRisePct": sample.get("gasRisePct"),
        "flameIr": sample.get("flameIr"),
        "flameDropMv": sample.get("flameDropMv"),
        # The app shows the raw millivolts beside the normalised figure, and the
        # firmware has been sending this all along.
        "flameMinMv": sample.get("flameMinMv"),
        # The node's own verdict, kept as a cross check against the fusion done
        # here. The two are computed from the same thresholds, so a disagreement
        # means one of the two copies has drifted.
        "nodeLevel": sample.get("level"),
        # Seconds since the baselines were taken. The app uses it to say a
        # channel has never been baselined rather than showing a bare dash.
        "calAgeS": cal,
        "okDs": bool(ok.get("ds")),
        "okMlx": bool(ok.get("mlx")),
        "okMq2": bool(ok.get("mq2")),
        "okFlame": bool(ok.get("flame")),
    }


def fuse(vision_alarm, sample, vision_degraded=False):
    """Combine the camera decision with the node. Returns (level, rationale).

    vision_alarm     True once the temporal layer has raised an alarm
    sample           the node's latest sample, or None if silent or stale
    vision_degraded  the camera pipeline is not running
    """
    node_level = (sample or {}).get("level")
    sensors_up = node_level in ("WATCH", "ALERT", "CONFIRMED")

    if vision_degraded:
        level = "OFFLINE"
    elif vision_alarm and sensors_up:
        level = "CONFIRMED"
    elif vision_alarm:
        level = "ALERT"
    elif sensors_up:
        level = "WATCH"
    else:
        level = "NORMAL"

    if sample is None:
        said_s = "No sensor sample: the node is silent or its data is stale."
    else:
        bits = []
        if sample.get("surfaceRiseC") is not None:
            bits.append("surface %+.2f C above baseline" % sample["surfaceRiseC"])
        if sample.get("gasRatio") is not None:
            bits.append("Rs/R0 %.3f" % sample["gasRatio"])
        if sample.get("flameDropMv") is not None:
            bits.append("infrared drop %d mV" % sample["flameDropMv"])
        said_s = ("; ".join(bits) + ".") if bits else "Node reporting, no channel elevated."

    said_v = ("Detection sustained through the persistence rule."
              if vision_alarm else
              "No detection above the calibrated threshold." if not vision_degraded else
              "Camera pipeline is not running.")

    conclusion = {
        "NORMAL": "Nothing above threshold on either channel.",
        "WATCH": ("Sensors elevated while the camera is clear. Not an alarm: "
                  "sensors alone never raise one."),
        "ALERT": ("Camera detected fire. This alarms on its own, so a fire far "
                  "from the sensor node is not missed."),
        "CONFIRMED": "Both independent channels agree. Highest priority.",
        "OFFLINE": "Detection is degraded; the sensor channel is watching alone.",
    }[level]

    return level, {
        "visionSaid": said_v,
        "sensorsSaid": said_s,
        "conclusion": conclusion,
        "visionContributed": bool(vision_alarm),
        "sensorsContributed": bool(sensors_up),
    }


# -------------------------------------------------------------------- modes

def _show(sample, level, why, age):
    ok = sample.get("ok", {})
    print("  %-9s  air %-6s surf %-6s dSurf %-6s Rs/R0 %-6s drop %-5s "
          "p2p %-5s ok %d%d%d%d  age %.1fs"
          % (level,
             sample.get("ambientC"), sample.get("surfaceC"),
             sample.get("surfaceRiseC"), sample.get("gasRatio"),
             sample.get("flameDropMv"), sample.get("flameP2pMv"),
             ok.get("ds", 0), ok.get("mlx", 0), ok.get("mq2", 0), ok.get("flame", 0),
             age or 0.0))


def run_monitor(a):
    r = NodeReader(port=a.port, verbose=True)
    print("opening serial ...")
    print("port:", r.open())
    r.start()
    print("switched the node to JSON. Ctrl-C to stop.")
    print()
    last_seen = None
    try:
        while True:
            s = r.latest()
            if s is None:
                age = r.age()
                if age is None:
                    print("  waiting for the first sample ...")
                else:
                    print("  NODE STALE, last sample %.1f s ago" % age)
            elif s is not last_seen:
                last_seen = s
                level, why = fuse(False, s)
                _show(s, level, why, r.age())
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass
    finally:
        r.stop()
        print()
        print("lines %d  parsed %d  comments %d  bad %d"
              % (r.stats["lines"], r.stats["parsed"],
                 r.stats["comments"], r.stats["bad"]))


def run_replay(a):
    """Parse a captured log. Verifies the parser with no hardware attached."""
    r = NodeReader()
    src = sys.stdin if a.replay == "-" else open(a.replay)
    n = 0
    for line in src:
        s = r.feed(line)
        if s:
            n += 1
            for va in (False, True):
                level, why = fuse(va, s)
                print("  vision=%-5s -> %-9s  %s"
                      % (va, level, why["conclusion"][:58]))
            if n >= a.limit:
                break
    print()
    print("lines %d  parsed %d  comments %d  bad %d"
          % (r.stats["lines"], r.stats["parsed"],
             r.stats["comments"], r.stats["bad"]))
    if r.stats["parsed"] == 0:
        print("nothing parsed. Was the node in JSON mode? Press j, or let this")
        print("script send it on connect.")


def run_send(a):
    """Send one command key and print what the node says back.

    Baselining is deliberate, never automatic. It must happen in clean air with
    nothing hot in the field, and doing it on a schedule would eventually
    rebaseline in a room that is already smoky.
    """
    r = NodeReader(port=a.port, verbose=True)
    print("port:", r.open())
    time.sleep(0.5)
    r._ser.reset_input_buffer()
    r._ser.write(a.send.encode()[:1])
    r._ser.flush()
    print("sent %r, listening 12 s" % a.send[:1])
    print()
    t0 = time.time()
    buf = b""
    while time.time() - t0 < 12.0:
        chunk = r._ser.read(256)
        if chunk:
            buf += chunk
    r.stop()
    for line in buf.decode("utf-8", "replace").splitlines():
        if line.strip():
            print("  " + line.rstrip())


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="SAFE-Fire node reader and fusion")
    ap.add_argument("--port", default=None, help="e.g. /dev/ttyUSB0")
    ap.add_argument("--limit", type=int, default=5, help="replay: samples to show")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--monitor", action="store_true", help="live from the node")
    g.add_argument("--replay", metavar="FILE", help="parse a captured log, - for stdin")
    g.add_argument("--send", metavar="KEY",
                   help="send one command key to the node: b baseline, s status, "
                        "j json/table, c clear")
    a = ap.parse_args()
    if a.send:
        run_send(a)
    else:
        (run_monitor if a.monitor else run_replay)(a)
