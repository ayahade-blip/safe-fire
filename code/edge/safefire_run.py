# -*- coding: utf-8 -*-
"""SAFE-Fire - the whole system, running.

Camera -> TensorRT -> threshold -> persistence layer -> fusion with the sensor
node -> Firestore -> phone. Every piece was measured on its own; this is the
file that runs them together.

    camera + engine     from cam_infer2.py, the version that measured 16.39 fps
    threshold           the operating point C3 measured, or a conformal one
    persistence         K-of-N with IoU association, from temporal_alarm.py
    sensor node         node_reader.py over USB serial
    fusion              the asymmetric ladder: sensors raise, never suppress
    publish             publish.py, throttled and off the hot path

WHAT IS NOT ALLOWED TO SLOW THE DETECTOR
    Nothing in the network path runs inside the frame loop. Publishing happens
    on a worker with a single-slot queue, so a stall drops stale state instead
    of dropping frames. The serial reader is a second worker. The loop itself
    does capture, preprocess, infer, threshold, track: the same work that was
    benchmarked, plus a dictionary update.

THE OPERATING POINT IS MEASURED, NOT CHOSEN
    Default is confidence 0.50 with 3-of-5 and IoU 0.30, because that exact
    configuration has a measured false-alarm rate on 32.2 minutes of negative
    video: 31.7 alarms per hour pooled, 66.2 on FIRESENSE and 3.4 on KMU.
    --alpha switches to a conformal threshold instead, which carries a
    distribution-free guarantee but a different, separately measured recall.

    Usage
        python3 safefire_run.py                    run until stopped
        python3 safefire_run.py --seconds 120      run for two minutes
        python3 safefire_run.py --no-publish       local only, no cloud writes
        python3 safefire_run.py --alpha 0.05       use the conformal threshold
"""
from __future__ import print_function

import argparse
import ctypes
import os
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from node_reader import NodeReader, fuse, to_app_sensors      # noqa: E402
from publish import FirestorePublisher                        # noqa: E402
from stream_server import FrameHub                            # noqa: E402
from notify import FcmSender, from_rationale                  # noqa: E402

ENGINE = "/home/aya5/kd6_fp16.engine"
SRC_W, SRC_H = 1640, 1232
CAP_W, CAP_H = 640, 480
NET = 640
# These strings are parsed by DetectionClass.valueOf on the Android side,
# so they must match that enum exactly: FLAME and SMOKE, upper case. They
# were "fire" and "smoke", which threw inside a runCatching and made every
# box vanish with no error anywhere.
NAMES = ["FLAME", "SMOKE"]

# Measured operating point. See C3_TEMPORAL/E3_2_two_by_two.csv.
CONF_DEFAULT = 0.50
K, N, IOU_MIN = 3, 5, 0.30

# Conformal thresholds from C2_CONFORMAL/E2_2_conformal.csv, verified on a
# disjoint 250 negatives. Recall at each is 0.7582 and 0.8819.
CONFORMAL_TAU = {0.01: 0.6641, 0.05: 0.0842}

FRAME_W, FRAME_H, JPEG_Q = 640, 360, 75

cudart = ctypes.CDLL("libcudart.so")
cudart.cudaMalloc.argtypes = [ctypes.POINTER(ctypes.c_void_p), ctypes.c_size_t]
cudart.cudaMemcpy.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                              ctypes.c_size_t, ctypes.c_int]
H2D, D2H = 1, 2


def cuda_malloc(n):
    p = ctypes.c_void_p()
    if cudart.cudaMalloc(ctypes.byref(p), n):
        raise RuntimeError("cudaMalloc")
    return p


# ------------------------------------------------------ persistence layer

