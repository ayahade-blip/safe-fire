# -*- coding: utf-8 -*-
"""SAFE_FIRE_SCOPUS shared library.

The Colab notebooks write this file to /content/sfs/sfs_lib.py and import it, so
every notebook uses exactly the same data preparation, training recipe and
evaluation protocol.

Rules this file follows:
  * SAFE_FIRE (the original Drive folder) is READ ONLY. Nothing is ever written there.
  * Every output goes under SAFE_FIRE_SCOPUS.
  * The training recipe is the one of SAFE_FIRE_MASTER_CLEAN.ipynb (batch 32, AdamW, ...).
  * The evaluation protocol is the one of the paper: per-image max confidence at
    extraction 0.01 for negatives, IoU >= 0.5 instance matching for positives.
"""
import argparse
import csv
import datetime
import hashlib
import json
import math
import os
import random
import shutil
import sys
import time
import traceback
import zipfile
from pathlib import Path

IMG_EXT = ('.jpg', '.jpeg', '.png', '.bmp', '.webp')
VID_EXT = ('.avi', '.mp4', '.mov', '.mkv', '.mpg', '.mpeg', '.wmv', '.flv', '.3gp', '.m4v')

SRC = Path(os.environ.get('SFS_SRC', '/content/drive/MyDrive/SAFE_FIRE'))
OUT = Path(os.environ.get('SFS_OUT', '/content/drive/MyDrive/SAFE_FIRE_SCOPUS'))
LOC = Path(os.environ.get('SFS_LOCAL', '/content/sfs'))

# The recipe of SAFE_FIRE_MASTER_CLEAN.ipynb (cell S1). Device and workers come from
# OUT/config/train_config.json so that every run of the revision uses identical settings.
RECIPE = dict(
    imgsz=640, batch=32, epochs=300, patience=50,
    optimizer='AdamW', lr0=0.001, lrf=0.01, weight_decay=0.05,
    warmup_epochs=3.0, cos_lr=True,
    mosaic=1.0, mixup=0.0, copy_paste=0.1, close_mosaic=10,
    hsv_h=0.015, hsv_s=0.7, hsv_v=0.4,
    fliplr=0.5, flipud=0.0, erasing=0.4,
    amp=True, cache='ram',
)
ULTRALYTICS_VERSION = '8.4.90'          # the version that trained every run in the paper
KD_DIS = 6.0                            # the deployed student kd6
TEACHER_RUN = 'showcase__xs960__s42'    # yolo26s @960, trained on the 3,276-image union

SUITE_ZIPS = {
    'hn_holdout': 'eval_suite_v2/hn_holdout_500.zip',
    'novel': 'eval_suite_v2/novel_firelike.zip',
    'dfire_neg': 'eval_suite_v2/dfire_neg_1500.zip',
    'mined_dev': 'eval_suite_v2/mined_dev.zip',
}
FRESH_NAMES = ('F_hard', 'F_novel', 'F_cross')

# Where each negative image of the training sets comes from (zip on Drive).
SOURCES = {
    'hn_pool': SRC / 'train_neg_v2' / 'hn_train_pool.zip',
    'hits': SRC / 'safemine_v2' / 'mining' / 'round0_hits.zip',
    'randbg': SRC / 'train_neg_v2' / 'randbg_pool.zip',
    'coco_extra': OUT / 'extra' / 'coco_extra.zip',
}


# --------------------------------------------------------------------- basics
def log(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')


def imgs_in(folder):
    folder = Path(folder)
    if not folder.exists():
        return []
    return sorted(p for p in folder.rglob('*') if p.suffix.lower() in IMG_EXT)


def read_json(p, default=None):
    p = Path(p)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding='utf-8'))


def write_json(p, obj):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + '.tmp')
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding='utf-8')
    os.replace(tmp, p)


def write_csv(p, header, rows):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + '.tmp')
    with open(tmp, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    os.replace(tmp, p)


def atomic_copy(src, dst):
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.name + '.tmp')
    shutil.copy2(src, tmp)
    os.replace(tmp, dst)


def link(src, dst):
    """Symlink on Linux (Colab); hard link or copy where symlinks are not allowed."""
    try:
        os.symlink(src, dst)
    except OSError:
        try:
            os.link(src, dst)
        except OSError:
            shutil.copy2(src, dst)


def sha256_file(p, chunk=1 << 20):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def dhash(p, size=8):
    """64-bit difference hash, for near-duplicate detection (Hamming distance).

    Written against numpy rather than Image.getdata()/Image.LANCZOS so that it gives the
    same bits on every Pillow version Colab may install.
    """
    import numpy as np
    from PIL import Image
    lanczos = getattr(Image, 'Resampling', Image).LANCZOS
    a = np.asarray(Image.open(p).convert('L').resize((size + 1, size), lanczos), dtype=np.int16)
    bits = 0
    for b in (a[:, :-1] > a[:, 1:]).ravel():
        bits = (bits << 1) | int(b)
    return bits


def robust_extract(zip_path, dest):
    """Same behaviour as SAFE_FIRE_MASTER: if the archive has a single top folder, return it."""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(dest)
    entries = [p for p in dest.iterdir() if not p.name.startswith('.')]
    if len(entries) == 1 and entries[0].is_dir():
        return entries[0]
    return dest


def extract_members(zip_path, names, dest):
    """Extract only the listed basenames (flat). Idempotent."""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    have = {p.name for p in dest.iterdir()}
    need = set(names) - have
    if not need:
        return dest
    with zipfile.ZipFile(zip_path) as z:
        for m in z.infolist():
            b = os.path.basename(m.filename)
            if b in need:
                with z.open(m) as fs, open(dest / b, 'wb') as fd:
                    shutil.copyfileobj(fs, fd)
                need.discard(b)
    if need:
        raise RuntimeError('%d names not found in %s, e.g. %s' % (len(need), zip_path, sorted(need)[:3]))
    return dest


def zip_flat(paths, zpath, arcnames=None):
    zpath = Path(zpath)
    zpath.parent.mkdir(parents=True, exist_ok=True)
    tmp = zpath.with_name(zpath.name + '.tmp')
    with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_STORED) as z:
        for i, p in enumerate(paths):
            z.write(p, arcnames[i] if arcnames else Path(p).name)
    os.replace(tmp, zpath)
    return zpath


# ------------------------------------------------------------------ hardware
def hardware():
    info = {'cpu_count': os.cpu_count()}
    try:
        import psutil
        info['ram_gb'] = round(psutil.virtual_memory().total / 1e9, 1)
    except Exception:
        info['ram_gb'] = None
    try:
        import torch
        info['torch'] = torch.__version__
        info['cuda'] = torch.version.cuda
        if torch.cuda.is_available():
            p = torch.cuda.get_device_properties(0)
            info['gpu'] = p.name
            info['gpu_gb'] = round(p.total_memory / 1e9, 1)
            info['capability'] = '%d.%d' % torch.cuda.get_device_capability(0)
    except Exception as e:
        info['torch_error'] = repr(e)
    try:
        import ultralytics
        info['ultralytics'] = ultralytics.__version__
    except Exception:
        pass
    return info


def gpu_selftest():
    """A Blackwell GPU needs a CUDA 12.8+ build of torch; fail loudly here, not mid-training."""
    import torch
    assert torch.cuda.is_available(), 'No GPU. Runtime > Change runtime type > G4 GPU.'
    x = torch.randn(64, 3, 64, 64, device='cuda')
    conv = torch.nn.Conv2d(3, 8, 3).cuda()
    with torch.no_grad(), torch.autocast('cuda', dtype=torch.float16):
        y = conv(x)
    torch.cuda.synchronize()
    return float(y.float().abs().mean())


# ------------------------------------------------------------------ datasets
def ensure_home_fire():
    hf = LOC / 'pools' / 'hf'
    if not (hf / 'test' / 'images').exists():
        log('extracting home_fire.zip')
        root = robust_extract(SRC / 'datasets' / 'home_fire.zip', hf)
        if root != hf:
            for item in list(root.iterdir()):
                shutil.move(str(item), str(hf / item.name))
            root.rmdir()
    assert (hf / 'train' / 'images').exists() and (hf / 'test' / 'images').exists(), 'unexpected home_fire layout'
    y = hf / 'data.yaml'
    txt = ('path: %s\ntrain: train/images\nval: val/images\ntest: test/images\n'
           'names:\n  0: flame\n  1: smoke\nnc: 2\n' % hf)
    if not y.exists() or y.read_text() != txt:
        tmp = hf / ('data.yaml.tmp%d' % os.getpid())
        tmp.write_text(txt)
        os.replace(tmp, y)
    return hf


