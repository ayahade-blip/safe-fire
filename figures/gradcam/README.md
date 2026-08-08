# Grad-CAM — SAFE-Fire

Merged from two runs (sampled CPU pass, then a full GPU pass). Model:
`kd__kd6__s42__best.pt`, the deployed distilled YOLO26n. Images: the frozen
`home_fire` test split and the three frozen negative sets — nothing here was
seen during training.

---

## What was run

| | |
|---|---|
| test frames scanned | **1,300** (the whole positive split) |
| frames with labels | 1,285 |
| **usable Grad-CAM** | **1,232 — 96 %** |
| negatives scanned | **1,096** across three frozen sets |
| figures kept | 12 detection panels + 5 comparisons |

A first pass over a 157-frame sample gave the same 96 % success rate as the full
1,285, which is the useful thing to be able to state about the method.

---

## Method

**Grad-CAM** weights each feature channel by the gradient of a detection score.
**Eigen-CAM** (first principal component of the activations, no gradients) runs
alongside as a control — it cannot fail the way Grad-CAM can, so when the two
disagree entirely the Grad-CAM run is suspect. Eigen-CAM is class-agnostic and
looks diffuse by design; that is expected, not a fault.

### The trap that had to be fixed

Hooking a single layer before the head **silently returns an empty map about a
third of the time**. Measured on `test_1193.jpg`: backpropagating the top
detection gives a gradient of `3.8e-02` at the stride-16 neck output and
**exactly `0.0`** at stride-32, because that detection came from the P4 head and
the P5 branch contributes nothing to it. Correct arithmetic, but it looks like a
broken implementation.

All three levels feeding `Detect` are hooked instead — layers **16, 19, 22** in
YOLO26n — each converted to a CAM and summed. That took the success rate from
roughly two thirds to 96 %.

The scalar backpropagated is the **sum of all detection confidences above 0.25**,
not the single maximum, so the map covers every fire in the frame.

### Figures were chosen by measurement

Each map is scored by **concentration**: heat inside the ground-truth boxes,
divided by the fraction of the frame those boxes cover. 1.0 means the heat is
spread at random. The kept frames score **5–19** on targets covering 5–20 % of
the image. A coverage filter (5–55 %) is applied first, because frames with tiny
boxes score in the hundreds but are unreadable as figures.

Per-image numbers: `scores_full1285.csv` (full sweep) and `scores_sample157.csv`
(first pass).

### Display note

Overlays are clipped at the 99th percentile and blurred by ~1 % of the image
width. Raw maps are extremely peaky — on one candle frame 99.99 % of the map
sits below 0.5 — and would render blank. **Only the display mapping is affected;
every number in the CSVs is computed on the raw map.**

---

## Detection panels

Layout: input with ground truth · Grad-CAM · Eigen-CAM.

| File | Scene | Class |
|---|---|---|
| `gradcam_test_10.jpg` | Room fire indoors | flame |
| `gradcam_test_577.jpg` | Fire in a bowl, dark room | flame |
| `gradcam_test_1070.jpg` | Armchair fire indoors | flame |
| `gradcam_test_224.jpg` | Laptop fire, map traces the flame shape | flame |
| `gradcam_test_952.jpg` | Heat at the flame base, not the glow around it | flame |
| `gradcam_test_505.jpg` | Burning barrel, flame and the smoke above | flame + smoke |
| `gradcam_test_895.jpg` | Two separate fires in one frame, both found | flame |
| `gradcam_test_1068.jpg` | Campfire, heat follows the flame column | flame |
| `gradcam_test_582.jpg` | Ground fire, heat along the flame line | flame |
| `gradcam_test_390.jpg` | Smoke plume, one clean hotspot at its base | smoke |
| `gradcam_test_558.jpg` | Industrial chimney plume | smoke |
| `gradcam_test_318.jpg` | Chimney smoke against snow | smoke |

For a paper, `test_10` or `test_1070` (indoor, which is what the system is for)
plus `test_390` (clean smoke) carry the point on their own.

---

## Baseline vs SAFE-Fire on hard negatives

`compare_*.jpg`. Same image, two models — the negatives-free tournament baseline
and the deployed kd6. **No fire is present in any of them.**

### The scan behind the choice

All 1,096 images in the three frozen negative sets were run through both models
first (`negatives_scan.csv`); figures were made only where the baseline actually
fires, since a comparison on an image both models ignore shows nothing.

| set | n | baseline FPR@0.50 | SAFE-Fire FPR@0.50 |
|---|---|---|---|
| hard holdout — lamps, bulbs, candles | 500 | **27.60 %** | **1.20 %** |
| novel fire-like — torches, street/traffic lights | 196 | **18.37 %** | **1.53 %** |
| open-world mined | 400 | **37.50 %** | **2.75 %** |

**These reproduce the thesis numbers exactly.** `runs_master_v2.csv` records
27.6 % and 1.2 % for the hard holdout and 2.75 % for kd6 on mined — computed
months earlier on Colab, on a different machine, a different torch and a
different Ultralytics version. Reproducing them locally is an independent
verification of the central result and is worth stating in the thesis.

