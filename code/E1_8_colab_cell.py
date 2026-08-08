# ==========================================================================
#  E1.8 — التجربة القاتلة:  هل المشكلة والحل موجودان ببروتوكول الورقة نفسه؟
# ==========================================================================
#  الصقيها خلية واحدة في Colab **بعد تشغيل S1**.
#
#  الاعتراض الذي تسدّه هذه التجربة، حرفياً:
#      «نتيجتك عن الإنذارات الكاذبة تعود لاستخدامك أوزاناً مدرَّبة مسبقاً،
#       لا للسوالب المنقّبة.»
#
#  الردّ الوحيد المقنع هو إعادة إنتاج بروتوكول YOLO-HF كما هو — من الصفر،
#  بمعمارية YOLOv5s نفسها ووصفة SGD نفسها — ثم إضافة السوالب فقط، وقياس ما
#  يتغيّر. تدريبان، ومتغيّر واحد بينهما.
#
#  ⚠️ لماذا مستودع YOLOv5 الأصلي ولا ultralytics:
#      YOLO('yolov5s.yaml') في ultralytics 8.4 يبني **9.15 مليون** معامل،
#      بينما الورقة تُبلغ عن **7.02 مليون**. المستودع الأصلي يعطي 7.02
#      بالضبط عند صنفين — وهو ما استخدمته الورقة. الادعاء «أعدنا إنتاج
#      0.904» لا يصحّ بمعمارية أخرى.
#
#  البروتوكول (من الورقة، لا من عندي):
#      YOLOv5s • from scratch • 300 epoch • patience 100 على val mAP
#      • batch 32 • imgsz 640 • SGD lr0=0.01 • momentum 0.937 • wd 0.0005
#      المتوقع: mAP50 ≈ 0.904 ، mAP50-95 ≈ 0.603 ، P 0.930 ، R 0.833
# ==========================================================================

import os, sys, json, time, shutil, zipfile, subprocess
from pathlib import Path

try:
    ROOT, D_DATA, D_WEIGHTS, D_RESULTS, L_DS, header, ensure_home_fire_local, robust_extract
except NameError:
    raise RuntimeError("شغّلي S1 قبل هذه الخلية")

header("E1.8 — استنساخ بروتوكول YOLO-HF ثم إضافة السوالب")

E18       = ROOT / "e1_8"
E18.mkdir(parents=True, exist_ok=True)
YOLOV5    = Path("/content/yolov5")
SEED      = 42
EPOCHS    = 300
PATIENCE  = 100
BATCH     = 32
IMGSZ     = 640
RESULTS   = E18 / "e1_8_results.csv"


# ------------------------------------------------------------------ ١. المستودع
if not (YOLOV5 / "train.py").exists():
    print("استنساخ YOLOv5 v7.0 (وسم مثبَّت — لا فرع متحرك) ...")
    subprocess.run(["git", "clone", "--depth", "1", "--branch", "v7.0",
                    "https://github.com/ultralytics/yolov5", str(YOLOV5)], check=True)
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-r",
                    str(YOLOV5 / "requirements.txt")], check=False)


# ------------------------------------------------------------- ١.٥ طبقة التوافق
#  YOLOv5 v7.0 صدر نوفمبر 2022. بيئة Colab اليوم Python 3.12 و numpy 2 و
#  torch ≥ 2.6، وثلاثة أشياء تغيّرت تحته:
#
#    • torch.load صار weights_only=True افتراضياً، و check_amp() في v7.0
#      يحمّل yolov5n.pt — فيموت قبل أن يبدأ التدريب أصلاً.
#    • numpy 2 حذف np.trapz، ويستعمله utils/metrics.py عند حساب mAP.
#    • np.bool / np.int / np.float محذوفة منذ numpy 1.24.
#
#  تُعالَج كلها في sitecustomize.py، الذي يستورده بايثون تلقائياً عند الإقلاع.
#
#  ⚠️ لكنه يُستورد من مسارات sys.path المهيّأة **قبل** تشغيل السكربت، ومجلد
#     yolov5 يُضاف بعدها. لذلك لا بد من تمرير PYTHONPATH صراحةً في env أدناه.
#     بدون ذلك يبقى الملف على القرص ولا يُنفَّذ أبداً — وهذا بالضبط سبب فشل
#     المحاولة الأولى.
(YOLOV5 / "sitecustomize.py").write_text(
    "import functools\n"
    "import numpy as np\n"
    "import torch\n"
    "_orig = torch.load\n"
    "@functools.wraps(_orig)\n"
    "def _load(*a, **k):\n"
    "    k.setdefault('weights_only', False)\n"
    "    return _orig(*a, **k)\n"
    "torch.load = _load\n"
    "torch.load._e18_patched = True\n"
    "if not hasattr(np, 'trapz'):  np.trapz = np.trapezoid\n"
    "if not hasattr(np, 'bool'):   np.bool = bool\n"
    "if not hasattr(np, 'int'):    np.int = int\n"
    "if not hasattr(np, 'float'):  np.float = float\n")

