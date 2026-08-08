#!/usr/bin/env python3
"""SAFE-Fire: camera -> TensorRT, measured stage by stage on the Jetson Nano.

trtexec already answered "how fast is the engine" (19.9 FPS at MAXN). The
question this answers is different and is the one the thesis actually needs:
what does the whole pipeline deliver once a real camera feeds it, and which
stage is the bottleneck. Those are not the same number, and quoting the
engine figure as a system figure would be wrong.

CUDA is driven through ctypes rather than pycuda: pycuda is not installed and
building it on the Nano costs ~20 minutes, while the four calls actually
needed here are a dozen lines.
"""
import ctypes, sys, time
import numpy as np
import cv2
import tensorrt as trt

ENGINE  = '/home/aya5/kd6_fp16.engine'
CONF    = 0.25
WARMUP  = 20
FRAMES  = 200
SRC_W, SRC_H = 1640, 1232        # full-FOV 4:3 sensor mode, no cropping
CAP_W, CAP_H = 640, 480          # nvvidconv scales on the GPU, free
NET     = 640
OUTDIR  = '/home/aya5/cam_run'

# class order must match the data.yaml the model was trained with - printed
# raw as well, so a wrong guess here cannot silently mislabel the results
NAMES = ['fire', 'smoke']

# ----------------------------------------------------------------- CUDA glue
cudart = ctypes.CDLL('libcudart.so')
cudart.cudaMalloc.argtypes = [ctypes.POINTER(ctypes.c_void_p), ctypes.c_size_t]
cudart.cudaMalloc.restype = ctypes.c_int
cudart.cudaMemcpy.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                              ctypes.c_size_t, ctypes.c_int]
cudart.cudaMemcpy.restype = ctypes.c_int
cudart.cudaDeviceSynchronize.restype = ctypes.c_int
H2D, D2H = 1, 2


def cuda_malloc(n):
    p = ctypes.c_void_p()
    if cudart.cudaMalloc(ctypes.byref(p), n):
        raise RuntimeError('cudaMalloc failed')
    return p


def to_dev(dst, a):
    if cudart.cudaMemcpy(dst, a.ctypes.data_as(ctypes.c_void_p), a.nbytes, H2D):
        raise RuntimeError('H2D failed')


def from_dev(a, src):
    if cudart.cudaMemcpy(a.ctypes.data_as(ctypes.c_void_p), src, a.nbytes, D2H):
        raise RuntimeError('D2H failed')


# -------------------------------------------------------------------- engine
print('loading engine ...')
logger = trt.Logger(trt.Logger.ERROR)
runtime = trt.Runtime(logger)
engine = runtime.deserialize_cuda_engine(open(ENGINE, 'rb').read())
ctx = engine.create_execution_context()

inp = np.zeros(tuple(engine.get_binding_shape(0)), np.float32)
out = np.zeros(tuple(engine.get_binding_shape(1)), np.float32)
d_in, d_out = cuda_malloc(inp.nbytes), cuda_malloc(out.nbytes)
bindings = [int(d_in.value), int(d_out.value)]
print('  input  %s' % (inp.shape,))
print('  output %s   (end-to-end, no NMS)' % (out.shape,))

# -------------------------------------------------------------------- camera
PIPE = ('nvarguscamerasrc sensor-id=0 ! '
        'video/x-raw(memory:NVMM),width=%d,height=%d,framerate=30/1 ! '
        'nvvidconv ! video/x-raw,width=%d,height=%d,format=BGRx ! '
        'videoconvert ! video/x-raw,format=BGR ! '
        'appsink drop=true max-buffers=1 sync=false'
        % (SRC_W, SRC_H, CAP_W, CAP_H))

print('opening camera ...')
cap = cv2.VideoCapture(PIPE, cv2.CAP_GSTREAMER)
if not cap.isOpened():
    print('CAMERA FAILED TO OPEN'); sys.exit(1)

PAD = (NET - CAP_H) // 2         # letterbox bands, 80 px top and bottom