def ensure_suites():
    out = {}
    for name, rel in SUITE_ZIPS.items():
        d = LOC / 'pools' / 'suite' / name
        if not imgs_in(d):
            log('extracting', rel)
            robust_extract(SRC / rel, d)
        out[name] = d
    return out


def ensure_fresh():
    out = {}
    for name in FRESH_NAMES:
        z = OUT / 'fresh_suite' / (name + '.zip')
        if not z.exists():
            continue
        d = LOC / 'pools' / 'fresh' / name
        if not imgs_in(d):
            robust_extract(z, d)
        out[name] = d
    return out


def find_dfire_root():
    raw = LOC / 'pools' / 'dfire_raw'
    if not raw.exists() or not any(raw.iterdir()):
        log('extracting dfire_raw.zip (large)')
        robust_extract(SRC / 'datasets' / 'dfire_raw.zip', raw)
    return raw


def dfire_split_dirs(split):
    """(images_dir, labels_dir) of a D-Fire split, searched robustly."""
    raw = find_dfire_root()
    alias = {'test': ('test',), 'train': ('train', 'training')}[split]
    for lbl in sorted(raw.rglob('labels')):
        if lbl.is_dir() and lbl.parent.name.lower() in alias and (lbl.parent / 'images').is_dir():
            return lbl.parent / 'images', lbl
    for img in sorted(raw.rglob('images')):
        sub = img / split
        if sub.is_dir() and (img.parent / 'labels' / split).is_dir():
            return sub, img.parent / 'labels' / split
    raise RuntimeError('D-Fire %s split not found under %s' % (split, raw))


def ensure_dfire_pos():
    """D-Fire TEST positives with classes remapped to ours (D-Fire 0=smoke,1=fire -> 0=flame,1=smoke)."""
    d = LOC / 'pools' / 'dfire_pos'
    if (d / 'labels').exists() and any((d / 'labels').iterdir()):
        return d
    src_img, src_lbl = dfire_split_dirs('test')
    (d / 'images').mkdir(parents=True, exist_ok=True)
    (d / 'labels').mkdir(parents=True, exist_ok=True)
    remap = {0: 1, 1: 0}
    kept = 0
    for lp in sorted(src_lbl.glob('*.txt')):
        txt = lp.read_text().strip()
        if not txt:
            continue
        out = []
        for line in txt.splitlines():
            p = line.split()
            if len(p) >= 5:
                try:
                    c = int(float(p[0]))
                except ValueError:
                    continue
                if c in remap:
                    out.append(' '.join([str(remap[c])] + p[1:5]))
        if not out:
            continue
        ip = next((src_img / (lp.stem + e) for e in ('.jpg', '.jpeg', '.png', '.JPG')
                   if (src_img / (lp.stem + e)).exists()), None)
        if ip is None:
            continue
        (d / 'labels' / lp.name).write_text('\n'.join(out) + '\n')
        if not (d / 'images' / ip.name).exists():
            link(ip, d / 'images' / ip.name)
        kept += 1
    log('D-Fire test positives:', kept)
    return d


def ensure_sources(keys=('hn_pool', 'hits', 'randbg', 'coco_extra')):
    out = {}
    for k in keys:
        z = SOURCES[k]
        d = LOC / 'pools' / 'src' / k
        if not z.exists():
            log('source not available (yet):', k, z)
            continue
        if not imgs_in(d):
            log('extracting source', k)
            root = robust_extract(z, d)
            if root != d:
                for item in list(root.iterdir()):
                    shutil.move(str(item), str(d / item.name))
                root.rmdir()
        out[k] = d
    return out


def neg_items(set_name):
    """[(path, name)] for a negative set, from OUT/manifests/neg_sets.json."""
    if set_name in ('N0', 'none'):
        return []
    ms = read_json(OUT / 'manifests' / 'neg_sets.json', {})
    if set_name not in ms:
        extra = read_json(OUT / 'manifests' / ('neg_%s.json' % set_name))
        if extra is None:
            raise KeyError('negative set %s has no manifest yet' % set_name)
        ms[set_name] = extra
    items = []
    for src_key, name in ms[set_name]['items']:
        p = LOC / 'pools' / 'src' / src_key / name
        if not p.exists():
            raise FileNotFoundError('missing %s (run the preparation cell)' % p)
        items.append((p, name))
    return items


def build_job_dataset(run_id, items, hf):
    """A private dataset per run: symlinked images, copied labels, its own label caches.

    Private copies keep parallel runs from racing on Ultralytics' labels.cache files.
    """
    root = LOC / 'jobs' / run_id / 'data'
    marker = root / 'READY'
    if marker.exists():
        return root / 'data.yaml'
    shutil.rmtree(root, ignore_errors=True)
    for split in ('train', 'val', 'test'):
        (root / 'images' / split).mkdir(parents=True)
        (root / 'labels' / split).mkdir(parents=True)
        for img in imgs_in(hf / split / 'images'):
            link(img, root / 'images' / split / ('hf__' + img.name))
            lbl = hf / split / 'labels' / (img.stem + '.txt')
            if lbl.exists():
                shutil.copy2(lbl, root / 'labels' / split / ('hf__' + img.stem + '.txt'))
    for p, name in items:
        link(p, root / 'images' / 'train' / ('neg__' + name))
        (root / 'labels' / 'train' / ('neg__' + Path(name).stem + '.txt')).write_text('')
    y = root / 'data.yaml'
    y.write_text('path: %s\ntrain: images/train\nval: images/val\ntest: images/test\n'
                 'names:\n  0: flame\n  1: smoke\nnc: 2\n' % root)
    marker.write_text(now_iso())
    return y


# ------------------------------------------------------------------ evaluation
def _iou_mat(a, b):
    import numpy as np
    if len(a) == 0 or len(b) == 0:
        return np.zeros((len(a), len(b)))
    x1 = np.maximum(a[:, None, 0], b[None, :, 0])
    y1 = np.maximum(a[:, None, 1], b[None, :, 1])
    x2 = np.minimum(a[:, None, 2], b[None, :, 2])
    y2 = np.minimum(a[:, None, 3], b[None, :, 3])
    inter = np.clip(x2 - x1, 0, None) * np.clip(y2 - y1, 0, None)
    aa = (a[:, 2] - a[:, 0]) * (a[:, 3] - a[:, 1])
    bb = (b[:, 2] - b[:, 0]) * (b[:, 3] - b[:, 1])
    return inter / np.clip(aa[:, None] + bb[None, :] - inter, 1e-9, None)


def _gt(lbl):
    import numpy as np
    rows = []
    if Path(lbl).exists():
        for ln in Path(lbl).read_text().split('\n'):
            v = ln.split()
            if len(v) >= 5:
                rows.append([float(x) for x in v[:5]])
    return np.array(rows) if rows else np.zeros((0, 5))


def _predict_safe(model, paths, imgsz, conf):
    """Predict a chunk; on a corrupt file fall back to one image at a time."""
    try:
        return list(zip(paths, model.predict([str(x) for x in paths], imgsz=imgsz, conf=conf,
                                             verbose=False, save=False)))
    except Exception:
        out = []
        for p in paths:
            try:
                out.append((p, model.predict(str(p), imgsz=imgsz, conf=conf, verbose=False, save=False)[0]))
            except Exception as e:
                log('  skipped unreadable image', Path(p).name, repr(e)[:80])
        return out


def scan_neg(model, folder, out_csv, imgsz=640, conf=0.01, chunk=64, boxes_csv=None):
    """Per-image max box confidence, exactly the protocol of the paper (scan_max_conf).

    boxes_csv (optional) also keeps every box >= conf on these images, so that
    false positives per image (FPPI) and Caltech-style curves can be computed.
    """
    out_csv = Path(out_csv)
    if out_csv.exists() and (boxes_csv is None or Path(boxes_csv).exists()):
        return
    rows, brows = [], []
    fs = imgs_in(folder)
    for i in range(0, len(fs), chunk):
        for src, r in _predict_safe(model, fs[i:i + chunk], imgsz, conf):
            name = Path(src).name
            if len(r.boxes):
                cs = r.boxes.conf.cpu().numpy()
                ks = r.boxes.cls.cpu().numpy()
                rows.append((name, float(cs.max())))
                brows.extend((name, round(float(c), 5), int(k)) for c, k in zip(cs, ks))
            else:
                rows.append((name, 0.0))
    write_csv(out_csv, ['image', 'max_conf'], rows)
    if boxes_csv is not None:
        write_csv(boxes_csv, ['image', 'conf', 'cls'], brows)


