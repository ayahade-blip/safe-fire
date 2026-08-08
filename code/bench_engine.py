#!/usr/bin/env python3
"""Camera -> engine benchmark for ANY engine, stage by stage.

    python3 bench_engine.py /home/aya5/kd6_fp16.engine [frames]
    python3 bench_engine.py /home/aya5/kd6_int8.engine [frames]

Same pipeline as cam_infer2.py, with the engine as an argument so two
precisions can be compared on the same camera, the same scene and the same
preprocessing rather than across two separate runs.
"""
import ctypes, os, sys, time
import numpy as np
import cv2
import tensorrt as trt

ENGINE = sys.argv[1] if len(sys.argv) > 1 else '/home/aya5/kd6_fp16.engine'
FRAMES = int(sys.argv[2]) if len(sys.argv) > 2 else 200
WARMUP, CONF = 20, 0.25
SRC_W, SRC_H, CAP_W, CAP_H, NET = 1640, 1232, 640, 480, 640

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
engine = trt.Runtime(logger).deserialize_cuda_engine(open(ENGINE, 'rb').read())
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
t_cap, t_pre, t_inf, t_post, t_all = [], [], [], [], []
dets = 0

for i in range(WARMUP + FRAMES):
    t0 = time.time()
    ok, frame = cap.read()
    t1 = time.time()
    if not ok:
        print('grab failed'); break
    CANVAS[PAD:PAD + CAP_H] = frame
    blob = cv2.dnn.blobFromImage(CANVAS, 1.0/255.0, (NET, NET), swapRB=True, crop=False)
    t2 = time.time()
    cudart.cudaMemcpy(d_in, blob.ctypes.data_as(ctypes.c_void_p), inp.nbytes, H2D)
    ctx.execute_v2(bindings)
    cudart.cudaMemcpy(out.ctypes.data_as(ctypes.c_void_p), d_out, out.nbytes, D2H)
    cudart.cudaDeviceSynchronize()
    t3 = time.time()
    n = int((out[0][:, 4] >= CONF).sum())
    t4 = time.time()
    if i < WARMUP:
        continue
    t_cap.append(t1-t0); t_pre.append(t2-t1); t_inf.append(t3-t2)
    t_post.append(t4-t3); t_all.append(t4-t0); dets += n

cap.release()


def stats(n, v):
    a = np.sort(np.array(v) * 1000.0)
    print('  %-12s mean %6.1f   median %6.1f   p95 %6.1f   max %6.1f  ms'
          % (n, a.mean(), a[len(a)//2], a[int(len(a)*0.95)], a[-1]))


print()
print('=' * 62)
print('  %s   %d frames' % (os.path.basename(ENGINE), len(t_all)))
print('=' * 62)
stats('capture', t_cap); stats('preprocess', t_pre)
stats('inference', t_inf); stats('postprocess', t_post); stats('END TO END', t_all)
print()
print('  end-to-end     %5.2f FPS' % (1.0 / np.mean(t_all)))
print('  inference only %5.2f FPS' % (1.0 / np.mean(t_inf)))
print('  detections     %d' % dets)
print('=' * 62)