ENV = dict(os.environ)
ENV["PYTHONPATH"] = str(YOLOV5) + os.pathsep + ENV.get("PYTHONPATH", "")

_chk = subprocess.run(
    [sys.executable, "-c",
     "import torch, numpy as np;"
     "print('torch.load patched :', getattr(torch.load, '_e18_patched', False));"
     "print('np.trapz available :', hasattr(np, 'trapz'));"
     "print('numpy', np.__version__, '| torch', torch.__version__)"],
    capture_output=True, text=True, cwd=str(YOLOV5), env=ENV)
print(_chk.stdout.strip() or _chk.stderr.strip()[-500:])
if "True" not in _chk.stdout:
    raise RuntimeError("طبقة التوافق لم تُحمَّل — لا تكملي، التدريب سيفشل")


# --------------------------------------------- ٢. تحقّق من المعمارية قبل أي تدريب
def check_params():
    """لا تُدرَّب ٣٠٠ epoch قبل التأكد أن المعمارية هي المقصودة."""
    r = subprocess.run(
        [sys.executable, "-c",
         "from models.yolo import Model;"
         "m = Model('models/yolov5s.yaml', ch=3, nc=2);"
         "print('PARAMS', sum(p.numel() for p in m.parameters()))"],
        capture_output=True, text=True, cwd=str(YOLOV5), env=ENV)
    n = None
    for ln in r.stdout.splitlines():
        if ln.startswith("PARAMS"):
            n = int(ln.split()[1])
    if n is None:
        print(r.stdout[-900:]); print(r.stderr[-900:])
        raise RuntimeError("فشل بناء النموذج — اقري المخرجات أعلاه")
    print("  YOLOv5s @ nc=2 : %.3f مليون معامل   (الورقة تقول 7.02)" % (n / 1e6))
    if abs(n / 1e6 - 7.02) > 0.15:
        print("  ⚠️ لا يطابق الورقة — لا تدّعي إعادة إنتاج قبل حلّ هذا")
    return n


check_params()


# ------------------------------------------------- ٣. المجموعتان: بلا سوالب / بها
hf_yaml = ensure_home_fire_local()
hf = Path(hf_yaml).parent
print("  home_fire :", hf)

# (أ) إيجابيات فقط — مجموعة الورقة كما هي، بلا أي تدخّل
ds_pos = E18 / "ds_pos"
ds_pos.mkdir(exist_ok=True)
(ds_pos / "data.yaml").write_text(
    "train: %s\nval: %s\ntest: %s\nnc: 2\nnames: [flame, smoke]\n"
    % (hf / "train" / "images", hf / "val" / "images", hf / "test" / "images"))

# (ب) نفسها + سوالب SAFE-Mine المنتقاة في الجولة صفر
sel = json.loads((D_DATA / "sm_manifest__round0_selected.json").read_text())
blk = set(json.loads((D_DATA / "sm_manifest__fire_block.json").read_text()))
keep = [s for s in sel if s not in blk]
print("  سوالب مختارة: %d ، محجوبة كنار مسرَّبة: %d ، صافي: %d"
      % (len(sel), len(sel) - len(keep), len(keep)))

ds_neg = E18 / "ds_combo"
neg_img = ds_neg / "images" / "extra"
neg_lbl = ds_neg / "labels" / "extra"
if not neg_img.exists() or len(list(neg_img.glob("*.jpg"))) < len(keep) * 0.9:
    shutil.rmtree(ds_neg, ignore_errors=True)
    neg_img.mkdir(parents=True); neg_lbl.mkdir(parents=True)
    hits = D_DATA / "sm_round0_hits.zip"
    assert hits.exists(), "sm_round0_hits.zip مفقود: " + str(hits)
    want = set(keep)
    n = 0
    with zipfile.ZipFile(hits) as z:
        for m in z.namelist():
            b = os.path.basename(m)
            if b in want:
                with z.open(m) as fsrc, open(neg_img / b, "wb") as fdst:
                    shutil.copyfileobj(fsrc, fdst)
                (neg_lbl / (Path(b).stem + ".txt")).write_text("")   # خلفية = تسمية فارغة
                n += 1
    print("  استُخرجت %d صورة سالبة" % n)