def match_pos(model, img_dir, lbl_dir, out_csv, imgsz=640, conf=0.01, iou_t=0.5, chunk=64):
    """One row per ground-truth box: best matching confidence, class-agnostic and same-class."""
    import numpy as np
    out_csv = Path(out_csv)
    if out_csv.exists():
        return
    rows = []
    fs = imgs_in(img_dir)
    for i in range(0, len(fs), chunk):
        for f, r in _predict_safe(model, fs[i:i + chunk], imgsz, conf):
            f = Path(f)
            g = _gt(Path(lbl_dir) / (f.stem + '.txt'))
            if len(g) == 0:
                continue
            h, w = r.orig_shape
            gx = np.stack([(g[:, 1] - g[:, 3] / 2) * w, (g[:, 2] - g[:, 4] / 2) * h,
                           (g[:, 1] + g[:, 3] / 2) * w, (g[:, 2] + g[:, 4] / 2) * h], 1)
            if r.boxes is not None and len(r.boxes):
                pb = r.boxes.xyxy.cpu().numpy()
                pc = r.boxes.conf.cpu().numpy()
                pk = r.boxes.cls.cpu().numpy().astype(int)
            else:
                pb, pc, pk = np.zeros((0, 4)), np.zeros(0), np.zeros(0, int)
            M = _iou_mat(gx, pb)
            for j in range(len(gx)):
                hit = M[j] >= iou_t if len(pb) else np.zeros(0, bool)
                ca = float(pc[hit].max()) if hit.any() else 0.0
                same = hit & (pk == int(g[j, 0])) if len(pb) else hit
                cs = float(pc[same].max()) if same.any() else 0.0
                bc = int(pk[hit][pc[hit].argmax()]) if hit.any() else -1
                rows.append((f.name, j, int(g[j, 0]), round(float(g[j, 3] * g[j, 4]), 8),
                             round(ca, 6), round(cs, 6), bc))
    write_csv(out_csv, ['img', 'gt', 'cls', 'area', 'conf_any', 'conf_same', 'best_cls'], rows)


def val_metrics(model, data_yaml, imgsz, out_json, tag):
    out_json = Path(out_json)
    if out_json.exists():
        return read_json(out_json)
    v = model.val(data=str(data_yaml), split='test', imgsz=imgsz, verbose=False, plots=False,
                  project=str(LOC / 'tmp' / 'val'), name=tag, exist_ok=True)
    p, r = float(v.box.mp), float(v.box.mr)
    ap50, ap = v.box.ap50, v.box.ap
    res = {'mAP50': round(float(v.box.map50), 4), 'mAP5095': round(float(v.box.map), 4),
           'precision': round(p, 4), 'recall': round(r, 4),
           'f1': round(2 * p * r / (p + r), 4) if p + r > 0 else 0.0,
           'flame_AP50': round(float(ap50[0]), 4) if len(ap50) > 0 else None,
           'smoke_AP50': round(float(ap50[1]), 4) if len(ap50) > 1 else None,
           'flame_AP5095': round(float(ap[0]), 4) if len(ap) > 0 else None,
           'smoke_AP5095': round(float(ap[1]), 4) if len(ap) > 1 else None}
    try:
        res['params_M'] = round(sum(x.numel() for x in model.model.parameters()) / 1e6, 3)
    except Exception:
        pass
    write_json(out_json, res)
    return res


def evaluate_model(weights, imgsz, out_dir, tag, hf=None, suites=None, fresh=None, dfire=None):
    """Everything the revision analyses need from one set of weights."""
    from ultralytics import YOLO
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    model = YOLO(str(weights))
    t0 = time.time()
    if hf is not None:
        val_metrics(model, hf / 'data.yaml', imgsz, out_dir / 'val_test.json', tag)
        match_pos(model, hf / 'test' / 'images', hf / 'test' / 'labels', out_dir / 'test_pos.csv', imgsz)
    for name, d in list((suites or {}).items()) + list((fresh or {}).items()):
        scan_neg(model, d, out_dir / ('neg_%s.csv' % name), imgsz,
                 boxes_csv=out_dir / ('negboxes_%s.csv' % name))
    if dfire is not None:
        match_pos(model, dfire / 'images', dfire / 'labels', out_dir / 'dfire_pos.csv', imgsz)
        scan_neg(model, dfire / 'images', out_dir / 'dfire_pos_img.csv', imgsz)
    return round(time.time() - t0, 1)


# ------------------------------------------------------------------ training
def train_config():
    cfg = read_json(OUT / 'config' / 'train_config.json')
    if cfg is None:
        raise RuntimeError('OUT/config/train_config.json missing: run the settings cell of notebook 03 or 04')
    return cfg


def ensure_train_config(hw):
    """One configuration for EVERY revision run, whichever notebook or GPU starts first.

    workers=8 is the value of SAFE_FIRE_MASTER and does not depend on the machine, so the
    runs of SFS_03 and SFS_04 stay identical even if they are run on different runtimes.
    """
    import ultralytics
    p = OUT / 'config' / 'train_config.json'
    cfg = read_json(p)
    if cfg is None:
        cfg = {'ultralytics': ultralytics.__version__, 'workers': 8, 'sync_every_s': 180, 'eval_dfire': True,
               'recipe': RECIPE, 'kd_dis': KD_DIS, 'teacher': TEACHER_RUN, 'created_utc': now_iso(), 'created_on': hw}
        write_json(p, cfg)
    if cfg['ultralytics'] != ultralytics.__version__:
        raise RuntimeError('this runtime has ultralytics %s, the revision runs use %s'
                           % (ultralytics.__version__, cfg['ultralytics']))
    return cfg