### The figures

| File | What the baseline attends to | baseline → SAFE-Fire |
|---|---|---|
| `compare_streetlamp.jpg` | The glowing globe, cleanly outlined | 1.33 → 0.01 |
| `compare_trafficlight.jpg` | Inside the red lamp itself | 1.57 → 0.00 |
| `compare_flower.jpg` | The orange centre of a water lily | 0.92 → 0.00 |
| `compare_shell.jpg` | Orange banding on a nautilus shell | 0.93 → 0.00 |
| `compare_candle_table.jpg` | The candle, and the warm-coloured pasta beside it | 0.87 → 0.00 |

`compare_streetlamp.jpg` and `compare_trafficlight.jpg` are the cleanest: one
hotspot exactly on the light source, a dark panel beside it.

**The flower and the shell deserve a sentence in the discussion.** Neither is a
lamp or a candle — neither is anything a person would think to collect as a hard
negative. They match two of the sixteen groups the CLIP clustering found in the
mined corpus: *red or orange flower* (n=624) and *orange vehicle or object*
(n=2,904). The attention maps land on the same confusers the clustering found,
by a completely different route. That is independent support for the argument
that hand-picked negatives miss what the model actually reacts to.

### What not to claim

Maps are scaled by each model's own peak confidence before colouring, so a
silent model renders dark. Normalising each map to its own range would stretch
the near-zero output of a model that detected nothing to full saturation and
make it look like it is staring at the candle.

Even so, not every negative gives a clean map. Of the twelve strongest
candidates, roughly half put their peak on the light source; the rest scatter or
produce blobs at the frame border. A steam locomotive with a baseline confidence
of 2.05 puts its strongest blob in a corner, not on the plume. The five kept
here were chosen after looking at all twelve.

**The FPR table is the evidence. The figures illustrate it. A heatmap is not
proof on its own.**

---

## The failure case

`failure_test_680.jpg`. Every figure above is a success, and a section made only
of successes reads as a selection. This one is the counterweight, and it says
something more precise than "sometimes it does not work".

A domestic living room was chosen deliberately — a snowy roof would invite the
answer that it lies outside the system's domain anyway. This is exactly the
scene the system is built for.

| | |
|---|---|
| Detector box vs ground truth | **IoU 0.80** |
| Detection confidence | **0.70** |
| Grad-CAM concentration | **0.02** (1.0 = random) |

**The detector is right and the explanation is wrong.** The model puts its box on
the small smoke source by the coffee table, overlapping the annotation. The
attention map meanwhile lights up the orange cushions, the curtain edge and the
clutter on the floor, and puts almost nothing on the smoke it just detected.
Eigen-CAM does the same.

That is why the first cell shows **both** boxes: without the green prediction box
a reader would assume the detector missed, and the actual point would be lost.

Worth noticing where the heat does land — the **orange cushions**. The model did
not alarm on them, but its attention is drawn there, which is the same pull the
CLIP clustering identified as *orange vehicle or object*.

### How common, and what it means

Of the 1,232 frames with a usable map:

- **61 frames** score a concentration below 1.0 while detecting at confidence
  above 0.7 — heat less concentrated on the target than chance, despite a
  confident, correct detection.
- **53 further frames** produce no usable map at all: the gradient-weighted
  combination comes out entirely negative and ReLU zeroes it.

Together about 9 % of the split. The low-concentration cases are dominated by
**small, faint smoke targets in visually busy scenes**, which is exactly the
regime where a coarse 80×80 or 40×40 feature grid has little to localise with.

### What to write

Do not present this as a limitation of the detector, because it is not one. The
honest statement is about the method:

> Grad-CAM agrees with the detector on most frames but not all. On roughly one
> frame in ten the model localises correctly while the attribution does not,
> most often on small smoke targets in cluttered scenes. Attention maps are
> therefore reported as qualitative support for the quantitative results, never
> as evidence in their own right.

Saying that costs nothing and protects the whole section: a reviewer who runs
the method and hits a scattered map will find it already documented rather than
appearing to have caught something hidden. It is also the reason every figure
here carries a measured concentration score instead of being chosen by eye.

---

## Reproducing

Scripts are in the session scratchpad: `cam.py` (both CAM methods, the
concentration metric), `run_cam.py` (sweep, device-selectable), `render.py`
(panels and comparisons), `scan_negatives.py`, `make_compare.py`.

Environment: Python 3.14, torch 2.12.0+cu130, ultralytics 8.4.115, RTX 4060.

The pipeline is CPU-bound, not GPU-bound — 1041 ms/image on CPU against
643 ms on GPU, only 1.6×, with GPU utilisation at 3 % during the sweep. The cost
is JPEG decode, letterboxing and the per-level SVD that Eigen-CAM runs on the
CPU. Plain inference is a different story: 23.1 ms against 64.9 ms, a clean 2.8×.
