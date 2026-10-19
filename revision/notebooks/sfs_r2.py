# -*- coding: utf-8 -*-
"""Round 2 of the extended study: the steps that run on Colab. Imported by SFS_06 next to sfs_lib.

Stage 1 (CPU)  audit sheets: every M-top image + 200 reserve hits (M labels), the most fire-like
               images of the new random control (R) and of the domestic set (D); random control drawn
               from the filtered mining corpus; domestic negatives from SUN RGB-D; indoor share of the
               two D-Fire negative subsets.
Stage 2 (G4)   sets rebuilt without the images marked in the audit; RC, MC, UC and UC+KD at three seeds;
               domestic set scored by every model; test-split boxes for bootstrap intervals of mAP;
               re-encoded unreadable clips; every clip for the new runs.
Writes only under OUT (mostly OUT/round2) and LOC; SRC is read only.
"""
import csv
import gzip
import os
import random
import re
import shutil
import subprocess
import tarfile
import time
import zipfile
from pathlib import Path

import sfs_lib as L

R2 = L.OUT / 'round2'
AUDIT = R2 / 'audit'                      # the sheets the authors check by eye
SEEDS = (42, 123, 2024)
L.SOURCES['rc'] = R2 / 'rc_pool.zip'

# the fire-like rule of SAFE-Mine (same prompts and thresholds)
FIRE_P = ['a real fire with large flames', 'a house or building on fire', 'a wildfire in a forest', 'intense flames burning',
          'a car on fire']
SAFE_P = ['a lamp', 'a lit candle', 'a sunset sky', 'an orange object', 'a person', 'indoor lighting', 'a glowing screen',
          'a plate of food', 'a red flower', 'a fireplace']
INDOOR_P = ['an indoor room', 'the inside of a house', 'an indoor space', 'a room with furniture']
OUTDOOR_P = ['an outdoor scene', 'a landscape', 'a street', 'a forest', 'the sky', 'a field', 'a mountain']
DOMESTIC_SCENES = ('bedroom', 'living_room', 'kitchen', 'bathroom', 'dining_room', 'dining_area', 'home_office', 'home',
                   'playroom')
OI_URL = 'https://open-images-dataset.s3.amazonaws.com/test/%s.jpg'
PLACES_TAR = 'http://data.csail.mit.edu/places/places365/val_large.tar'
PLACES_LIST = 'http://data.csail.mit.edu/places/places365/filelist_places365-standard.tar'
SUN_ZIP = 'http://rgbd.cs.princeton.edu/data/SUNRGBD.zip'
OLD_WEIGHTS = ('tournament__yolo26n__s42', 'kd__kd6__s42')            # in SRC/weights
VIDEO_MODELS = list(OLD_WEIGHTS) + ['N0__noKD__yolo26n__s42', 'M__noKD__yolo26n__s42', 'L__noKD__yolo26n__s42',
                                    'U3276__KD__yolo26n__s42', 'U3276__KD__yolo26n__s123', 'U3276__KD__yolo26n__s2024',
                                    'PA__noKD__yolo26n__s42', 'PA__KD__yolo26n__s42']
FFMPEG = shutil.which('ffmpeg') or 'ffmpeg'
log = L.log


# ------------------------------------------------------------------ helpers
def download(url, dst, tries=4):
    import requests
    dst = Path(dst)
    if dst.exists() and dst.stat().st_size > 0:
        return dst
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.name + '.part')
    for k in range(tries):
        try:
            with requests.get(url, stream=True, timeout=120, headers={'User-Agent': 'Mozilla/5.0 (research download)'}) as r:
                r.raise_for_status()
                with open(tmp, 'wb') as f:
                    for ch in r.iter_content(1 << 20):
                        f.write(ch)
            os.replace(tmp, dst)
            return dst
        except Exception as e:
            log('download attempt %d failed for %s: %r' % (k + 1, url, e))
            time.sleep(5 * (k + 1))
    raise RuntimeError('could not download ' + url)


def image_ok(p, min_side=64):
    from PIL import Image
    try:
        with Image.open(p) as im:
            im.verify()
        with Image.open(p) as im:
            return min(im.size) >= min_side
    except Exception:
        return False


