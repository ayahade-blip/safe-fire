#!/usr/bin/env python3
"""FP16 fidelity: TensorRT on the Jetson vs PyTorch FP32 on the desktop.

Both sides read the same 640x640 PNG, so letterboxing, resizing and JPEG
artefacts are all out of the picture. Whatever difference remains is the cost
of FP16 and of TensorRT's kernel choices - which is exactly the number the
thesis needs before it can claim the deployed model is the evaluated model.
"""
import ctypes, json, os, sys
import numpy as np
import cv2
import tensorrt as trt

ENGINE = '/home/aya5/kd6_fp16.engine'
DIR = '/home/aya5/fp16_check'
CONF = 0.25
IOU_MATCH = 0.5

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


def iou(a, b):
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    ua = ((a[2] - a[0]) * (a[3] - a[1]) +
          (b[2] - b[0]) * (b[3] - b[1]) - inter)
    return inter / ua if ua > 0 else 0.0


ref_doc = json.load(open(os.path.join(DIR, 'pytorch_ref.json')))
REF = ref_doc['ref']
print('reference: %s, conf %.2f, imgsz %d'
      % (ref_doc['weights'], ref_doc['conf'], ref_doc['imgsz']))
print('classes  : %s' % ref_doc['names'])
print()

logger = trt.Logger(trt.Logger.ERROR)
runtime = trt.Runtime(logger)
engine = runtime.deserialize_cuda_engine(open(ENGINE, 'rb').read())
ctx = engine.create_execution_context()
inp = np.zeros(tuple(engine.get_binding_shape(0)), np.float32)
out = np.zeros(tuple(engine.get_binding_shape(1)), np.float32)
d_in, d_out = cuda_malloc(inp.nbytes), cuda_malloc(out.nbytes)
bindings = [int(d_in.value), int(d_out.value)]

tot_ref = tot_trt = matched = 0
ious, dconfs = [], []
cls_mismatch = 0

print('%-12s %5s %5s %7s %9s %9s' %
      ('image', 'ref', 'trt', 'matched', 'min IoU', 'max dconf'))
print('-' * 56)

for name in sorted(REF):
    path = os.path.join(DIR, name + '.png')
    img = cv2.imread(path)
    if img is None:
        print('%-12s  MISSING' % name); continue

    blob = cv2.dnn.blobFromImage(img, 1.0 / 255.0, (640, 640),
                                 swapRB=True, crop=False)
    cudart.cudaMemcpy(d_in, blob.ctypes.data_as(ctypes.c_void_p), inp.nbytes, H2D)
    ctx.execute_v2(bindings)
    cudart.cudaMemcpy(out.ctypes.data_as(ctypes.c_void_p), d_out, out.nbytes, D2H)
    cudart.cudaDeviceSynchronize()

    trt_det = [(r[:4].tolist(), float(r[4]), int(r[5]))
               for r in out[0] if r[4] >= CONF]
    refs = REF[name]
    tot_ref += len(refs); tot_trt += len(trt_det)

    used = set()
    im_iou, im_dc = [], []
    for rd in refs:
        best, bi = 0.0, -1
        for j, (bb, cf, ck) in enumerate(trt_det):
            if j in used:
                continue
            v = iou(rd['box'], bb)
            if v > best:
                best, bi = v, j
        if bi >= 0 and best >= IOU_MATCH:
            used.add(bi)
            matched += 1
            ious.append(best); im_iou.append(best)
            dc = abs(trt_det[bi][1] - rd['conf'])
            dconfs.append(dc); im_dc.append(dc)
            if trt_det[bi][2] != rd['cls']:
                cls_mismatch += 1

    print('%-12s %5d %5d %7d %9s %9s'
          % (name, len(refs), len(trt_det), len(im_iou),
             '%.4f' % min(im_iou) if im_iou else '-',
             '%.4f' % max(im_dc) if im_dc else '-'))

print('-' * 56)
print()
print('=' * 56)
print('  FP16 (TensorRT, Jetson)  vs  FP32 (PyTorch, RTX 4060)')
print('=' * 56)
print('  reference boxes   : %d' % tot_ref)
print('  TensorRT boxes    : %d' % tot_trt)
print('  matched at IoU>%.1f: %d  (%.1f %% of reference)'
      % (IOU_MATCH, matched, 100.0 * matched / max(tot_ref, 1)))
print('  missed            : %d' % (tot_ref - matched))
print('  extra             : %d' % (tot_trt - matched))
print('  class disagreement: %d' % cls_mismatch)
if ious:
    a = np.array(ious)
    print('  IoU  mean %.4f   min %.4f   worst-case gap %.4f'
          % (a.mean(), a.min(), 1.0 - a.min()))
if dconfs:
    d = np.array(dconfs)
    print('  |dconf| mean %.4f   max %.4f' % (d.mean(), d.max()))
print('=' * 56)
