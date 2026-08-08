#!/usr/bin/env python3
"""Image-level false-alarm rate of a TensorRT engine on the frozen negative sets.

    python3 neg_fpr.py /home/aya5/kd6_fp16.engine
    python3 neg_fpr.py /home/aya5/kd6_int8.engine

WHY THIS AND NOT THE 16-BOX IoU CHECK
    Matching 16 fire boxes says the engine still draws the same rectangles. It
    says nothing about the claim the thesis actually makes, which is about
    FALSE ALARMS. A quantisation that shifts confidences by a few thousandths
    on fire images could still push a lamp across the alarm threshold, and the
    box check would never see it. This measures the thing that is claimed.

    FPR here is image-level, identical in definition to the recorded numbers:
    the fraction of no-fire images with at least one detection above the
    threshold. Images are read straight out of the frozen zips so nothing can
    be silently swapped.
"""
import ctypes, os, sys, zipfile
import numpy as np
import cv2
import tensorrt as trt

ENGINE = sys.argv[1] if len(sys.argv) > 1 else '/home/aya5/kd6_fp16.engine'
SETS_DIR = '/home/aya5/negsets'
NET = 640
THRESHOLDS = (0.25, 0.50)

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


def letterbox(bgr, net=NET):
    h, w = bgr.shape[:2]
    r = min(net / float(h), net / float(w))
    nh, nw = int(round(h * r)), int(round(w * r))
    canvas = np.full((net, net, 3), 114, np.uint8)
    top, left = (net - nh) // 2, (net - nw) // 2
    canvas[top:top + nh, left:left + nw] = cv2.resize(bgr, (nw, nh))
    return canvas


logger = trt.Logger(trt.Logger.ERROR)
engine = trt.Runtime(logger).deserialize_cuda_engine(open(ENGINE, 'rb').read())
ctx = engine.create_execution_context()
inp = np.zeros(tuple(engine.get_binding_shape(0)), np.float32)
out = np.zeros(tuple(engine.get_binding_shape(1)), np.float32)
d_in, d_out = cuda_malloc(inp.nbytes), cuda_malloc(out.nbytes)
bindings = [int(d_in.value), int(d_out.value)]

print('engine: %s (%.2f MB)' % (os.path.basename(ENGINE),
                                os.path.getsize(ENGINE) / 1048576.0))
print()
print('%-22s %6s %10s %10s' % ('set', 'n', 'FPR@0.25', 'FPR@0.50'))
print('-' * 52)

zips = sorted(f for f in os.listdir(SETS_DIR) if f.endswith('.zip'))
rows = []
for zn in zips:
    z = zipfile.ZipFile(os.path.join(SETS_DIR, zn))
    names = [n for n in z.namelist() if n.lower().endswith(('.jpg', '.png', '.jpeg'))]
    maxconf = []
    for i, n in enumerate(names):
        buf = np.frombuffer(z.read(n), np.uint8)
        img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
        if img is None:
            continue
        blob = cv2.dnn.blobFromImage(letterbox(img), 1.0 / 255.0, (NET, NET),
                                     swapRB=True, crop=False)
        blob = np.ascontiguousarray(blob, dtype=np.float32)
        cudart.cudaMemcpy(d_in, blob.ctypes.data_as(ctypes.c_void_p), inp.nbytes, H2D)
        ctx.execute_v2(bindings)
        cudart.cudaMemcpy(out.ctypes.data_as(ctypes.c_void_p), d_out, out.nbytes, D2H)
        cudart.cudaDeviceSynchronize()
        maxconf.append(float(out[0][:, 4].max()))
        if (i + 1) % 100 == 0:
            sys.stdout.write('\r  %s %d/%d' % (zn, i + 1, len(names)))
            sys.stdout.flush()
    sys.stdout.write('\r' + ' ' * 60 + '\r')
    a = np.array(maxconf)
    fprs = [100.0 * (a >= t).mean() for t in THRESHOLDS]
    rows.append((zn, len(a), fprs, a))
    print('%-22s %6d %9.2f %% %9.2f %%'
          % (zn.replace('.zip', ''), len(a), fprs[0], fprs[1]))

print('-' * 52)
tot_n = sum(r[1] for r in rows)
allc = np.concatenate([r[3] for r in rows])
print('%-22s %6d %9.2f %% %9.2f %%'
      % ('ALL SETS POOLED', tot_n,
         100.0 * (allc >= 0.25).mean(), 100.0 * (allc >= 0.50).mean()))
print()
print('  max confidence over every negative image: %.4f' % allc.max())
print('  images above 0.50: %d of %d' % (int((allc >= 0.50).sum()), tot_n))