(ds_neg / "data.yaml").write_text(
    "train:\n  - %s\n  - %s\nval: %s\ntest: %s\nnc: 2\nnames: [flame, smoke]\n"
    % (hf / "train" / "images", neg_img,
       hf / "val" / "images", hf / "test" / "images"))


# ------------------------------------------------------------------ ٤. التدريب
def train(tag, data_yaml, epochs, patience, sanity=False):
    name = ("sanity_" if sanity else "") + tag
    out = YOLOV5 / "runs" / "train" / name / "weights" / "best.pt"
    keep_to = D_WEIGHTS / ("e18__%s__s%d__best.pt" % (tag, SEED))
    if (not sanity) and keep_to.exists():
        print("  ⏭ %s موجود — تخطّي التدريب" % keep_to.name)
        return keep_to
    cmd = [sys.executable, str(YOLOV5 / "train.py"),
           "--img", str(IMGSZ), "--batch", str(BATCH), "--epochs", str(epochs),
           "--data", str(data_yaml),
           "--cfg", str(YOLOV5 / "models" / "yolov5s.yaml"),
           "--weights", "",                       # فارغ = من الصفر، كما الورقة
           "--hyp", str(YOLOV5 / "data" / "hyps" / "hyp.scratch-low.yaml"),
           "--patience", str(patience), "--seed", str(SEED),
           "--name", name, "--exist-ok", "--device", "0"]
    print("\n  $ " + " ".join(cmd[1:]) + "\n")
    t0 = time.time()

    # المخرجات تُلتقط ثم تُطبع عند الفشل. تشغيلها بـ check=True وحده يبتلع
    # رسالة الخطأ الحقيقية ويترك CalledProcessError عارياً بلا سبب — وهذا ما
    # حدث في المحاولة الأولى وأضاع جولة كاملة.
    r = subprocess.run(cmd, cwd=str(YOLOV5), env=ENV,
                       capture_output=True, text=True)
    if r.returncode != 0:
        print("\n" + "!" * 72)
        print("  فشل train.py — آخر ٤٠ سطراً من مخرجاته:")
        print("!" * 72)
        for ln in (r.stdout + "\n" + r.stderr).strip().splitlines()[-40:]:
            print("   ", ln)
        print("!" * 72)
        raise RuntimeError("train.py رجع %d — السبب في الأسطر أعلاه" % r.returncode)

    for ln in r.stdout.strip().splitlines()[-6:]:
        print("   ", ln)
    print("  ⏱ %.1f دقيقة" % ((time.time() - t0) / 60))
    assert out.exists(), "best.pt مفقود: " + str(out)
    if not sanity:
        shutil.copy2(out, keep_to)
        return keep_to
    return out


# ٢ epoch أولاً — نفس ممارستك في X4: نثبت أن الربط سليم قبل حرق ساعات
print("\n" + "=" * 70)
print("  فحص سلامة الربط — ٢ epoch لكل مجموعة")
print("=" * 70)
train("pos", ds_pos / "data.yaml", 2, 2, sanity=True)
train("combo", ds_neg / "data.yaml", 2, 2, sanity=True)
print("\n✅ الربط سليم. التدريب الكامل يبدأ الآن — ساعات، اتركيه.\n")

w_pos = train("pos", ds_pos / "data.yaml", EPOCHS, PATIENCE)
w_neg = train("combo", ds_neg / "data.yaml", EPOCHS, PATIENCE)


# ---------------------------------------------------------- ٥. التقييم: mAP
def eval_map(weights, data_yaml, tag):
    r = subprocess.run(
        [sys.executable, str(YOLOV5 / "val.py"), "--weights", str(weights),
         "--data", str(data_yaml), "--img", str(IMGSZ), "--task", "test",
         "--name", "val_" + tag, "--exist-ok", "--device", "0"],
        capture_output=True, text=True, cwd=str(YOLOV5), env=ENV)
    if r.returncode != 0:
        print("  ⚠️ val.py رجع %d:" % r.returncode)
        for ln in (r.stdout + "\n" + r.stderr).strip().splitlines()[-25:]:
            print("   ", ln)
        return {}
    print(r.stdout[-1600:])
    out = {}
    for ln in r.stdout.splitlines():
        p = ln.split()
        if len(p) >= 7 and p[0] == "all":
            out = dict(P=float(p[3]), R=float(p[4]),
                       mAP50=float(p[5]), mAP5095=float(p[6]))
    return out