def preprocess(frame):
    canvas = np.full((NET, NET, 3), 114, np.uint8)
    canvas[PAD:PAD + CAP_H] = frame
    x = canvas[:, :, ::-1].transpose(2, 0, 1).astype(np.float32) / 255.0
    return np.ascontiguousarray(x)[None]


def to_frame_coords(b):
    """640-space box back to the captured 640x480 frame."""
    return [b[0], b[1] - PAD, b[2], b[3] - PAD]


# ---------------------------------------------------------------- benchmark
import os
os.makedirs(OUTDIR, exist_ok=True)
t_cap, t_pre, t_inf, t_post, t_all = [], [], [], [], []
det_frames = 0
det_total = 0
cls_hist = {}
saved = 0

print('warming up %d frames ...' % WARMUP)
for i in range(WARMUP + FRAMES):
    t0 = time.time()

    ok, frame = cap.read()
    t1 = time.time()
    if not ok:
        print('frame grab failed at %d' % i); break

    x = preprocess(frame)
    t2 = time.time()

    to_dev(d_in, x)
    ctx.execute_v2(bindings)
    from_dev(out, d_out)
    cudart.cudaDeviceSynchronize()
    t3 = time.time()

    d = out[0]
    keep = d[d[:, 4] >= CONF]
    t4 = time.time()

    if i < WARMUP:
        if i == WARMUP - 1:
            print('measuring %d frames ...' % FRAMES)
        continue

    t_cap.append(t1 - t0); t_pre.append(t2 - t1)
    t_inf.append(t3 - t2); t_post.append(t4 - t3); t_all.append(t4 - t0)

    if len(keep):
        det_frames += 1
        det_total += len(keep)
        for r in keep:
            c = int(r[5])
            cls_hist[c] = cls_hist.get(c, 0) + 1
        if saved < 6:
            vis = frame.copy()
            for r in keep:
                b = to_frame_coords(r[:4])
                p1 = (int(max(0, b[0])), int(max(0, b[1])))
                p2 = (int(min(CAP_W, b[2])), int(min(CAP_H, b[3])))
                cv2.rectangle(vis, p1, p2, (0, 255, 0), 2)
                c = int(r[5])
                lbl = '%s %.2f' % (NAMES[c] if c < len(NAMES) else 'cls%d' % c, r[4])
                cv2.putText(vis, lbl, (p1[0], max(12, p1[1] - 5)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            cv2.imwrite('%s/det_%02d.jpg' % (OUTDIR, saved), vis)
            saved += 1
    elif saved < 6 and i == WARMUP:
        cv2.imwrite('%s/plain_first.jpg' % OUTDIR, frame)

cap.release()


def stats(name, v):
    a = np.array(v) * 1000.0
    a.sort()
    print('  %-12s mean %6.1f   median %6.1f   p95 %6.1f   max %6.1f  ms'
          % (name, a.mean(), a[len(a) // 2], a[int(len(a) * 0.95)], a[-1]))


print()
print('=' * 62)
print('  PER-STAGE TIMING   (%d frames, MAXN)' % len(t_all))
print('=' * 62)
stats('capture', t_cap)
stats('preprocess', t_pre)
stats('inference', t_inf)
stats('postprocess', t_post)
stats('END TO END', t_all)

fps = 1.0 / np.mean(t_all)
inf_fps = 1.0 / np.mean(t_inf)
print()
print('  end-to-end   %5.2f FPS' % fps)
print('  inference only %5.2f FPS   (what trtexec measures)' % inf_fps)
print('  the gap is what the camera and the CPU cost you')
print()
print('  frames with a detection : %d / %d' % (det_frames, len(t_all)))
print('  detections total        : %d' % det_total)
for c in sorted(cls_hist):
    print('    class %d (%s): %d' % (c, NAMES[c] if c < len(NAMES) else '?', cls_hist[c]))
print('  annotated frames saved  : %d in %s' % (saved, OUTDIR))
print('=' * 62)
