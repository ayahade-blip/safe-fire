#!/usr/bin/env python3
"""Build an INT8 engine for kd6 with entropy calibration on real fire images.

The pipeline is GPU-bound - 52 of 61 ms is inference - so INT8 is the only
change left that attacks the actual bottleneck. Everything else has already
been taken: the head is NMS-free, preprocessing is down to 8 ms, and the
transfers are half a millisecond.

Calibration images come from the TRAIN split, never from test. Calibrating on
test data would tune the quantisation ranges to the evaluation set and quietly
inflate every number that follows.
"""
import os, sys, ctypes
import numpy as np
import cv2
import tensorrt as trt

ONNX  = '/home/aya5/kd6_nomod.onnx'
OUT   = '/home/aya5/kd6_int8.engine'
CACHE = '/home/aya5/kd6_int8.cache'
CALIB_DIR = '/home/aya5/calib'
NET = 640
BATCH = 1

cudart = ctypes.CDLL('libcudart.so')
cudart.cudaMalloc.argtypes = [ctypes.POINTER(ctypes.c_void_p), ctypes.c_size_t]
cudart.cudaMemcpy.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                              ctypes.c_size_t, ctypes.c_int]
H2D = 1


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


class Calibrator(trt.IInt8EntropyCalibrator2):
    """Feeds real images through the same preprocessing the node will use.

    Calibrating with anything else - random tensors, a different normalisation -
    puts the quantisation ranges in the wrong place and the accuracy loss that
    follows gets blamed on INT8 rather than on the calibration.
    """

    def __init__(self, files):
        trt.IInt8EntropyCalibrator2.__init__(self)
        self.files = files
        self.idx = 0
        self.nbytes = BATCH * 3 * NET * NET * 4
        self.dev = cuda_malloc(self.nbytes)

    def get_batch_size(self):
        return BATCH

    def get_batch(self, names, p_str=None):
        if self.idx >= len(self.files):
            return None
        img = cv2.imread(self.files[self.idx])
        self.idx += 1
        if img is None:
            return self.get_batch(names)
        if self.idx % 32 == 0:
            print('  calibrated %d/%d' % (self.idx, len(self.files)))
            sys.stdout.flush()
        blob = cv2.dnn.blobFromImage(letterbox(img), 1.0 / 255.0, (NET, NET),
                                     swapRB=True, crop=False)
        blob = np.ascontiguousarray(blob, dtype=np.float32)
        cudart.cudaMemcpy(self.dev, blob.ctypes.data_as(ctypes.c_void_p),
                          self.nbytes, H2D)
        return [int(self.dev.value)]

    def read_calibration_cache(self):
        if os.path.exists(CACHE):
            print('using existing cache %s' % CACHE)
            return open(CACHE, 'rb').read()
        return None

    def write_calibration_cache(self, cache):
        open(CACHE, 'wb').write(cache)
        print('wrote cache %s (%d bytes)' % (CACHE, len(cache)))


files = sorted(os.path.join(CALIB_DIR, f)
               for f in os.listdir(CALIB_DIR) if f.endswith('.jpg'))
print('calibration images: %d' % len(files))

logger = trt.Logger(trt.Logger.INFO)
builder = trt.Builder(logger)
network = builder.create_network(
    1 << int(trt.NetworkDefinitionCreationFlag.EXPLICIT_BATCH))
parser = trt.OnnxParser(network, logger)

with open(ONNX, 'rb') as f:
    if not parser.parse(f.read()):
        for i in range(parser.num_errors):
            print('  parse error:', parser.get_error(i))
        sys.exit(1)
print('parsed ONNX: %d layers, in %s -> out %s'
      % (network.num_layers,
         network.get_input(0).shape, network.get_output(0).shape))

cfg = builder.create_builder_config()
cfg.max_workspace_size = 1 << 31          # 2 GB
cfg.set_flag(trt.BuilderFlag.INT8)
cfg.set_flag(trt.BuilderFlag.FP16)        # let TRT keep layers in FP16 where
                                          # INT8 would cost more than it saves
cfg.int8_calibrator = Calibrator(files)

print('building INT8 engine - this takes a while on a Nano ...')
sys.stdout.flush()
engine = builder.build_engine(network, cfg)
if engine is None:
    print('BUILD FAILED')
    sys.exit(1)

with open(OUT, 'wb') as f:
    f.write(engine.serialize())
print('wrote %s (%.1f MB)' % (OUT, os.path.getsize(OUT) / 1e6))