def iou(a, b):
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    ua = (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - inter
    return inter / ua if ua > 0 else 0.0


class Track(object):
    __slots__ = ("box", "hits", "last", "cls", "alarmed")

    def __init__(self, box, frame, cls):
        self.box, self.cls = box, cls
        self.hits = [frame]
        self.last = frame
        self.alarmed = False


class TemporalAlarm(object):
    """K-of-N persistence with spatial association.

    Persistence asks how often. The IoU chain asks whether it stayed in the
    same place. A flickering reflection satisfies the first and fails the
    second, which is why both are required. Identical logic to
    C3_TEMPORAL/temporal_alarm.py, so the measured rates carry over.
    """

    def __init__(self, k=K, n=N, iou_min=IOU_MIN, conf=CONF_DEFAULT):
        self.k, self.n, self.iou_min, self.conf = k, n, iou_min, conf
        self.tracks = []

    def update(self, idx, dets):
        dets = [d for d in dets if d[4] >= self.conf]
        used = set()
        for t in self.tracks:
            best, bi = 0.0, -1
            for j, d in enumerate(dets):
                if j in used or int(d[5]) != t.cls:
                    continue
                v = iou(t.box, d[:4])
                if v > best:
                    best, bi = v, j
            if bi >= 0 and best >= self.iou_min:
                used.add(bi)
                t.box = dets[bi][:4]
                t.hits.append(idx)
                t.last = idx
        for j, d in enumerate(dets):
            if j not in used:
                self.tracks.append(Track(d[:4], idx, int(d[5])))
        self.tracks = [t for t in self.tracks if idx - t.last <= self.n]
        fired = []
        for t in self.tracks:
            t.hits = [h for h in t.hits if h > idx - self.n]
            if not t.alarmed and len(t.hits) >= self.k:
                t.alarmed = True
                fired.append(t)
        return fired

    def active(self):
        return any(t.alarmed for t in self.tracks)


# ------------------------------------------------------------------- main

def main(a):
    conf = a.conf
    if a.alpha is not None:
        if a.alpha not in CONFORMAL_TAU:
            print("alpha must be one of %s" % sorted(CONFORMAL_TAU))
            return 2
        conf = CONFORMAL_TAU[a.alpha]
        print("conformal threshold for alpha=%.2f : %.4f" % (a.alpha, conf))
    print("threshold %.4f   rule %d-of-%d   IoU >= %.2f" % (conf, a.k, a.n, IOU_MIN))

    import tensorrt as trt
    logger = trt.Logger(trt.Logger.ERROR)
    runtime = trt.Runtime(logger)
    engine = runtime.deserialize_cuda_engine(open(a.engine, "rb").read())
    ctx = engine.create_execution_context()
    inp = np.zeros(tuple(engine.get_binding_shape(0)), np.float32)
    out = np.zeros(tuple(engine.get_binding_shape(1)), np.float32)
    d_in, d_out = cuda_malloc(inp.nbytes), cuda_malloc(out.nbytes)
    bindings = [int(d_in.value), int(d_out.value)]

    pipe = ("nvarguscamerasrc sensor-id=0 ! "
            "video/x-raw(memory:NVMM),width=%d,height=%d,framerate=30/1 ! "
            "nvvidconv ! video/x-raw,width=%d,height=%d,format=BGRx ! "
            "videoconvert ! video/x-raw,format=BGR ! "
            "appsink drop=true max-buffers=1 sync=false"
            % (SRC_W, SRC_H, CAP_W, CAP_H))
    cap = cv2.VideoCapture(pipe, cv2.CAP_GSTREAMER)
    if not cap.isOpened():
        print("CAMERA FAILED TO OPEN")
        return 1

    pad = (NET - CAP_H) // 2
    canvas = np.full((NET, NET, 3), 114, np.uint8)   # allocated once

    def preprocess(frame):
        canvas[pad:pad + CAP_H] = frame              # only the centre changes
        return cv2.dnn.blobFromImage(canvas, 1.0 / 255.0, (NET, NET),
                                     swapRB=True, crop=False)

    node = None
    if not a.no_node:
        try:
            node = NodeReader(port=a.port)
            print("node on", node.open())
            node.start()
        except Exception as e:
            print("node unavailable: %s" % e)
            print("continuing on vision alone")
            node = None

    pub = None
    if not a.no_publish:
        pub = FirestorePublisher(verbose=True)
        pub.start_async()
        print("publishing to", pub.project)

    # The phone cannot discover the Jetson on its own, so the hub's address goes
    # out through Firestore, which is the only place the two ever meet.
    hub = None
    if not a.no_stream:
        try:
            # net, pad and src_size are what let the hub put a box in the same
            # place the cloud snapshot puts it. They are the letterbox geometry,
            # not a preference.
            hub = FrameHub(port=a.stream_port, fps_cap=a.stream_fps,
                           net=NET, pad=pad, src_size=(CAP_W, CAP_H),
                           names=NAMES, draw_boxes=True)
            hub.start()
            print("stream on", hub.url())
            if pub:
                # The publisher re-detects the address on every heartbeat, so a
                # DHCP lease change repairs itself without a restart.
                pub.set_stream(port=hub.port, path=hub.path, up=True)
        except Exception as e:
            print("stream unavailable: %s" % e)
            print("continuing without live video")
            hub = None

    # Push normally comes from the Cloud Function in CLOUD/functions, which
    # keeps the service account key off this device entirely. This path exists
    # so the two can be measured against each other: it sends at the instant the
    # event is written, without waiting for the write to commit and a trigger to
    # fire. Opt in, and do not run both at once or the phone buzzes twice.
    notifier = None
    if a.notify_edge:
        notifier = FcmSender(verbose=True)
        if notifier.available():
            print("push alerts via FCM topic", notifier.topic)
        else:
            print("push alerts off: set SAFEFIRE_FCM_KEY to enable")
            notifier = None

    layer = TemporalAlarm(a.k, a.n, IOU_MIN, conf)
    t_all = []
    frames = alarms = 0
    last_level = None
    last_report = time.time()
    t_start = time.time()

    print()
    print("running. Ctrl-C to stop.")
    print()
    try:
        while True:
            if a.seconds and time.time() - t_start > a.seconds:
                break
            t0 = time.time()
            ok, frame = cap.read()
            if not ok:
                print("grab failed")
                break
            x = preprocess(frame)
            cudart.cudaMemcpy(d_in, x.ctypes.data_as(ctypes.c_void_p), inp.nbytes, H2D)
            ctx.execute_v2(bindings)
            cudart.cudaMemcpy(out.ctypes.data_as(ctypes.c_void_p), d_out, out.nbytes, D2H)
            cudart.cudaDeviceSynchronize()
            keep = out[0][out[0][:, 4] >= conf]
            fired = layer.update(frames, keep)

            # Offered before the timing is taken, deliberately. Putting it after
            # would hide the stream's cost from the very numbers used to argue
            # the system runs in real time. It is measured or it is not claimed.
            # Same boxes the publisher uses, so the video and the event agree.
            if hub is not None:
                hub.offer(frame, keep if layer.active() else None)

            t_all.append(time.time() - t0)
            frames += 1
            if fired:
                alarms += 1

            sample = node.latest() if node else None
            level, why = fuse(layer.active(), sample)

            # Publish on a change, or on the publisher's own heartbeat. Nothing
            # here waits for the network.
            if pub and (level != last_level or (time.time() - last_report) >= 5.0):
                # Publish only what the persistence layer confirmed. Using the
                # raw per-frame array let a NORMAL document carry boxes while
                # its own rationale said nothing was above threshold, which is
                # a document that contradicts itself.
                dets = []
                for r in (keep[:8] if layer.active() else []):
                    dets.append({"label": NAMES[int(r[5])] if int(r[5]) < len(NAMES) else "obj",
                                 "confidence": round(float(r[4]), 4),
                                 "x": round(float(max(0, r[0])) / NET, 4),
                                 "y": round(float(max(0, r[1] - pad)) / CAP_H, 4),
                                 "w": round(float(r[2] - r[0]) / NET, 4),
                                 "h": round(float(r[3] - r[1]) / CAP_H, 4)})
                fps = 1.0 / np.mean(t_all[-60:]) if t_all else 0.0
                doc = pub.build_state(
                    level, detections=dets,
                    sensors=to_app_sensors(sample, node.age() if node else None),
                    frame_b64=None,          # the worker encodes it, see submit()
                    fps=round(fps, 2),
                    inference_ms=round(float(np.mean(t_all[-60:]) * 1000.0), 1),
                    rationale=why)
                # Hand over the frame, not a JPEG. Encoding here cost 350 ms on
                # every publishing frame and dropped throughput by 10 percent.
                if level != last_level:
                    # Encode for the event BEFORE handing the document to the
                    # worker. publish_event used to copy the dict while the
                    # worker was still about to inject frameB64 into it, so
                    # every stored alarm showed placeholder art, and the copy
                    # raced the worker. A transition is rare; paying the
                    # encode here costs nothing measurable.
                    ev = dict(doc)
                    okj, jbuf = cv2.imencode(
                        ".jpg", cv2.resize(frame, (FRAME_W, FRAME_H)),
                        [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_Q])
                    if okj:
                        b64 = pub.frame_to_b64(jbuf.tobytes())
                        if b64:
                            ev["frameB64"] = b64
                    eid = pub.publish_event(ev)
                    # Sent on the transition only, and with the id of the
                    # document that was actually stored, so tapping the
                    # notification opens that event and not a guess at it.
                    if notifier is not None and eid:
                        title, body = from_rationale(level, why)
                        notifier.notify(level, title, body, event_id=eid)
                pub.submit(doc, frame=frame, size=(FRAME_W, FRAME_H), quality=JPEG_Q)
                if level != last_level:
                    print("  [%7.1fs] %-9s -> %s" % (time.time() - t_start, level,
                                                     why["conclusion"][:52]))
                last_level = level
                last_report = time.time()

            if time.time() - last_report < 0.001 or frames % 100 == 0:
                pass
    except KeyboardInterrupt:
        print("\nstopping")
    finally:
        cap.release()
        if hub:
            # Before the publisher stops, so the last heartbeat can say the
            # stream is down instead of leaving the phone dialling a dead port.
            if pub:
                pub.set_stream(port=hub.port, path=hub.path, up=False)
            hub.stop()
        if node:
            node.stop()
        if pub:
            pub.stop()

    if t_all:
        arr = np.sort(np.array(t_all) * 1000.0)
        print()
        print("=" * 62)
        print("  frames %d   alarms raised %d   %.1f s" % (frames, alarms,
                                                           time.time() - t_start))
        print("  end to end  mean %.1f  median %.1f  p95 %.1f  p99 %.1f ms"
              % (arr.mean(), arr[len(arr) // 2],
                 arr[int(len(arr) * 0.95)], arr[int(len(arr) * 0.99)]))
        print("  throughput  %.2f FPS" % (1000.0 / arr.mean()))
        if notifier:
            print("  push        sent %s  errors %s  last %s"
                  % (notifier.stats["sent"], notifier.stats["errors"],
                     notifier.stats["last_error"]))
        if hub:
            # Reported as its own line so the stream's cost is visible next to
            # the detector's, instead of being absorbed into it silently.
            h = hub.health()
            print("  stream      accepted %s  encoded %s  served %s  "
                  "contended %s  peak clients %s"
                  % (h["accepted"], h["encoded"], h["served"],
                     h["contended"], h["peakClients"]))
            print("  stream cost encode mean %s ms  max %.1f ms  "
                  "delivered %.2f FPS"
                  % (h["encodeMsEma"], h["encodeMsMax"], h["fps"]))
        if pub:
            print("  publisher   writes %d  errors %d  dropped %d  last rtt %s ms"
                  % (pub.stats["writes"], pub.stats["errors"],
                     pub.stats["dropped"], pub.stats["last_rtt_ms"]))
        if node:
            print("  node        parsed %d  bad %d" % (node.stats["parsed"],
                                                       node.stats["bad"]))
        print("=" * 62)
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="SAFE-Fire full system")
    ap.add_argument("--engine", default=ENGINE)
    ap.add_argument("--conf", type=float, default=CONF_DEFAULT)
    ap.add_argument("--alpha", type=float, default=None,
                    help="use the conformal threshold for this alpha: 0.01 or 0.05")
    ap.add_argument("--k", type=int, default=K)
    ap.add_argument("--n", type=int, default=N)
    ap.add_argument("--port", default=None, help="serial port of the sensor node")
    ap.add_argument("--seconds", type=float, default=None)
    ap.add_argument("--no-node", action="store_true")
    ap.add_argument("--no-publish", action="store_true")
    ap.add_argument("--notify-edge", action="store_true",
                    help="send push from here instead of the Cloud Function, "
                         "for measuring the two paths against each other")
    ap.add_argument("--no-stream", action="store_true",
                    help="do not serve MJPEG video on the local network")
    ap.add_argument("--stream-port", type=int, default=8090)
    ap.add_argument("--stream-fps", type=float, default=5.0,
                    help="cap on frames handed to the stream, not on inference")
    sys.exit(main(ap.parse_args()))