def parallel_slots(hw, cfg):
    """How many runs fit side by side on this machine (CPU for the data loaders, RAM cache, GPU memory)."""
    by_cpu = max(1, ((hw.get('cpu_count') or 8) - 2) // (cfg['workers'] + 1))
    by_ram = max(1, int(((hw.get('ram_gb') or 32) - 12) // 14))
    by_gpu = max(1, int(((hw.get('gpu_gb') or 16) - 4) // 8))
    return min(by_cpu, by_ram, by_gpu, 8), {'cpu': by_cpu, 'ram': by_ram, 'gpu': by_gpu}


def benchmark(job, epochs=4):
    """Optional: train `epochs` epochs of one job in a scratch folder and time them.

    Nothing is written to runs/; it only answers "how fast is this runtime" before the
    queue starts, so two runtime types (e.g. G4 and L4) can be compared on cost per run.
    """
    import torch
    from ultralytics import YOLO
    cfg = train_config()
    hf = ensure_home_fire()
    data_yaml = build_job_dataset('bench__' + job['run_id'], neg_items(job['neg_set']), hf)
    ends = []
    model = YOLO(str(LOC / 'pretrained' / job['base']))
    model.add_callback('on_train_epoch_end', lambda tr: ends.append(time.time()))
    args = dict(RECIPE)
    args.update(device=0, workers=cfg['workers'], data=str(data_yaml), seed=int(job['seed']), epochs=epochs,
                project=str(LOC / 'bench'), name=job['run_id'], exist_ok=True, plots=False, verbose=False, save=False)
    if job.get('kd'):
        args.update(distill_model=str(LOC / 'pretrained' / 'teacher.pt'), dis=float(job.get('dis', KD_DIS)))
    torch.cuda.reset_peak_memory_stats()
    t0 = time.time()
    model.train(**args)
    steps = [b - a for a, b in zip(ends[:-1], ends[1:])]
    spe = sorted(steps)[len(steps) // 2] if steps else float('nan')
    res = {'run': job['run_id'], 'gpu': hardware().get('gpu'), 'seconds_per_epoch': round(spe, 1),
           'startup_seconds': round(ends[0] - t0 - spe, 1) if ends else None,
           'gpu_peak_gb_one_run': round(torch.cuda.max_memory_allocated() / 1e9, 2),
           'hours_per_full_run_alone': round(spe * EXPECTED_EPOCHS[bool(job.get('kd'))] / 3600, 2)}
    del model
    torch.cuda.empty_cache()
    return res


def train_job(job):
    """Train one run, resumable across Colab sessions, then evaluate it."""
    from ultralytics import YOLO
    run_id = job['run_id']
    ddir = OUT / 'runs' / run_id
    ddir.mkdir(parents=True, exist_ok=True)
    if (ddir / 'DONE.json').exists():
        log(run_id, 'already done')
        return 0
    cfg = train_config()
    import ultralytics
    if ultralytics.__version__ != cfg['ultralytics']:
        raise RuntimeError('ultralytics %s but the revision runs use %s' % (ultralytics.__version__, cfg['ultralytics']))
    hf = ensure_home_fire()
    items = neg_items(job['neg_set'])
    data_yaml = build_job_dataset(run_id, items, hf)
    write_json(ddir / 'job.json', dict(job, n_negatives=len(items), data_yaml=str(data_yaml)))
    lrun = LOC / 'runs' / run_id
    llast = lrun / 'weights' / 'last.pt'
    lbest = lrun / 'weights' / 'best.pt'
    timing = read_json(ddir / 'timing.json', {'train_wall_s': 0.0, 'segments': 0, 'resumed': False})

    if not (ddir / 'TRAINED.json').exists():
        state = {'t': time.time()}
        seg_start = time.time()

        def sync(trainer):
            if time.time() - state['t'] < cfg.get('sync_every_s', 180):
                return
            state['t'] = time.time()
            last = Path(getattr(trainer, 'last', lrun / 'weights' / 'last.pt'))
            if last.exists():
                atomic_copy(last, ddir / 'last.pt')
            rc = Path(trainer.save_dir) / 'results.csv'
            if rc.exists():
                atomic_copy(rc, ddir / 'results.csv')
            t = dict(timing)
            t['train_wall_s'] = round(timing['train_wall_s'] + time.time() - seg_start, 1)
            write_json(ddir / 'timing.json', t)

        if (ddir / 'last.pt').exists():
            log(run_id, 'resuming from Drive last.pt')
            llast.parent.mkdir(parents=True, exist_ok=True)
            if not llast.exists():
                shutil.copy2(ddir / 'last.pt', llast)
            timing['resumed'] = True
            model = YOLO(str(llast))
            model.add_callback('on_model_save', sync)
            try:
                model.train(resume=True)
            except AssertionError as e:
                if 'nothing to resume' not in str(e).lower() and 'finished' not in str(e).lower():
                    raise
                log(run_id, 'checkpoint already finished; going to evaluation')
        else:
            model = YOLO(str(LOC / 'pretrained' / job['base']))
            model.add_callback('on_model_save', sync)
            args = dict(RECIPE)
            args.update(device=0, workers=cfg['workers'], data=str(data_yaml), seed=int(job['seed']),
                        project=str(LOC / 'runs'), name=run_id, exist_ok=True,
                        plots=False, verbose=False, save=True)
            for k in ('imgsz', 'batch', 'epochs', 'patience'):
                if k in job:
                    args[k] = job[k]
            if job.get('kd'):
                args.update(distill_model=str(LOC / 'pretrained' / 'teacher.pt'), dis=float(job.get('dis', KD_DIS)))
            model.train(**args)
        if not lbest.exists():
            raise RuntimeError('best.pt missing after training')
        atomic_copy(lbest, ddir / 'best.pt')
        if llast.exists():
            atomic_copy(llast, ddir / 'last.pt')
        for f in ('results.csv', 'args.yaml'):
            if (lrun / f).exists():
                atomic_copy(lrun / f, ddir / f)
        timing['train_wall_s'] = round(timing['train_wall_s'] + time.time() - seg_start, 1)
        timing['segments'] = timing.get('segments', 0) + 1
        write_json(ddir / 'timing.json', timing)
        write_json(ddir / 'TRAINED.json', {'at': now_iso()})

    best = lbest if lbest.exists() else ddir / 'best.pt'
    hfp = ensure_home_fire()
    suites = ensure_suites()
    fresh = ensure_fresh()
    dfire = ensure_dfire_pos() if cfg.get('eval_dfire', True) else None
    eval_s = evaluate_model(best, int(job.get('imgsz', 640)), ddir / 'eval', run_id, hfp, suites, fresh, dfire)
    try:
        import pandas as pd
        rc = pd.read_csv(ddir / 'results.csv')
        rc.columns = [c.strip() for c in rc.columns]
        col = next((c for c in rc.columns if 'mAP50-95' in c), None)
        best_epoch = int(rc.loc[rc[col].idxmax(), 'epoch']) if col else None
        epochs_run = int(rc['epoch'].max())
    except Exception:
        best_epoch, epochs_run = None, None
    write_json(ddir / 'DONE.json', {'run_id': run_id, 'at': now_iso(), 'eval_s': eval_s,
                                    'best_epoch': best_epoch, 'epochs_run': epochs_run,
                                    'train_wall_s': timing['train_wall_s'], 'hardware': hardware(),
                                    'fresh_scored': sorted(fresh)})
    log(run_id, 'DONE')
    return 0


# ------------------------------------------------------------------ video
# Every video is decoded strictly in order and outside the notebook kernel. Random seeking in
# some old AVI files is where FFmpeg inside OpenCV can corrupt memory ("free(): invalid next
# size"), which kills the whole Colab session; in a separate process it costs one video only.
def _write_jpg(path, img, quality=88):
    import cv2
    ok, buf = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if ok:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(buf.tobytes())


def probe_video(path, role, thumb=None, frames_dir=None, n_keep=8):
    """Decode a whole video once, in order: frame count, fps, preview tiles and (optionally)
    n_keep evenly spaced frames saved as JPG. Reading every frame also proves the video decodes."""
    import cv2
    import numpy as np
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        return {'ok': False, 'note': 'cannot open'}
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    n_meta = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    cap.release()

    def targets(n):
        if role == 'positive':           # ignition-time tiles at 0, 1, 2, 4 and 8 s
            tile_at = {int(t * fps) for t in (0, 1, 2, 4, 8)}
        else:
            tile_at = {int(n * f) for f in (0.1, 0.5, 0.9)} if n > 0 else set()
        keep_at = {int(x) for x in np.linspace(0, n - 1, n_keep)} if (frames_dir and n > 0) else set()
        return tile_at, keep_at

    def scan(tile_at, keep_at):
        if frames_dir:
            shutil.rmtree(frames_dir, ignore_errors=True)
        cap = cv2.VideoCapture(str(path))
        tiles, kept, idx = {}, 0, 0
        while cap.grab():
            if idx in tile_at or idx in keep_at:
                ok, fr = cap.retrieve()
                if ok:
                    if idx in tile_at:
                        tiles[idx] = cv2.resize(fr, (240, max(1, int(240 * fr.shape[0] / fr.shape[1]))))
                    if idx in keep_at:
                        _write_jpg(Path(frames_dir) / ('%d.jpg' % idx), fr)
                        kept += 1
            idx += 1
        cap.release()
        return idx, tiles, kept

    n, tiles, kept = scan(*targets(n_meta))
    if n_meta <= 0 < n:                  # no frame count in the container: second pass with the real one
        n, tiles, kept = scan(*targets(n))
    if n == 0:
        return {'ok': False, 'note': 'no decodable frame', 'fps': round(fps, 3), 'frames_meta': n_meta}
    if thumb and tiles:
        ims = [tiles[k] for k in sorted(tiles)]
        h = min(t.shape[0] for t in ims)
        _write_jpg(thumb, cv2.hconcat([t[:h] for t in ims]))
    return {'ok': True, 'note': '', 'frames': n, 'frames_meta': n_meta, 'fps': round(fps, 3),
            'seconds': round(n / fps, 1), 'tiles': len(tiles), 'kept_frames': kept}


def probe_videos(videos, thumbs_dir, frames_dir, parallel=8, timeout_s=3600):
    """probe_video for every video, each in its own process, several at a time.

    Returns the video dicts with ok/note/frames/fps/seconds filled in. A crash or a hang marks
    only that video (ok=False, with the reason). Good results are cached in OUT/video/probe.
    """
    import subprocess
    from concurrent.futures import ThreadPoolExecutor
    lib = str(Path(__file__).resolve())
    env = dict(os.environ, SFS_SRC=str(SRC), SFS_OUT=str(OUT), SFS_LOCAL=str(LOC), OMP_NUM_THREADS='2',
               PYTHONIOENCODING='utf-8')
    cache_dir = OUT / 'video' / 'probe'

    def one(v):
        p = Path(v['path'])
        size = p.stat().st_size if p.exists() else -1
        fdir = Path(frames_dir) / v['key'] if v['role'] == 'indoor_small' else None
        cache = read_json(cache_dir / (v['key'] + '.json'))
        if cache and cache.get('size') == size and (fdir is None or imgs_in(fdir)):
            return dict(v, **{k: x for k, x in cache.items() if k != 'size'})
        cmd = [sys.executable, lib, 'probe', '--video', str(p), '--key', v['key'], '--role', v['role'],
               '--thumb', str(Path(thumbs_dir) / (v['key'] + '.jpg'))]
        if fdir is not None:
            cmd += ['--frames-dir', str(fdir)]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace',
                               timeout=timeout_s, env=env, cwd='/content' if Path('/content').exists() else None)
        except subprocess.TimeoutExpired:
            return dict(v, ok=False, note='no answer after %d s' % timeout_s)
        lines = (r.stdout or '').strip().splitlines()
        try:
            res = json.loads(lines[-1]) if lines else None
        except ValueError:
            res = None
        if r.returncode != 0 or not isinstance(res, dict):
            err = [ln for ln in (r.stderr or '').splitlines() if ln.strip()]
            return dict(v, ok=False, note='reader crashed (exit code %s)%s'
                        % (r.returncode, (': ' + err[-1].strip()[:150]) if err else ''))
        if res.get('ok'):
            write_json(cache_dir / (v['key'] + '.json'), dict(res, size=size))
        return dict(v, **res)

    with ThreadPoolExecutor(max_workers=max(1, parallel)) as ex:
        return list(ex.map(one, videos))


def run_video_specs(spec_file, nworkers, logs_dir, tag, rounds=4, poll_s=60):
    """Run the video workers (detections or max confidence) and start them again if one dies.

    Each worker leaves a marker in LOC/video_running while it reads a video. Markers still there
    after a round belong to crashed readers; a video with two crashes is skipped for every model
    and recorded as <key>.failed.json next to its missing CSV. Finished CSVs are never redone.
    """
    import subprocess
    specs = read_json(spec_file)
    need = [Path(s['out_dir']) / (v['key'] + '.csv') for s in specs for v in s['videos']]
    resolved = lambda f: f.exists() or f.with_suffix('.failed.json').exists()
    lib = str(Path(__file__).resolve())
    env = dict(os.environ, SFS_SRC=str(SRC), SFS_OUT=str(OUT), SFS_LOCAL=str(LOC), OMP_NUM_THREADS='2',
               PYTHONUNBUFFERED='1')
    logs_dir = Path(logs_dir)
    logs_dir.mkdir(parents=True, exist_ok=True)
    running_dir = LOC / 'video_running'
    running_dir.mkdir(parents=True, exist_ok=True)
    crashes = read_json(LOC / 'video_crashes.json', {})
    t0 = time.time()
    for rnd in range(rounds):
        procs = []
        for i in range(nworkers):
            fh = open(logs_dir / ('%s_%d.log' % (tag, i)), 'a')
            procs.append((subprocess.Popen([sys.executable, lib, 'video', '--specs', str(spec_file), '--worker', str(i),
                                            '--nworkers', str(nworkers)], stdout=fh, stderr=subprocess.STDOUT, env=env,
                                           cwd='/content' if Path('/content').exists() else None), fh))
        while any(p.poll() is None for p, _ in procs):
            time.sleep(poll_s)
            log('%5.1f min  %d / %d video files' % ((time.time() - t0) / 60, sum(f.exists() for f in need), len(need)))
        for _, fh in procs:
            fh.close()
        for m in running_dir.glob('*.json'):
            k = (read_json(m) or {}).get('video')
            if k:
                crashes[k] = crashes.get(k, 0) + 1
            m.unlink()
        write_json(LOC / 'video_crashes.json', crashes)
        dead = [(i, p.returncode) for i, (p, _) in enumerate(procs) if p.returncode != 0]
        left = [f for f in need if not resolved(f)]
        if not left or not dead:
            break
        log('round %d: worker(s) stopped abnormally %s; starting again for %d missing files' % (rnd + 1, dead, len(left)))
    failed = [read_json(f.with_suffix('.failed.json')) for f in need if f.with_suffix('.failed.json').exists()]
    missing = [str(f) for f in need if not resolved(f)]
    log('video files: %d done, %d skipped (unreadable), %d missing'
        % (sum(f.exists() for f in need), len(failed), len(missing)))
    for k in sorted({x['video'] for x in failed}):
        log('  UNREADABLE for the detector:', k)
    return {'failed': failed, 'missing': missing}


def detect_video_csv(model, video, out_csv, imgsz=640, conf=0.10, stride=1):
    """Per-frame detections, exactly the format of detect_video.py (empty row = frame without boxes)."""
    import cv2
    out_csv = Path(out_csv)
    if out_csv.exists():
        return 'exists'
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        log('cannot open', video)
        return 'cannot open'
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    rows, idx = [], 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if stride > 1 and idx % stride:
            idx += 1
            continue
        r = model.predict(frame, imgsz=imgsz, conf=conf, verbose=False)[0]
        t = idx / fps
        if len(r.boxes):
            for b, c, k in zip(r.boxes.xyxy.cpu().numpy(), r.boxes.conf.cpu().numpy(), r.boxes.cls.cpu().numpy()):
                rows.append([idx, round(t, 4), round(float(b[0]), 1), round(float(b[1]), 1),
                             round(float(b[2]), 1), round(float(b[3]), 1), round(float(c), 4), int(k)])
        else:
            rows.append([idx, round(t, 4), '', '', '', '', '', ''])
        idx += 1
    cap.release()
    write_csv(out_csv, ['frame', 'time_s', 'x1', 'y1', 'x2', 'y2', 'conf', 'cls'], rows)
    return 'done'


def video_maxconf_csv(model, video, out_csv, imgsz=640, conf=0.001):
    """Per-frame max confidence per class (for the indoor small-flame clips)."""
    import cv2
    out_csv = Path(out_csv)
    if out_csv.exists():
        return 'exists'
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        log('cannot open', video)
        return 'cannot open'
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    rows, idx = [], 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        r = model.predict(frame, imgsz=imgsz, conf=conf, verbose=False)[0]
        fm = sm = 0.0
        if len(r.boxes):
            for c, k in zip(r.boxes.conf.cpu().numpy(), r.boxes.cls.cpu().numpy()):
                if int(k) == 0:
                    fm = max(fm, float(c))
                else:
                    sm = max(sm, float(c))
        rows.append([idx, round(idx / fps, 4), round(fm, 5), round(sm, 5)])
        idx += 1
    cap.release()
    write_csv(out_csv, ['frame', 'time_s', 'flame_max', 'smoke_max'], rows)
    return 'done'


# ------------------------------------------------------------------ experiment grid
SEEDS = (42, 123, 2024)
BASE_OF = {'yolo26n': 'yolo26n.pt', 'yolo11n': 'yolo11n.pt', 'yolov8n': 'yolov8n.pt'}


# Typical length of one run (early stopping at best epoch + 50), from runs_master_v2.csv:
# negative-set runs stopped at about 190-240 epochs, the distilled students at about 270-335.
EXPECTED_EPOCHS = {False: 220, True: 290}


def job_grid(priority=1, kd=None):
    """All revision runs. Priority 1 = the core conditions; 2 and 3 = extras.

    kd=False -> only runs without distillation (notebook SFS_03)
    kd=True  -> only distillation runs (notebook SFS_04)
    kd=None  -> everything
    Order: every priority-1 condition at seed 42 first, then 123, then 2024, so that
    a partial run of the queue still leaves complete single-seed rows.
    """
    jobs = _job_grid(priority)
    return jobs if kd is None else [j for j in jobs if bool(j['kd']) == bool(kd)]


def _job_grid(priority=1):
    p1 = [('N0', False), ('M', False), ('L', False), ('U1638', False),
          ('N0', True), ('M', True), ('L', True), ('U1638', True),
          ('R', False), ('C', False), ('BG10', False), ('P', False),
          ('U3276', False), ('U3276', True), ('R3276', True),
          ('PA', False), ('PA', True)]
    jobs = []

    def add(neg, kd, arch, seed, pr, why):
        jobs.append({'run_id': '%s__%s__%s__s%d' % (neg, 'KD' if kd else 'noKD', arch, seed),
                     'neg_set': neg, 'kd': kd, 'arch': arch, 'base': BASE_OF[arch], 'seed': seed,
                     'imgsz': 640, 'batch': 32, 'priority': pr, 'why': why})
    for seed in SEEDS:
        for neg, kd in p1:
            add(neg, kd, 'yolo26n', seed, 1, 'factorial / controls')
    if priority >= 2:
        for arch in ('yolo11n', 'yolov8n'):
            for seed in (123, 2024):
                add('M', False, arch, seed, 2, 'M-top transfer, three seeds')
    if priority >= 3:
        for seed in SEEDS:
            add('R', True, 'yolo26n', seed, 3, 'random + KD')
        for arch in ('yolo11n', 'yolov8n'):
            for seed in SEEDS:
                add('N0', False, arch, seed, 3, 'transfer baseline on the same GPU')
            add('M', False, arch, 42, 3, 'transfer on the same GPU')
    return jobs


def run_queue(jobs, max_parallel, stagger_s=150, poll_s=60, max_attempts=2, status_every_s=600):
    """Run training jobs as separate processes, several at a time on the one GPU.

    Each job is deterministic on its own, so running them side by side changes the
    wall time and nothing else. Stopping the cell stops every job it started; running
    it again resumes them from their last Drive checkpoint.
    """
    import subprocess
    lib = str(Path(__file__).resolve())
    logs = OUT / 'logs' / 'train'
    logs.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(['pkill', '-f', 'sfs_lib.py train'], check=False)
    except Exception:
        pass
    done = lambda j: (OUT / 'runs' / j['run_id'] / 'DONE.json').exists()
    pending = [j for j in jobs if not done(j)]
    attempts = {j['run_id']: 0 for j in pending}
    running, failed = {}, []
    last_start, last_status = 0.0, 0.0
    env = dict(os.environ, SFS_SRC=str(SRC), SFS_OUT=str(OUT), SFS_LOCAL=str(LOC),
               OMP_NUM_THREADS='4', PYTHONUNBUFFERED='1')
    log('queue: %d to run (%d already done), up to %d at a time'
        % (len(pending), len(jobs) - len(pending), max_parallel))
    try:
        while pending or running:
            for rid, (p, j, t0, fh) in list(running.items()):
                rc = p.poll()
                if rc is None:
                    continue
                fh.close()
                del running[rid]
                if done(j):
                    log('finished %-32s %.0f min' % (rid, (time.time() - t0) / 60))
                else:
                    attempts[rid] += 1
                    tail = (logs / (rid + '.log')).read_text(errors='ignore').splitlines()[-15:]
                    log('FAILED %s (attempt %d, exit %s)\n    %s' % (rid, attempts[rid], rc, '\n    '.join(tail)))
                    if attempts[rid] < max_attempts:
                        pending.append(j)
                    else:
                        failed.append(rid)
            while pending and len(running) < max_parallel and time.time() - last_start >= stagger_s:
                j = pending.pop(0)
                jf = LOC / 'jobs' / (j['run_id'] + '.json')
                write_json(jf, j)
                fh = open(logs / (j['run_id'] + '.log'), 'a')
                fh.write('\n===== %s start =====\n' % now_iso())
                fh.flush()
                p = subprocess.Popen([sys.executable, lib, 'train', '--job', str(jf)], stdout=fh,
                                     stderr=subprocess.STDOUT, cwd='/content' if Path('/content').exists() else None,
                                     env=env)
                running[j['run_id']] = (p, j, time.time(), fh)
                last_start = time.time()
                log('started  %s' % j['run_id'])
            if time.time() - last_status >= status_every_s:
                last_status = time.time()
                n_done = sum(done(j) for j in jobs)
                lines, rates = [], []
                for rid, (p, j, t0, fh) in running.items():
                    rc = LOC / 'runs' / rid / 'results.csv'
                    ep = max(0, len(rc.read_text().splitlines()) - 1) if rc.exists() else 0
                    lines.append('%s ep %d' % (rid, ep))
                    if ep >= 2:
                        rates.append((time.time() - t0) / ep)
                log('status: %d/%d done | running: %s' % (n_done, len(jobs), '; '.join(lines) or '-'))
                if rates:
                    spe = sorted(rates)[len(rates) // 2]
                    left = [j for j in jobs if not done(j)]
                    h = sum(EXPECTED_EPOCHS[bool(j['kd'])] for j in left) * spe / 3600 / max(1, max_parallel)
                    log('        about %.0f s per epoch per run at %d in parallel -> roughly %.1f h for the %d runs left'
                        % (spe, len(running), h, len(left)))
            time.sleep(poll_s)
    except KeyboardInterrupt:
        log('stopping: terminating running jobs (they resume next time from Drive)')
        for p, j, t0, fh in running.values():
            p.terminate()
        for p, j, t0, fh in running.values():
            try:
                p.wait(60)
            except Exception:
                p.kill()
            fh.close()
        raise
    log('queue finished. failed: %s' % (failed or 'none'))
    return failed


# ------------------------------------------------------------------ manifests
def _manifest_dir():
    return SRC / 'safemine_v2' / 'manifests'


def hits_table():
    """{name: max_conf} for the 9,854 round-0 hits."""
    with open(SRC / 'safemine_v2' / 'mining' / 'round0_hits.csv', encoding='utf-8-sig') as f:
        return {r['name']: float(r['max_conf']) for r in csv.DictReader(f)}


def build_neg_sets(randbg_names, coco_extra_names):
    """Manifests of every negative set used by the revision runs (OUT/manifests/neg_sets.json).

    Original sets are taken from the frozen SAFE_FIRE manifests unchanged.
    New sets are built with fixed seeds and described in the file itself.
    """
    md = _manifest_dir()
    L = read_json(md / 'ratio_hn30.json')
    M = read_json(md / 'round0_top.json')
    C = read_json(md / 'round0_cov.json')
    R = read_json(md / 'ratio_hn30rand.json')
    dev = set(read_json(md / 'dev_neg.json'))
    fb = set(read_json(md / 'fire_block.json'))
    sets = {
        'L': {'items': [['hn_pool', n] for n in L],
              'description': 'L-ratio: 1,638 Open Images v7 train images labelled Lamp/Light bulb/Candle (ratio_hn30.json)'},
        'M': {'items': [['hits', n] for n in M],
              'description': 'M-top: 1,638 highest-scoring eligible round-0 hits (round0_top.json)'},
        'C': {'items': [['hits', n] for n in C],
              'description': 'Cluster coverage: 1,638 hits sampled by cluster quota (round0_cov.json)'},
        'R': {'items': [['randbg', n] for n in R],
              'description': 'Random control: 1,638 random COCO-2017 validation images (ratio_hn30rand.json)'},
        'BG10': {'items': [['randbg', n] for n in R[:433]],
                 'description': '433 random COCO-2017 val backgrounds = 10.0% of the training set (433/4,333), '
                                'the first 433 of the random-control order'},
    }
    rng = random.Random(2026)
    half = min(819, len(L), len(M))            # 819 + 819 = 1,638 on the real manifests
    Ls, Ms = rng.sample(L, half), rng.sample(M, half)
    sets['U1638'] = {'items': [['hn_pool', n] for n in Ls] + [['hits', n] for n in Ms],
                     'description': 'Union subsampled to 1,638: 819 from L-ratio + 819 from M-top, random.Random(2026)'}
    seen, U = set(), []
    for k, n in [('hn_pool', n) for n in L] + [('hits', n) for n in M]:
        if n not in seen:
            seen.add(n)
            U.append([k, n])
    sets['U3276'] = {'items': U, 'description': 'Union L-ratio + M-top as in the deployed model (dedup by file name)'}
    order = sorted(randbg_names)
    random.Random(42).shuffle(order)
    if order[:len(R)] != R:
        rest = sorted(set(randbg_names) - set(R))
        random.Random(2026).shuffle(rest)
        order = list(R) + rest
        how = 'R, then the other pool images shuffled with Random(2026)'
    else:
        how = 'the original Random(42) order of the 2,000-image pool'
    need = 3276 - len(order)
    sets['R3276'] = {'items': [['randbg', n] for n in order] + [['coco_extra', n] for n in coco_extra_names[:need]],
                     'description': 'Random control at the deployed volume: %d COCO val images in %s, plus %d '
                                    'further random COCO-2017 val images (coco_extra.zip)' % (len(order), how, need)}
    conf = hits_table()
    places = [n for n in conf if n.startswith('Places365') and n not in dev and n not in fb]
    P = sorted(places, key=lambda n: (-conf[n], n))[:1638]
    sets['P'] = {'items': [['hits', n] for n in P],
                 'description': 'Label-free mining: top-confidence %d of the %d eligible Places365 hits '
                                '(scene labels only, no object labels)' % (len(P), len(places))}
    for k, v in sets.items():
        v['n'] = len(v['items'])
    write_json(OUT / 'manifests' / 'neg_sets.json', sets)
    return {k: v['n'] for k, v in sets.items()}


def _clip(device):
    from transformers import CLIPModel, CLIPProcessor
    cm = CLIPModel.from_pretrained('openai/clip-vit-base-patch32').to(device).eval()
    cp = CLIPProcessor.from_pretrained('openai/clip-vit-base-patch32')
    return cm, cp


def clip_image_features(cm, cp, pil_list, device):
    import torch
    with torch.no_grad():
        inp = cp(images=pil_list, return_tensors='pt').to(device)
        out = cm.get_image_features(**inp)
        if not torch.is_tensor(out):
            vo = cm.vision_model(pixel_values=inp['pixel_values'])
            pooled = getattr(vo, 'pooler_output', None)
            if pooled is None:
                pooled = vo.last_hidden_state[:, 0]
            out = cm.visual_projection(pooled)
        out = out / out.norm(dim=-1, keepdim=True)
    return out.float().cpu().numpy()


def clip_text_features(cm, cp, prompts, device):
    import torch
    with torch.no_grad():
        ti = cp(text=prompts, return_tensors='pt', padding=True).to(device)
        out = cm.get_text_features(**ti)
        if not torch.is_tensor(out):
            to = cm.text_model(input_ids=ti['input_ids'], attention_mask=ti.get('attention_mask'))
            pooled = getattr(to, 'pooler_output', None)
            if pooled is None:
                pooled = to.last_hidden_state[:, 0]
            out = cm.text_projection(pooled)
        out = out / out.norm(dim=-1, keepdim=True)
    return out.float().cpu().numpy()


def _ctx_crop(im, box_xywhn, ctx=2.0, min_side=32):
    W, H = im.size
    if box_xywhn is None:
        return im
    xc, yc, w, h = [float(v) for v in box_xywhn]
    s = max(max(w * W, h * H) * ctx, min_side)
    x1, y1 = max(0, xc * W - s / 2), max(0, yc * H - s / 2)
    x2, y2 = min(W, xc * W + s / 2), min(H, yc * H + s / 2)
    if x2 - x1 < 2 or y2 - y1 < 2:
        return im
    return im.crop((int(x1), int(y1), int(x2), int(y2)))


def build_pa_manifest(budget=1638, k=5, ctx=2.0, max_area=0.05):
    """Positive-aware SAFE-Mine. The rule is fixed here, before any PA model is trained.

    1. Fire bank: every flame box of the home_fire TRAIN split covering <= 5% of the image
       (small and medium fires), cropped with 2x context and embedded by CLIP ViT-B/32.
    2. Confuser bank: the 1,638 L-ratio images (lamp, light bulb, candle), cropped around the
       top box of the negative-free baseline detector, same context, same encoder.
    3. Candidates: the eligible round-0 hits (not mining_dev, not fire-like), cropped the same way.
    4. A candidate is EXCLUDED when the mean similarity of its k=5 nearest fire crops is at least
       the mean similarity of its 5 nearest confuser crops: its detected region looks more like a
       real small fire than like the known confusers, so learning it as background would teach the
       detector to suppress small fires.
    5. The remaining candidates are ranked by detector confidence exactly like M-top; top 1,638.
    No test image, test video or evaluation subset is consulted.
    """
    import numpy as np
    import torch
    from PIL import Image
    from ultralytics import YOLO
    out = OUT / 'manifests' / 'neg_PA.json'
    if out.exists():
        return read_json(out)
    hf = ensure_home_fire()
    ensure_sources(('hits', 'hn_pool'))
    hit_dir = LOC / 'pools' / 'src' / 'hits'
    pool_dir = LOC / 'pools' / 'src' / 'hn_pool'
    md = _manifest_dir()
    dev, fb = set(read_json(md / 'dev_neg.json')), set(read_json(md / 'fire_block.json'))
    L = read_json(md / 'ratio_hn30.json')
    conf = hits_table()
    elig = [n for n in sorted(conf) if n not in dev and n not in fb and (hit_dir / n).exists()]
    fire = []
    for img in imgs_in(hf / 'train' / 'images'):
        for row in _gt(hf / 'train' / 'labels' / (img.stem + '.txt')):
            if int(row[0]) == 0 and row[3] * row[4] <= max_area:
                fire.append((img, row[1:5]))
    log('PA: %d candidates, %d small/medium flame boxes (train split), %d confuser images'
        % (len(elig), len(fire), len(L)))
    det = YOLO(str(SRC / 'weights' / 'tournament__yolo26n__s42__best.pt'))

    def top_boxes(paths):
        boxes = {}
        for i in range(0, len(paths), 64):
            for p, r in _predict_safe(det, paths[i:i + 64], 640, 0.01):
                boxes[str(p)] = (r.boxes.xywhn[int(r.boxes.conf.argmax())].cpu().numpy()
                                 if len(r.boxes) else None)
        return boxes
    cand_paths = [hit_dir / n for n in elig]
    conf_paths = [pool_dir / n for n in L if (pool_dir / n).exists()]
    cbox = top_boxes(cand_paths)
    lbox = top_boxes(conf_paths)
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    cm, cp = _clip(device)

    def emb(pairs):
        feats = []
        for j in range(0, len(pairs), 128):
            ims = [_ctx_crop(Image.open(p).convert('RGB'), b, ctx) for p, b in pairs[j:j + 128]]
            feats.append(clip_image_features(cm, cp, ims, device))
        return np.concatenate(feats)
    F = emb(fire)
    Lf = emb([(p, lbox.get(str(p))) for p in conf_paths])
    Cf = emb([(p, cbox.get(str(p))) for p in cand_paths])

    def topk_mean(A, B):
        out_ = []
        for j in range(0, len(A), 2048):
            s = A[j:j + 2048] @ B.T
            s.sort(axis=1)
            out_.append(s[:, -k:].mean(1))
        return np.concatenate(out_)
    s_fire = topk_mean(Cf, F)
    s_conf = topk_mean(Cf, Lf)
    excl = s_fire >= s_conf
    remain = [n for n, e in zip(elig, excl) if not e]
    top = sorted(remain, key=lambda n: (-conf[n], n))[:budget]
    M = set(read_json(md / 'round0_top.json'))
    top_set = set(top)
    write_csv(OUT / 'audit' / 'pa_similarity.csv',
              ['name', 'max_conf', 'sim_fire_top5', 'sim_confuser_top5', 'excluded', 'in_M_top', 'in_PA'],
              [(n, conf[n], round(float(a), 4), round(float(b), 4), int(e), int(n in M), int(n in top_set))
               for n, a, b, e in zip(elig, s_fire, s_conf, excl)])
    res = {'items': [['hits', n] for n in top], 'n': len(top), 'rule': 'exclude if mean top-%d CLIP similarity to '
           'small/medium fire crops >= mean top-%d similarity to L-ratio confuser crops' % (k, k),
           'k': k, 'context': ctx, 'max_area': max_area, 'n_fire_crops': len(fire), 'n_confuser_crops': len(Lf),
           'n_candidates': len(elig), 'n_excluded': int(excl.sum()),
           'n_excluded_from_M_top': int(sum(1 for n, e in zip(elig, excl) if e and n in M)),
           'overlap_with_M_top': len(M & top_set),
           'description': 'Positive-aware SAFE-Mine: the M-top rule applied after removing candidates whose '
                          'detected region is closer to real small fires than to known confusers'}
    write_json(out, res)
    log('PA: excluded %d of %d candidates (%d of them were in M-top); PA overlaps M-top on %d of %d'
        % (res['n_excluded'], len(elig), res['n_excluded_from_M_top'], res['overlap_with_M_top'], len(top)))
    return res


# ------------------------------------------------------------------ VLM verifier baseline
VERIFY_POS = ['a photo of fire', 'a photo of flames', 'a photo of smoke']
VERIFY_NEG = ['a photo of a lamp', 'a photo of a light bulb', 'a photo of a candle', 'a photo of a sunset',
              'a photo of a glowing screen', 'a photo of a street light', 'a photo of a light reflection',
              'a photo of an orange object', 'a photo of a person', 'a photo of a room']


def clip_verify_eval(weights, imgsz, out_dir, hf, neg_sets, topk=10, ctx=2.0, conf=0.01, chunk=32):
    """A contemporary false-alarm baseline: detector + zero-shot vision-language verification.

    Every box (the 10 most confident per image) is cropped with 2x context and scored by CLIP ViT-B/32 against fire
    prompts and common confuser prompts; the box score becomes conf x P(fire | crop). The same
    per-image (negatives) and per-instance (positives) protocol as the paper is then applied, so
    the verifier is compared with trained negatives at a matched false-alarm budget.
    """
    import numpy as np
    import torch
    from PIL import Image
    from ultralytics import YOLO
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    cm, cp = _clip(device)
    T = clip_text_features(cm, cp, VERIFY_POS + VERIFY_NEG, device)
    model = YOLO(str(weights))

    def rescore(paths):
        res = _predict_safe(model, paths, imgsz, conf)
        crops, owner = [], []
        boxes = []
        for i, (p, r) in enumerate(res):
            if r.boxes is not None and len(r.boxes):
                o = r.boxes.conf.cpu().numpy().argsort()[::-1][:topk]
                xyxy = r.boxes.xyxy.cpu().numpy()[o]
                cs = r.boxes.conf.cpu().numpy()[o]
                xywhn = r.boxes.xywhn.cpu().numpy()[o]
                im = Image.open(p).convert('RGB')
                for b in xywhn:
                    crops.append(_ctx_crop(im, b, ctx))
                    owner.append(i)
                boxes.append((xyxy, cs))
            else:
                boxes.append((np.zeros((0, 4)), np.zeros(0)))
        pf = np.zeros(len(crops))
        for j in range(0, len(crops), 128):
            f = clip_image_features(cm, cp, crops[j:j + 128], device)
            lg = 100.0 * f @ T.T
            lg = lg - lg.max(1, keepdims=True)
            pr = np.exp(lg) / np.exp(lg).sum(1, keepdims=True)
            pf[j:j + 128] = pr[:, :len(VERIFY_POS)].sum(1)
        out, k = [], 0
        for i, (p, r) in enumerate(res):
            xyxy, cs = boxes[i]
            n = len(cs)
            out.append((p, r, xyxy, cs * pf[k:k + n], cs))
            k += n
        return out

    for name, d in neg_sets.items():
        f = out_dir / ('neg_%s.csv' % name)
        if f.exists():
            continue
        rows = []
        fs = imgs_in(d)
        for i in range(0, len(fs), chunk):
            for p, r, xyxy, vs, cs in rescore(fs[i:i + chunk]):
                rows.append((Path(p).name, float(vs.max()) if len(vs) else 0.0, float(cs.max()) if len(cs) else 0.0))
        write_csv(f, ['image', 'max_conf', 'max_conf_detector_only'], rows)
    f = out_dir / 'test_pos.csv'
    if not f.exists():
        rows = []
        fs = imgs_in(hf / 'test' / 'images')
        for i in range(0, len(fs), chunk):
            for p, r, xyxy, vs, cs in rescore(fs[i:i + chunk]):
                g = _gt(hf / 'test' / 'labels' / (Path(p).stem + '.txt'))
                if len(g) == 0:
                    continue
                h, w = r.orig_shape
                gx = np.stack([(g[:, 1] - g[:, 3] / 2) * w, (g[:, 2] - g[:, 4] / 2) * h,
                               (g[:, 1] + g[:, 3] / 2) * w, (g[:, 2] + g[:, 4] / 2) * h], 1)
                M = _iou_mat(gx, xyxy)
                for j in range(len(gx)):
                    hit = M[j] >= 0.5 if len(xyxy) else np.zeros(0, bool)
                    rows.append((Path(p).name, j, int(g[j, 0]), round(float(g[j, 3] * g[j, 4]), 8),
                                 round(float(vs[hit].max()), 6) if hit.any() else 0.0,
                                 round(float(cs[hit].max()), 6) if hit.any() else 0.0))
        write_csv(f, ['img', 'gt', 'cls', 'area', 'conf_any', 'conf_any_detector_only'], rows)
    write_json(out_dir / 'SCORED.json', {'at': now_iso(), 'weights': str(weights), 'topk': topk, 'context': ctx,
                                         'prompts_fire': VERIFY_POS, 'prompts_other': VERIFY_NEG,
                                         'fresh_scored': sorted(k for k in neg_sets if k.startswith('F_'))})


# ------------------------------------------------------------------ bundles
def make_bundle(tag, roots=None, exclude_ext=('.pt', '.zip', '.npz', '.onnx', '.engine', '.tmp'),
                max_file_mb=25):
    """Small zip of results (CSV/JSON/MD/logs/sheets) to download to the PC."""
    roots = roots or [OUT]
    ts = time.strftime('%Y%m%d_%H%M')
    z = OUT / 'bundles' / ('bundle_%s_%s.zip' % (tag, ts))
    z.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with zipfile.ZipFile(z, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root in roots:
            for p in Path(root).rglob('*'):
                if not p.is_file() or 'bundles' in p.parts or p.suffix.lower() in exclude_ext:
                    continue
                if p.suffix.lower() in IMG_EXT and 'audit' not in p.parts and 'thumbs' not in p.parts \
                        and 'figures' not in p.parts:
                    continue
                if p.stat().st_size > max_file_mb * 1e6:
                    continue
                zf.write(p, p.relative_to(OUT).as_posix())
                n += 1
    log('bundle: %s (%d files, %.1f MB)' % (z, n, z.stat().st_size / 1e6))
    return z


# ------------------------------------------------------------------ workers
def hash_one(p):
    """(path, sha256, dhash-hex) for the audit; never raises."""
    try:
        return str(p), sha256_file(p), '%016x' % dhash(p)
    except Exception:
        return str(p), 'ERR', ''


def warm_val_cache(hf, weights):
    """Create the label cache of the shared test split once, before parallel workers read it."""
    from ultralytics import YOLO
    YOLO(str(weights)).val(data=str(hf / 'data.yaml'), split='test', imgsz=640, verbose=False, plots=False,
                           project=str(LOC / 'tmp' / 'val'), name='warm', exist_ok=True)


def score_specs_complete(s, fresh_names):
    m = read_json(Path(s['out_dir']) / 'SCORED.json')
    return m is not None and set(fresh_names) <= set(m.get('fresh_scored', []))


def _score_worker(spec_file, worker, nworkers):
    """Score models (old or new) on everything; idempotent, fills only what is missing."""
    specs = read_json(spec_file)
    hf = ensure_home_fire()
    suites = ensure_suites()
    fresh = ensure_fresh()
    dfire = ensure_dfire_pos()
    for i, s in enumerate(specs):
        if i % nworkers != worker:
            continue
        od = Path(s['out_dir'])
        if score_specs_complete(s, fresh):
            continue
        lw = LOC / 'weights' / (s['run_id'] + '.pt')
        if not lw.exists():
            atomic_copy(s['weights'], lw)
        log('scoring', s['run_id'])
        try:
            sec = evaluate_model(lw, int(s['imgsz']), od, s['run_id'], hf, suites, fresh, dfire)
            write_json(od / 'SCORED.json', {'at': now_iso(), 'seconds': sec, 'imgsz': s['imgsz'],
                                            'weights': str(s['weights']), 'fresh_scored': sorted(fresh)})
        except Exception:
            traceback.print_exc()


def _video_worker(spec_file, worker, nworkers):
    """Videos of the models assigned to this worker; started by run_video_specs."""
    from ultralytics import YOLO
    specs = read_json(spec_file)
    crashes = read_json(LOC / 'video_crashes.json', {})
    running_dir = LOC / 'video_running'
    test_crash = os.environ.get('SFS_TEST_CRASH_WORKER')     # local tests only: simulate a decoder crash
    for i, s in enumerate(specs):
        if i % nworkers != worker:
            continue
        model = None
        for v in s['videos']:
            out = Path(s['out_dir']) / (v['key'] + '.csv')
            failed = out.with_suffix('.failed.json')
            if out.exists() or failed.exists():
                continue
            if crashes.get(v['key'], 0) >= 2:
                write_json(failed, {'model': s['tag'], 'video': v['key'], 'reason': 'the video reader crashed on it twice'})
                log('skipping', v['key'], 'for', s['tag'], '(the video reader crashed on it twice)')
                continue
            mark = running_dir / ('%s__%s.json' % (s['tag'], v['key']))
            write_json(mark, {'model': s['tag'], 'video': v['key'], 'pid': os.getpid()})
            if test_crash and test_crash == v['key']:
                os.abort()
            if model is None:
                model = YOLO(s['weights'])
            if s['mode'] == 'dets':
                st = detect_video_csv(model, v['path'], out, imgsz=int(s['imgsz']), conf=0.10)
            else:
                st = video_maxconf_csv(model, v['path'], out, imgsz=int(s['imgsz']), conf=0.001)
            if st == 'cannot open':
                write_json(failed, {'model': s['tag'], 'video': v['key'], 'reason': 'cannot open'})
            mark.unlink()
        log('video done', s['tag'])


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=['train', 'score', 'video', 'probe'])
    ap.add_argument('--job')
    ap.add_argument('--specs')
    ap.add_argument('--worker', type=int, default=0)
    ap.add_argument('--nworkers', type=int, default=1)
    ap.add_argument('--video')
    ap.add_argument('--key')
    ap.add_argument('--role')
    ap.add_argument('--thumb')
    ap.add_argument('--frames-dir')
    a = ap.parse_args()
    if a.mode == 'train':
        sys.exit(train_job(read_json(a.job)))
    elif a.mode == 'score':
        _score_worker(a.specs, a.worker, a.nworkers)
    elif a.mode == 'probe':
        if a.key and a.key == os.environ.get('SFS_TEST_CRASH_PROBE'):   # local tests only
            os.abort()
        print(json.dumps(probe_video(a.video, a.role, a.thumb, a.frames_dir)), flush=True)
    else:
        _video_worker(a.specs, a.worker, a.nworkers)
