#!/usr/bin/env python3
"""SAFE-Fire camera pipeline, v2 - preprocessing rewritten.

v1 measured 18.6 ms of preprocessing against 52.3 ms of inference: a quarter
of the frame budget spent before the GPU saw anything. The numpy version made
four full passes over ~5 MB per frame (fill, astype, divide, ascontiguousarray,
the last one forced by transpose leaving a non-contiguous view).

Two changes:
  1. The letterbox canvas is allocated once. The grey bands never change, so
     only the centre rows are rewritten per frame.
  2. cv2.dnn.blobFromImage replaces the numpy chain. It does swapRB, the
     /255 scale and the HWC->NCHW transpose in one SIMD-optimised C++ pass
     and returns a contiguous blob, so the extra copy disappears too.

Run with --old to measure the v1 path in the same session, on the same
frames, for an honest A/B rather than a comparison across two runs.
"""
import ctypes, os, sys, time
import numpy as np
import cv2
import tensorrt as trt

ENGINE = '/home/aya5/kd6_fp16.engine'
CONF, WARMUP, FRAMES = 0.25, 20, 200
SRC_W, SRC_H = 1640, 1232
CAP_W, CAP_H = 640, 480
NET = 640
OUTDIR = '/home/aya5/cam_run'
NAMES = ['fire', 'smoke']
USE_OLD = '--old' in sys.argv

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
    print('CAMERA FAILED TO OPEN'); sys.exit(1)

PAD = (NET - CAP_H) // 2
CANVAS = np.full((NET, NET, 3), 114, np.uint8)      # allocated once


def pre_new(frame):
    CANVAS[PAD:PAD + CAP_H] = frame                  # only the centre changes
    return cv2.dnn.blobFromImage(CANVAS, 1.0 / 255.0, (NET, NET),
                                 swapRB=True, crop=False)


def pre_old(frame):
    canvas = np.full((NET, NET, 3), 114, np.uint8)
    canvas[PAD:PAD + CAP_H] = frame
    x = canvas[:, :, ::-1].transpose(2, 0, 1).astype(np.float32) / 255.0
    return np.ascontiguousarray(x)[None]


preprocess = pre_old if USE_OLD else pre_new
os.makedirs(OUTDIR, exist_ok=True)
t_cap, t_pre, t_inf, t_post, t_all = [], [], [], [], []
det_frames = det_total = saved = 0
cls_hist = {}

for i in range(WARMUP + FRAMES):
    t0 = time.time()
    ok, frame = cap.read()
    t1 = time.time()
    if not ok:
        print('grab failed at %d' % i); break
    x = preprocess(frame)
    t2 = time.time()
    cudart.cudaMemcpy(d_in, x.ctypes.data_as(ctypes.c_void_p), inp.nbytes, H2D)
    ctx.execute_v2(bindings)
    cudart.cudaMemcpy(out.ctypes.data_as(ctypes.c_void_p), d_out, out.nbytes, D2H)
    cudart.cudaDeviceSynchronize()
    t3 = time.time()
    keep = out[0][out[0][:, 4] >= CONF]
    t4 = time.time()
    if i < WARMUP:
        continue
    t_cap.append(t1 - t0); t_pre.append(t2 - t1)
    t_inf.append(t3 - t2); t_post.append(t4 - t3); t_all.append(t4 - t0)
    if len(keep):
        det_frames += 1; det_total += len(keep)
        for r in keep:
            cls_hist[int(r[5])] = cls_hist.get(int(r[5]), 0) + 1
        if saved < 6:
            vis = frame.copy()
            for r in keep:
                p1 = (int(max(0, r[0])), int(max(0, r[1] - PAD)))
                p2 = (int(min(CAP_W, r[2])), int(min(CAP_H, r[3] - PAD)))
                cv2.rectangle(vis, p1, p2, (0, 255, 0), 2)
                c = int(r[5])
                cv2.putText(vis, '%s %.2f' % (NAMES[c] if c < len(NAMES)
                            else 'cls%d' % c, r[4]),
                            (p1[0], max(12, p1[1] - 5)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            cv2.imwrite('%s/det_%02d.jpg' % (OUTDIR, saved), vis)
            saved += 1

cap.release()


def stats(name, v):
    a = np.sort(np.array(v) * 1000.0)
    print('  %-12s mean %6.1f   median %6.1f   p95 %6.1f   max %6.1f  ms'
          % (name, a.mean(), a[len(a) // 2], a[int(len(a) * 0.95)], a[-1]))


print()
print('=' * 62)
print('  %s PREPROCESSING   (%d frames, MAXN)'
      % ('NUMPY (v1)' if USE_OLD else 'blobFromImage (v2)', len(t_all)))
print('=' * 62)
stats('capture', t_cap); stats('preprocess', t_pre)
stats('inference', t_inf); stats('postprocess', t_post); stats('END TO END', t_all)
print()
print('  end-to-end     %5.2f FPS' % (1.0 / np.mean(t_all)))
print('  inference only %5.2f FPS' % (1.0 / np.mean(t_inf)))
print('  detections: %d frames, %d boxes  %s'
      % (det_frames, det_total, cls_hist if cls_hist else ''))
print('=' * 62)
