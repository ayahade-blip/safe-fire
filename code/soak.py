#!/usr/bin/env python3
"""Sustained-load soak: camera + TensorRT for N seconds, bucketed.

A 200-frame benchmark says what the node does cold. A fire detector runs for
months, so the question that matters is whether it still does it warm. FPS is
reported in 30 s buckets so any thermal decay shows up as a trend rather than
being averaged away, and tegrastats runs alongside for power and temperature.
"""
import ctypes, os, sys, time
import numpy as np
import cv2
import tensorrt as trt

ENGINE = '/home/aya5/kd6_fp16.engine'
DURATION = int(sys.argv[1]) if len(sys.argv) > 1 else 300
BUCKET = 30.0
CONF = 0.25
SRC_W, SRC_H, CAP_W, CAP_H, NET = 1640, 1232, 640, 480, 640
NAMES = ['flame', 'smoke']            # confirmed from the checkpoint

cudart = ctypes.CDLL('libcudart.so')
cudart.cudaMalloc.argtypes = [ctypes.POINTER(ctypes.c_void_p), ctypes.c_size_t]
cudart.cudaMemcpy.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                              ctypes.c_size_t, ctypes.c_int]
H2D, D2H = 1, 2


def cuda_malloc(n):
    p = ctypes.c_void_p()
    if cudart.cudaMalloc(ctypes.byref(p), n):
        raise RuntimeError('cudaMalloc')
    return p


logger = trt.Logger(trt.Logger.ERROR)
runtime = trt.Runtime(logger)
engine = runtime.deserialize_cuda_engine(open(ENGINE, 'rb').read())
ctx = engine.create_execution_context()
inp = np.zeros(tuple(engine.get_binding_shape(0)), np.float32)
out = np.zeros(tuple(engine.get_binding_shape(1)), np.float32)
d_in, d_out = cuda_malloc(inp.nbytes), cuda_malloc(out.nbytes)
bindings = [int(d_in.value), int(d_out.value)]

PIPE = ('nvarguscamerasrc sensor-id=0 ! '
        'video/x-raw(memory:NVMM),width=%d,height=%d,framerate=30/1 ! '
        'nvvidconv ! video/x-raw,width=%d,height=%d,format=BGRx ! '
        'videoconvert ! video/x-raw,format=BGR ! '
        'appsink drop=true max-buffers=1 sync=false'
        % (SRC_W, SRC_H, CAP_W, CAP_H))
cap = cv2.VideoCapture(PIPE, cv2.CAP_GSTREAMER)
if not cap.isOpened():
    print('CAMERA FAILED'); sys.exit(1)

PAD = (NET - CAP_H) // 2
CANVAS = np.full((NET, NET, 3), 114, np.uint8)

print('soaking for %d s ...' % DURATION)
print()
print('  window        frames    FPS    latency ms (mean / p95 / max)   dets')
print('  ------------  ------  -----    ----------------------------   ----')

t_start = time.time()
b_start = t_start
b_lat, b_det = [], 0
tot_frames = tot_det = 0
all_lat = []
buckets = []

while time.time() - t_start < DURATION:
    t0 = time.time()
    ok, frame = cap.read()
    if not ok:
        print('  grab failed'); break
    CANVAS[PAD:PAD + CAP_H] = frame
    blob = cv2.dnn.blobFromImage(CANVAS, 1.0 / 255.0, (NET, NET),
                                 swapRB=True, crop=False)
    cudart.cudaMemcpy(d_in, blob.ctypes.data_as(ctypes.c_void_p), inp.nbytes, H2D)
    ctx.execute_v2(bindings)
    cudart.cudaMemcpy(out.ctypes.data_as(ctypes.c_void_p), d_out, out.nbytes, D2H)
    cudart.cudaDeviceSynchronize()
    n = int((out[0][:, 4] >= CONF).sum())
    dt = time.time() - t0

    b_lat.append(dt); all_lat.append(dt)
    b_det += n; tot_det += n; tot_frames += 1

    if time.time() - b_start >= BUCKET:
        a = np.sort(np.array(b_lat) * 1000.0)
        fps = len(b_lat) / (time.time() - b_start)
        print('  %4.0f - %4.0f s  %6d  %5.2f    %6.1f / %6.1f / %6.1f          %4d'
              % (b_start - t_start, time.time() - t_start, len(b_lat), fps,
                 a.mean(), a[int(len(a) * 0.95)], a[-1], b_det))
        buckets.append(fps)
        b_start = time.time(); b_lat, b_det = [], 0

cap.release()
a = np.sort(np.array(all_lat) * 1000.0)
print()
print('=' * 62)
print('  SOAK SUMMARY   %d frames over %.0f s' % (tot_frames, time.time() - t_start))
print('=' * 62)
print('  mean FPS        %.2f' % (tot_frames / (time.time() - t_start)))
print('  latency  mean %.1f  median %.1f  p95 %.1f  p99 %.1f  max %.1f ms'
      % (a.mean(), a[len(a) // 2], a[int(len(a) * .95)],
         a[int(len(a) * .99)], a[-1]))
if len(buckets) >= 2:
    print('  first window %.2f FPS -> last window %.2f FPS   (%+.1f %%)'
          % (buckets[0], buckets[-1], 100.0 * (buckets[-1] - buckets[0]) / buckets[0]))
    print('  -> a falling trend here would be thermal. A flat one means the')
    print('     passive heatsink is enough for continuous operation.')
print('  detections total %d' % tot_det)
print('=' * 62)