# --------------------------------------- ٦. التقييم: FPR على المجموعات المجمّدة
def scan_fpr(weights, tag):
    """أعلى ثقة لكل صورة سالبة، بمسار استدلال المستودع نفسه.

    لا يُستخدم ultralytics هنا: أوزان مستودع YOLOv5 صنف مختلف ولا تُحمَّل به،
    وخلط مسارين للاستدلال يجعل الأرقام غير قابلة للمقارنة.
    """
    import numpy as np, torch, cv2
    sys.path.insert(0, str(YOLOV5))
    from models.common import DetectMultiBackend
    from utils.augmentations import letterbox
    from utils.general import non_max_suppression

    dev = torch.device("cuda:0")
    model = DetectMultiBackend(str(weights), device=dev, dnn=False, fp16=False)
    model.warmup(imgsz=(1, 3, IMGSZ, IMGSZ))

    out = {}
    for zname, key in (("hn_holdout_500.zip", "hn_holdout"),
                       ("novel_firelike.zip", "novel"),
                       ("mined_dev.zip", "mined_dev"),
                       ("dfire_neg_1500.zip", "dfire_neg")):
        zp = ROOT / "eval_suite_v2" / zname
        if not zp.exists():
            print("  ⚠️ مفقود:", zp); continue
        z = zipfile.ZipFile(zp)
        names = [n for n in z.namelist() if n.lower().endswith((".jpg", ".png", ".jpeg"))]
        mx = []
        for i, n in enumerate(names):
            buf = np.frombuffer(z.read(n), np.uint8)
            im0 = cv2.imdecode(buf, cv2.IMREAD_COLOR)
            if im0 is None:
                continue
            im = letterbox(im0, IMGSZ, stride=model.stride, auto=False)[0]
            im = im.transpose((2, 0, 1))[::-1]
            im = torch.from_numpy(np.ascontiguousarray(im)).to(dev).float() / 255.0
            with torch.no_grad():
                pred = model(im[None])
            pred = non_max_suppression(pred, conf_thres=0.001, iou_thres=0.45)[0]
            mx.append(float(pred[:, 4].max()) if len(pred) else 0.0)
            if (i + 1) % 250 == 0:
                print("    %s %d/%d" % (key, i + 1, len(names)))
        a = np.array(mx)
        out["FPR25_" + key] = round(100.0 * float((a >= 0.25).mean()), 2)
        out["FPR50_" + key] = round(100.0 * float((a >= 0.50).mean()), 2)
        np.savetxt(str(E18 / ("scores_%s__%s.csv" % (tag, key))), a,
                   fmt="%.6f", header="max_conf", comments="")
        print("  %-12s %-10s FPR@0.50 = %5.2f %%" % (tag, key, out["FPR50_" + key]))
    return out


import pandas as pd

rows = []
for tag, w, dy in (("pos_only", w_pos, ds_pos / "data.yaml"),
                   ("plus_safemine", w_neg, ds_neg / "data.yaml")):
    header("تقييم: " + tag, "-")
    r = {"run": tag, "protocol": "YOLO-HF (scratch, SGD, 300ep)",
         "model": "yolov5s", "seed": SEED}
    r.update(eval_map(w, dy, tag))
    r.update(scan_fpr(w, tag))
    rows.append(r)

df = pd.DataFrame(rows)
df.to_csv(RESULTS, index=False)

print("\n" + "=" * 78)
print("  E1.8 — النتيجة")
print("=" * 78)
print(df.to_string(index=False))
print()
print("  للمقارنة، ما تُبلغ عنه الورقة لـYOLOv5s: mAP50 0.904 | mAP50-95 0.603")
print("                                          P 0.930 | R 0.833")
print()
print("  كيف تُقرأ:")
print("   • صف pos_only قريب من 0.904  →  الاستنساخ صحيح، والأساس مشترك.")
print("   • FPR في pos_only مرتفع        →  المشكلة موجودة ببروتوكولهم أيضاً،")
print("                                     لا بسبب أوزان مدرَّبة مسبقاً.")
print("   • FPR ينهار في plus_safemine   →  والحل يعمل ببروتوكولهم أيضاً.")
print("   • فرق mAP50 بين الصفين          →  ثمن الموثوقية، معروضاً لا مخفياً.")
print()
print("  حُفظ في:", RESULTS)