def read_rows(path):
    with open(path, encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def clip_scores(paths, pos, neg, device, batch=64):
    """Per image: max CLIP similarity to the `pos` prompts and to the `neg` prompts."""
    import numpy as np
    from PIL import Image
    cm, cp = L._clip(device)
    tp = L.clip_text_features(cm, cp, ['a photo of ' + x for x in pos], device)
    tn = L.clip_text_features(cm, cp, ['a photo of ' + x for x in neg], device)
    a, b = [np.zeros(0)], [np.zeros(0)]
    for i in range(0, len(paths), batch):
        F = L.clip_image_features(cm, cp, [Image.open(p).convert('RGB') for p in paths[i:i + batch]], device)
        a.append((F @ tp.T).max(1))
        b.append((F @ tn.T).max(1))
        if i % (batch * 20) == 0:
            log('  CLIP %d / %d' % (i, len(paths)))
    return np.concatenate(a), np.concatenate(b)


def fire_like(fire_s, safe_s):
    return ((fire_s - safe_s) > 0.05) & (fire_s > 0.25)


def sheets(items, prefix, out_dir=AUDIT, cols=8, rows=6, cell=300):
    """items = [(label, path)] -> numbered contact sheets (JPG), the label in red above each tile."""
    from PIL import Image, ImageDraw, ImageFont
    try:
        font = ImageFont.load_default(size=30)
    except Exception:
        font = ImageFont.load_default()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    per = cols * rows
    for pg, s in enumerate(range(0, len(items), per), 1):
        chunk = items[s:s + per]
        S = Image.new('RGB', (cols * cell, rows * (cell + 40)), 'white')
        d = ImageDraw.Draw(S)
        for i, (lab, p) in enumerate(chunk):
            x, y = (i % cols) * cell, (i // cols) * (cell + 40)
            try:
                im = Image.open(p).convert('RGB')
                im.thumbnail((cell - 8, cell - 8))
                S.paste(im, (x + 4, y + 38))
            except Exception:
                d.text((x + 10, y + 120), 'unreadable', fill='black', font=font)
            d.text((x + 6, y + 2), lab, fill=(220, 0, 0), font=font)
            d.rectangle([x, y, x + cell - 1, y + cell + 39], outline=(190, 190, 190))
        S.save(out_dir / ('%s_page%02d_%s-%s.jpg' % (prefix, pg, chunk[0][0], chunk[-1][0])), quality=90)
    return (len(items) + per - 1) // per


def eval_hashes():
    """sha256 and dHash of every evaluation image (frozen suite and fresh suite)."""
    import numpy as np
    sha, dh = set(), []
    for d in list(L.ensure_suites().values()) + list(L.ensure_fresh().values()):
        for p in L.imgs_in(d):
            _, s, h = L.hash_one(p)
            sha.add(s)
            if h:
                dh.append(int(h, 16))
    return sha, np.array(dh, dtype=np.uint64)


def near_eval(p, sha, dh, max_bits=4):
    import numpy as np
    _, s, h = L.hash_one(p)
    if s in sha:
        return True
    if not h or not len(dh):
        return False
    x = np.bitwise_xor(np.uint64(int(h, 16)), dh)
    return int(np.unpackbits(x.view(np.uint8)).reshape(-1, 64).sum(1).min()) <= max_bits


def _rebuild_ok(manifest, flagged, prefixes):
    """True if `manifest` must be (re)written for this audit answer; never changed under runs that use it."""
    old = L.read_json(manifest)
    if old is not None and old.get('flagged') == sorted(flagged):
        return False
    started = [d.name for d in (L.OUT / 'runs').glob('*') if d.name.startswith(prefixes)] if old is not None else []
    if started:
        raise RuntimeError('%s was built from a different FLAGGED list and runs already use it (%s). Paste the same '
                           'list as before.' % (manifest.name, ', '.join(started[:3])))
    return True


# ------------------------------------------------------------------ stage 1: M-top audit
def mtop_lists():
    """M-top (1,638) and the next 200 eligible hits in score order (they replace removed images)."""
    md = L._manifest_dir()
    conf = L.hits_table()
    excl = set(L.read_json(md / 'dev_neg.json')) | set(L.read_json(md / 'fire_block.json'))
    top = L.read_json(md / 'round0_top.json')
    elig = sorted((n for n in conf if n not in excl), key=lambda n: (-conf[n], n))
    tset = set(top)
    assert tset <= set(elig), 'M-top holds images outside the eligible hits'
    return top, [n for n in elig if n not in tset][:200], conf


def build_audit(device='cpu'):
    key = R2 / 'audit_M.csv'
    if key.exists():
        log('M sheets already built')
        return
    hits = L.ensure_sources(('hits',))['hits']
    top, reserve, conf = mtop_lists()
    names = top + reserve
    fs, ss = clip_scores([hits / n for n in names], FIRE_P, SAFE_P, device)
    order = sorted(range(len(names)), key=lambda i: -(fs[i] - ss[i]))          # the most fire-like first
    rows = [['M%d' % k, names[i], 'M-top' if i < len(top) else 'reserve', i + 1, round(conf[names[i]], 4),
             round(float(fs[i]), 4), round(float(ss[i]), 4)] for k, i in enumerate(order, 1)]
    n = sheets([(r[0], hits / r[1]) for r in rows], 'M')
    L.write_csv(key, ['label', 'image', 'set', 'conf_rank', 'max_conf', 'fire_sim', 'safe_sim'], rows)
    log('M sheets: %d images (%d M-top + %d reserve) on %d pages' % (len(rows), len(top), len(reserve), n))


# ------------------------------------------------------------------ stage 1: random control from the mining corpus
def places_filtered():
    """Places365 validation images of the mining corpus: the scene filter of SAFE_FIRE_MASTER (cell D1)."""
    d = L.LOC / 'places'
    if not (d / 'places365_val.txt').exists():
        with tarfile.open(download(PLACES_LIST, d / 'filelist.tar')) as tf:
            tf.extractall(d)
    cats = {}
    for line in (d / 'categories_places365.txt').read_text().splitlines():
        nm, idx = line.rsplit(' ', 1)
        cats[int(idx)] = nm.lower()
    block = lambda n: 'fire_escape' not in n and any(w in n for w in ('volcano', 'campsite', 'fire'))
    return [fn for fn, i in (ln.split() for ln in (d / 'places365_val.txt').read_text().splitlines())
            if not block(cats[int(i)])]


def fetch_places(names, dest):
    """Take the listed images out of val_large.tar (read as a stream; the 2.3 GB tar is deleted after)."""
    need = {n for n in names if not (Path(dest) / n).exists()}
    if not need:
        return
    tar = download(PLACES_TAR, L.LOC / 'places' / 'val_large.tar')
    with tarfile.open(tar, 'r|') as tf:
        for m in tf:
            b = os.path.basename(m.name)
            if m.isfile() and b in need:
                with tf.extractfile(m) as fs, open(Path(dest) / b, 'wb') as fd:
                    shutil.copyfileobj(fs, fd)
                need.discard(b)
                if not need:
                    break
    tar.unlink()
    if need:
        log('Places365 images missing from the archive: %d, e.g. %s' % (len(need), sorted(need)[:3]))


def fetch_oi(ids, dest, threads=16):
    from concurrent.futures import ThreadPoolExecutor

    def one(i):
        try:
            download(OI_URL % i, Path(dest) / (i + '.jpg'), tries=3)
        except Exception:
            pass
    with ThreadPoolExecutor(threads) as ex:
        list(ex.map(one, ids))


def build_rc(n=1638, n_cand=2000, n_review=96, seed=2026, device='cpu'):
    """Uniform random sample of the filtered mining corpus (Open Images v7 test + Places365 val), without the
    mining-development images, the fire-like exclusions and near-duplicates of any evaluation image, then
    the SAFE-Mine fire-like rule. The n_review most fire-like eligible images go on the R sheets."""
    man = R2 / 'rc_manifest.csv'
    if man.exists() and L.SOURCES['rc'].exists():
        log('random corpus control already built')
        return
    md = L._manifest_dir()
    oi_ids = L.read_json(md / 'oi_corpus_ids.json')
    places = places_filtered()
    excl = set(L.read_json(md / 'dev_neg.json')) | set(L.read_json(md / 'fire_block.json'))
    corpus = [('openimages', i + '.jpg') for i in oi_ids] + [('places365', p) for p in places]
    log('mining corpus rebuilt: %d Open Images + %d Places365 = %d (paper: 76,183)' % (len(oi_ids), len(places), len(corpus)))
    pool = [c for c in corpus if c[1] not in excl]
    cand = random.Random(seed).sample(pool, n_cand)
    raw = L.LOC / 'rc_raw'
    raw.mkdir(parents=True, exist_ok=True)
    fetch_oi([nm[:-4] for s, nm in cand if s == 'openimages'], raw)
    fetch_places([nm for s, nm in cand if s == 'places365'], raw)
    ok = [(s, nm) for s, nm in cand if (raw / nm).exists() and image_ok(raw / nm)]
    sha, dh = eval_hashes()
    dup = [near_eval(raw / nm, sha, dh) for _, nm in ok]
    fs, ss = clip_scores([raw / nm for _, nm in ok], FIRE_P, SAFE_P, device)
    flag = fire_like(fs, ss)
    elig = [i for i in range(len(ok)) if not flag[i] and not dup[i]]
    assert len(elig) >= n + 40, 'only %d usable images; raise n_cand' % len(elig)
    review = sorted(elig, key=lambda i: -(fs[i] - ss[i]))[:n_review]
    lab = {i: 'R%d' % (k + 1) for k, i in enumerate(review)}
    conf, es = L.hits_table(), set(elig)
    rows = [[nm, s, k + 1, int(nm in conf), round(float(fs[k]), 4), round(float(ss[k]), 4), int(flag[k]), int(dup[k]),
             int(k in es), lab.get(k, '')] for k, (s, nm) in enumerate(ok)]
    L.zip_flat([raw / ok[i][1] for i in elig], L.SOURCES['rc'])
    L.write_csv(man, ['image', 'source', 'sample_order', 'is_mining_hit', 'fire_sim', 'safe_sim', 'fire_like',
                      'near_dup_eval', 'eligible', 'review_label'], rows)
    sheets([(lab[i], raw / ok[i][1]) for i in review], 'R')
    log('RC candidates: %d sampled, %d readable, %d fire-like, %d near-duplicates of evaluation images, %d eligible; '
        '%d most fire-like on the R sheets' % (n_cand, len(ok), int(flag.sum()), sum(dup), len(elig), len(review)))


def finalize_rc(flagged_r, n=1638):
    man = L.OUT / 'manifests' / 'neg_RC.json'
    if not _rebuild_ok(man, flagged_r, ('RC__',)):
        return
    rows = read_rows(R2 / 'rc_manifest.csv')
    unknown = sorted(set(flagged_r) - {r['review_label'] for r in rows if r['review_label']})
    assert not unknown, 'R labels not on the sheets: %s' % unknown
    elig = [r for r in sorted(rows, key=lambda r: int(r['sample_order'])) if r['eligible'] == '1']
    kept = [r for r in elig if r['review_label'] not in flagged_r][:n]
    assert len(kept) == n
    top = set(L.read_json(L._manifest_dir() / 'round0_top.json'))
    res = {'items': [['rc', r['image']] for r in kept], 'n': n, 'flagged': sorted(flagged_r),
           'n_openimages': sum(r['source'] == 'openimages' for r in kept),
           'n_places365': sum(r['source'] == 'places365' for r in kept),
           'n_mining_hits': sum(r['is_mining_hit'] == '1' for r in kept),
           'n_in_mtop': sum(r['image'] in top for r in kept),
           'description': 'Random control from the filtered mining corpus: %d images drawn uniformly (random.Random(2026)) '
                          'from Open Images v7 test and Places365 validation after label filtering, without mining-'
                          'development images, fire-like exclusions and near-duplicates of evaluation images, passed '
                          'through the SAFE-Mine fire-like rule; %d removed after the visual audit' % (n, len(flagged_r))}
    L.write_json(man, res)
    log('RC: %d images (%d Open Images, %d Places365; %d are mining hits, %d in M-top), %d removed in the audit'
        % (n, res['n_openimages'], res['n_places365'], res['n_mining_hits'], res['n_in_mtop'], len(flagged_r)))


# ------------------------------------------------------------------ stage 1: domestic negatives
def build_domestic(n=1500, spare=60, n_review=48, seed=2026, device='cpu'):
    """Household scenes of SUN RGB-D, a source never used in mining or training. Nothing is dropped
    automatically: the most fire-like images (at least all the fire-like rule flags) go on the D sheets."""
    man = R2 / 'domestic_manifest.csv'
    if man.exists() and (R2 / 'domestic.zip').exists():
        log('domestic set already built')
        return
    z = download(SUN_ZIP, L.LOC / 'sun' / 'SUNRGBD.zip')
    d = L.LOC / 'domestic_raw'
    d.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(z) as zf:
        names = zf.namelist()
        scene = {nm[:-len('scene.txt')]: zf.read(nm).decode('utf-8', 'replace').strip()
                 for nm in names if nm.endswith('/scene.txt')}
        img = {}
        for nm in names:
            m = re.match(r'(.*/)image/[^/]+\.(jpg|png)$', nm, re.I)
            if m and m.group(1) in scene:
                img.setdefault(m.group(1), nm)
        cnt = {}
        for k in img:
            cnt[scene[k]] = cnt.get(scene[k], 0) + 1
        log('SUN RGB-D samples by scene: %s' % sorted(cnt.items(), key=lambda x: -x[1])[:30])
        dom = sorted(k for k in img if scene[k] in DOMESTIC_SCENES)
        pick = random.Random(seed).sample(dom, min(len(dom), n + spare))
        local = []
        for k in pick:
            out = d / ('sun_' + re.sub(r'[^A-Za-z0-9]+', '_', k.strip('/')) + Path(img[k]).suffix.lower())
            if not out.exists():
                with zf.open(img[k]) as fs, open(out, 'wb') as fd:
                    shutil.copyfileobj(fs, fd)
            local.append((k, out))
    log('household samples: %d, sampled %d' % (len(dom), len(local)))
    local = [(k, p) for k, p in local if image_ok(p, 100)]
    fs, ss = clip_scores([p for _, p in local], FIRE_P, SAFE_P, device)
    flag = fire_like(fs, ss)
    review = sorted(range(len(local)), key=lambda i: -(fs[i] - ss[i]))[:max(n_review, int(flag.sum()))]
    lab = {i: 'D%d' % (k + 1) for k, i in enumerate(review)}
    rows = [[p.name, k, scene[k], i + 1, L.sha256_file(p), round(float(fs[i]), 4), round(float(ss[i]), 4), int(flag[i]),
             lab.get(i, '')] for i, (k, p) in enumerate(local)]
    L.zip_flat([p for _, p in local], R2 / 'domestic.zip')
    L.write_csv(man, ['image', 'sun_sample', 'scene', 'sample_order', 'sha256', 'fire_sim', 'safe_sim', 'fire_like',
                      'review_label'], rows)
    sheets([(lab[i], local[i][1]) for i in review], 'D')
    log('domestic: %d household images (%d flagged by the fire-like rule); %d most fire-like on the D sheets'
        % (len(local), int(flag.sum()), len(review)))
    z.unlink()


def finalize_domestic(flagged_d, n=1500):
    rows = sorted(read_rows(R2 / 'domestic_manifest.csv'), key=lambda r: int(r['sample_order']))
    unknown = sorted(set(flagged_d) - {r['review_label'] for r in rows if r['review_label']})
    assert not unknown, 'D labels not on the sheets: %s' % unknown
    keep = [r['image'] for r in rows if r['review_label'] not in flagged_d][:n]
    d = L.LOC / 'pools' / 'domestic'
    used = L.read_json(d / 'USED.json')
    if used is None or used.get('flagged') != sorted(flagged_d):
        shutil.rmtree(d, ignore_errors=True)
        L.extract_members(R2 / 'domestic.zip', keep, d)
        L.write_json(d / 'USED.json', {'n': len(keep), 'flagged': sorted(flagged_d)})
    k = set(keep)
    L.write_csv(R2 / 'domestic_used.csv', ['image', 'scene', 'used'],
                [[r['image'], r['scene'], int(r['image'] in k)] for r in rows])
    log('domestic set: %d images, %d removed in the audit' % (len(keep), len(flagged_d)))
    return d


# ------------------------------------------------------------------ stage 1: indoor share of the D-Fire negatives
def dfire_indoor(device='cpu', n_check=48):
    out = R2 / 'dfire_indoor.csv'
    if out.exists():
        return
    sets = {'dfire_neg': L.ensure_suites()['dfire_neg']}
    sets.update({k: v for k, v in L.ensure_fresh().items() if k == 'F_cross'})
    rows = []
    for name, d in sets.items():
        ps = L.imgs_in(d)
        a, b = clip_scores(ps, INDOOR_P, OUTDOOR_P, device)
        lab = ['indoor' if x > y else 'outdoor' for x, y in zip(a, b)]
        rows += [[name, p.name, round(float(x), 4), round(float(y), 4), l] for p, x, y, l in zip(ps, a, b, lab)]
        chk = sorted(random.Random(7).sample(range(len(ps)), min(n_check, len(ps))))
        sheets([('%s%d' % ('IN' if lab[i] == 'indoor' else 'OUT', i), ps[i]) for i in chk], name,
               R2 / 'figures' / 'dfire_indoor_check')
        log('%s: %d of %d images classified indoor' % (name, lab.count('indoor'), len(lab)))
    L.write_csv(out, ['subset', 'image', 'indoor_sim', 'outdoor_sim', 'label'], rows)


# ------------------------------------------------------------------ stage 2: sets after the audit
def parse_flagged(text):
    toks = re.findall(r'([MRDmrd])\s*(\d+)', text or '')
    return {c: sorted({'%s%d' % (c, int(n)) for k, n in toks if k.upper() == c}, key=lambda s: int(s[1:])) for c in 'MRD'}


def build_clean_sets(flagged_m):
    """MC = M-top without the marked images, refilled in score order from the audited reserve.
    UC = L-ratio + MC, as the deployed union (lit candles of L-ratio stay: nuisance sources, not fires)."""
    man = L.OUT / 'manifests' / 'neg_MC.json'
    if not _rebuild_ok(man, flagged_m, ('MC__', 'UC__')):
        return
    key = {r['label']: r for r in read_rows(R2 / 'audit_M.csv')}
    unknown = sorted(set(flagged_m) - set(key))
    assert not unknown, 'M labels not on the sheets: %s' % unknown[:10]
    bad = {key[l]['image'] for l in flagged_m}
    top, reserve, _ = mtop_lists()
    removed = [n for n in top if n in bad]
    refill = [n for n in reserve if n not in bad][:len(removed)]
    assert len(refill) == len(removed), 'reserve too small: %d removed, %d clean reserve' % (len(removed), len(refill))
    mc = [n for n in top if n not in bad] + refill
    lr = L.read_json(L._manifest_dir() / 'ratio_hn30.json')
    seen, uc = set(), []
    for k, n in [('hn_pool', n) for n in lr] + [('hits', n) for n in mc]:
        if n not in seen:
            seen.add(n)
            uc.append([k, n])
    L.write_json(L.OUT / 'manifests' / 'neg_UC.json',
                 {'items': uc, 'n': len(uc), 'flagged': sorted(flagged_m),
                  'description': 'L-ratio + audited M-top (MC), deduplicated by file name, as the deployed union'})
    L.write_json(man, {'items': [['hits', n] for n in mc], 'n': len(mc), 'flagged': sorted(flagged_m), 'removed': removed,
                       'refill': refill,
                       'description': 'M-top after a visual audit of all 1,638 images: %d images showing fire or smoke '
                                      'removed and replaced by the next eligible hits in score order (also audited)'
                                      % len(removed)})
    L.write_csv(R2 / 'mtop_audit_result.csv', ['label', 'image', 'set', 'marked', 'action'],
                [[l, r['image'], r['set'], int(l in flagged_m),
                  'removed' if r['image'] in removed else 'refill' if r['image'] in refill else ''] for l, r in key.items()])
    log('MC: %d of 1,638 removed and refilled (%d more marked in the reserve); UC: %d images'
        % (len(removed), len(bad) - len(removed), len(uc)))


def jobs_round2(part='all'):
    """Same recipe as every revision run. Longest runs first, so the queue ends together."""
    parts = {'A': [('RC', False), ('MC', False)], 'B': [('UC', True), ('UC', False)]}
    use = parts['B'] + parts['A'] if part == 'all' else parts[part]
    why = {'RC': 'random control from the mining corpus', 'MC': 'audited M-top', 'UC': 'audited union'}
    return [{'run_id': '%s__%s__yolo26n__s%d' % (neg, 'KD' if kd else 'noKD', seed), 'neg_set': neg, 'kd': kd,
             'arch': 'yolo26n', 'base': 'yolo26n.pt', 'seed': seed, 'imgsz': 640, 'batch': 32, 'priority': 1,
             'why': 'round 2: ' + why[neg]} for neg, kd in use for seed in SEEDS]


def all_done():
    return all((L.OUT / 'runs' / j['run_id'] / 'DONE.json').exists() for j in jobs_round2('all'))


# ------------------------------------------------------------------ stage 2: scoring
def model_list():
    """(tag, weights, imgsz, eval_dir) of every scored model: rescored earlier models and every revision run."""
    out = []
    for d in sorted((L.OUT / 'scores').glob('*')):
        s = L.read_json(d / 'SCORED.json')
        if s and '__clipverify' not in d.name and Path(s['weights']).exists():
            out.append((d.name, s['weights'], int(s.get('imgsz', 640)), d))
    for d in sorted((L.OUT / 'runs').glob('*')):
        if (d / 'DONE.json').exists() and (d / 'best.pt').exists():
            out.append((d.name, str(d / 'best.pt'), 640, d / 'eval'))
    return out


def score_domestic(folder):
    from ultralytics import YOLO
    ms = model_list()
    for k, (tag, w, imgsz, ed) in enumerate(ms):
        if not (Path(ed) / 'neg_domestic.csv').exists():
            L.scan_neg(YOLO(str(w)), folder, Path(ed) / 'neg_domestic.csv', imgsz,
                       boxes_csv=Path(ed) / 'negboxes_domestic.csv')
        if k % 10 == 9:
            log('domestic set: %d / %d models' % (k + 1, len(ms)))
    log('domestic set scored by %d models' % len(ms))


def dump_test_preds(hf, conf=0.01):
    """Boxes >= conf on the test split (normalised xyxy) and its labels, for bootstrap intervals of mAP."""
    from ultralytics import YOLO
    imgs = L.imgs_in(hf / 'test' / 'images')
    if not (R2 / 'test_labels.csv').exists():
        L.write_csv(R2 / 'test_labels.csv', ['img', 'cls', 'xc', 'yc', 'w', 'h'],
                    [[p.name, int(g[0])] + [round(float(x), 6) for x in g[1:5]]
                     for p in imgs for g in L._gt(hf / 'test' / 'labels' / (p.stem + '.txt'))])
    runs = str(L.OUT / 'runs')
    ms = [m for m in model_list() if str(m[3]).startswith(runs) or m[0] in OLD_WEIGHTS]
    for tag, w, imgsz, ed in ms:
        f = Path(ed) / 'test_preds.csv.gz'
        if f.exists():
            continue
        model, rows = YOLO(str(w)), []
        for i in range(0, len(imgs), 64):
            for p, r in L._predict_safe(model, imgs[i:i + 64], imgsz, conf):
                if r.boxes is not None and len(r.boxes):
                    for b, c, k in zip(r.boxes.xyxyn.cpu().numpy(), r.boxes.conf.cpu().numpy(), r.boxes.cls.cpu().numpy()):
                        rows.append('%s,%d,%.4f,%.5f,%.5f,%.5f,%.5f' % (Path(p).name, int(k), c, b[0], b[1], b[2], b[3]))
        tmp = f.with_name(f.name + '.tmp')
        with gzip.open(tmp, 'wt') as g:
            g.write('img,cls,conf,x1,y1,x2,y2\n' + ''.join(r + '\n' for r in rows))
        os.replace(tmp, f)
    log('test-split boxes saved for %d models' % len(ms))


# ------------------------------------------------------------------ stage 2: videos
def video_inventory():
    """The clips of SFS_05 (same keys and roles), from the raw zips on Drive."""
    out = []
    for z in sorted((L.OUT / 'video' / 'raw').glob('*.zip')):
        d = L.LOC / 'video' / z.stem
        if not d.exists():
            zipfile.ZipFile(z).extractall(d)
        for p in sorted(d.rglob('*')):
            if p.suffix.lower() not in L.VID_EXT:
                continue
            low = str(p.relative_to(d)).lower()
            if z.stem.startswith(('fire_videos', 'smoke_videos')):
                kind = 'FS_fire' if z.stem.startswith('fire') else 'FS_smoke'
                role = 'negative' if 'neg' in low else ('positive' if 'pos' in low else 'unknown')
            elif z.stem.startswith('Smoke_flame_like'):
                kind, role = 'KMU_like', 'negative'
            elif 'short_distance' in z.stem and 'flame' in z.stem:
                kind = 'KMU_flame'
                role = 'indoor_small' if p.stem.lower() in ('flame2', 'flame3', 'flame4', 'flame5') else 'other'
            else:
                kind, role = z.stem, 'other'
            out.append({'key': ('%s__%s' % (kind, p.stem)).replace(' ', '_'), 'path': str(p), 'kind': kind, 'role': role})
    return out


def reencode(v):
    """H.264 copy of a clip the OpenCV reader could not decode; every frame kept at the original rate."""
    dst = L.LOC / 'video' / 'reencoded' / (v['key'] + '.mp4')
    dst.parent.mkdir(parents=True, exist_ok=True)
    for extra in ([], ['-err_detect', 'ignore_err', '-fflags', '+discardcorrupt+genpts']):
        if dst.exists() and dst.stat().st_size > 0:
            break
        r = subprocess.run([FFMPEG, '-y', '-v', 'error'] + extra + ['-i', v['path'], '-map', '0:v:0', '-c:v', 'libx264',
                            '-preset', 'veryfast', '-crf', '17', '-pix_fmt', 'yuv420p', '-vsync', '0', '-an', str(dst)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            log('ffmpeg %s: %s' % (v['key'], (r.stderr or '').strip()[-300:]))
            dst.unlink(missing_ok=True)
    return dict(v, path=str(dst), source=v['path'], reencoded=1) if dst.exists() else dict(v, note='ffmpeg failed')


def run_videos(new_runs):
    """B1: unreadable clips re-encoded and run through the paper's video models. B2: every clip for the new runs."""
    vids = L.probe_videos(video_inventory(), L.OUT / 'video' / 'thumbs', L.LOC / 'video' / 'frames')
    final = []
    for v in vids:
        if not v.get('ok') and v['role'] in ('negative', 'positive'):
            v = reencode(v)
            if v.get('reencoded'):
                v = L.probe_videos([v], L.OUT / 'video' / 'thumbs', L.LOC / 'video' / 'frames')[0]
        final.append(v)
    L.write_csv(R2 / 'video_list_round2.csv', ['key', 'kind', 'role', 'frames', 'fps', 'seconds', 'readable', 'reencoded', 'note'],
                [[v['key'], v['kind'], v['role'], v.get('frames'), v.get('fps'), v.get('seconds'), int(bool(v.get('ok'))),
                  v.get('reencoded', 0), v.get('note', '')] for v in final])
    clips = [v for v in final if v.get('ok') and v['role'] in ('negative', 'positive')]
    fixed = [v for v in clips if v.get('reencoded')]
    log('clips: %d positive + %d negative readable; re-encoded: %s'
        % (sum(v['role'] == 'positive' for v in clips), sum(v['role'] == 'negative' for v in clips),
           ', '.join(v['key'] for v in fixed) or 'none'))
    W = lambda m: L.SRC / 'weights' / (m + '__best.pt') if m in OLD_WEIGHTS else L.OUT / 'runs' / m / 'best.pt'
    vl = lambda vs: [{'key': v['key'], 'path': v['path']} for v in vs]
    ind = [v for v in final if v['role'] == 'indoor_small' and v.get('ok')]
    specs = [{'tag': m, 'weights': str(W(m)), 'imgsz': 640, 'mode': 'dets', 'out_dir': str(L.OUT / 'video' / 'dets' / m),
              'videos': vl(fixed)} for m in VIDEO_MODELS if W(m).exists()]
    for r in new_runs:
        specs.append({'tag': r, 'weights': str(W(r)), 'imgsz': 640, 'mode': 'dets',
                      'out_dir': str(L.OUT / 'video' / 'dets' / r), 'videos': vl(clips)})
        specs.append({'tag': r, 'weights': str(W(r)), 'imgsz': 640, 'mode': 'maxconf',
                      'out_dir': str(L.OUT / 'video' / 'indoor_maxconf' / r), 'videos': vl(ind)})
    specs = [s for s in specs if s['videos']]
    if not specs:
        return {}
    f = L.LOC / 'video_specs_round2.json'
    L.write_json(f, specs)
    return L.run_video_specs(f, min(4, len(specs)), L.OUT / 'logs' / 'video', 'round2')


def post_training(flagged, hf):
    """Everything after the 12 runs; idempotent. Done by whichever session finishes the last run."""
    if (R2 / 'POST_DONE.json').exists():
        log('post-training steps already done')
        return
    score_domestic(finalize_domestic(flagged['D']))
    dump_test_preds(hf)
    res = run_videos([j['run_id'] for j in jobs_round2('all')])
    L.write_json(R2 / 'POST_DONE.json', {'at': L.now_iso(), 'video': res})
    log('post-training steps done')
