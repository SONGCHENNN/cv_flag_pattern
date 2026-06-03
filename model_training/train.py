"""
train.py — YOLOv8s Flag Pattern Training Script
GPU: GTX 1650 4GB | Dataset: 133 train / 33 val | Class: flag

Install:
    pip install ultralytics
    pip install torch torchvision --index-url https://download.pytorch.org/whl/cu111

Usage:
    python train.py
"""

import os
import shutil
from pathlib import Path
from ultralytics import YOLO
import torch
import yaml

# ── Sanity checks ─────────────────────────────────────────────────────────────

print("=" * 55)
print("  FLAG PATTERN — YOLOv8s Training")
print("=" * 55)
print(f"  PyTorch  : {torch.__version__}")
print(f"  CUDA available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"  GPU      : {torch.cuda.get_device_name(0)}")
    print(f"  VRAM     : {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
print("=" * 55 + "\n")

# ── Config ────────────────────────────────────────────────────────────────────

DATA_YAML   = "data.yaml"       # path to your Roboflow data.yaml
MODEL       = "yolo26s.pt"      # YOLOv8 small — downloads automatically
PROJECT_DIR = "runs/flag"       # where results are saved
RUN_NAME    = "v1"

# Training hyperparameters — tuned for GTX 1650 4GB
EPOCHS      = 100
BATCH_SIZE  = 8                 # safe for 4GB VRAM; increase to 16 if no OOM
IMG_SIZE    = 640
PATIENCE    = 20                # early stopping if no improvement for 20 epochs
WORKERS     = 2                 # keep low on Windows to avoid multiprocessing issues

# ── Augmentation config ───────────────────────────────────────────────────────
# These override YOLOv8 defaults — tuned for chart pattern detection

AUGMENTATION = {
    # Geometric — simulate different chart zoom levels and aspect ratios
    "scale"      : 0.3,     # zoom in/out ±30% (simulates chart zoom)
    "shear"      : 2.0,     # slight shear ±2° (simulates monitor angle)
    "perspective": 0.0003,  # very slight perspective warp
    "translate"  : 0.1,     # shift ±10% (pattern not always centered)

    # Flip — horizontal flip off (bull flag ≠ bear flag for now)
    "fliplr"     : 0.0,     # NO horizontal flip — changes pattern direction
    "flipud"     : 0.0,     # NO vertical flip — charts don't go upside down

    # Color/brightness — simulate different chart themes and times of day
    "hsv_h"      : 0.01,    # tiny hue shift
    "hsv_s"      : 0.3,     # saturation variation
    "hsv_v"      : 0.3,     # brightness variation ±30%

    # Mosaic — combines 4 images into 1, great for small datasets
    "mosaic"     : 0.8,     # 80% of batches use mosaic augmentation

    # Copy-paste — disabled, not useful for chart patterns
    "copy_paste" : 0.0,

    # MixUp — blends two images, subtle but helpful
    "mixup"      : 0.05,

    # Erasing — randomly erases small patches (simulates tooltips/overlays)
    "erasing"    : 0.2,
}

# ── Verify data.yaml exists ───────────────────────────────────────────────────

if not os.path.exists(DATA_YAML):
    print(f"ERROR: {DATA_YAML} not found.")
    print("Make sure data.yaml is in the same folder as train.py")
    exit(1)

# Print data.yaml contents for verification
with open(DATA_YAML) as f:
    print("data.yaml contents:")
    print("-" * 30)
    print(f.read())
    print("-" * 30 + "\n")

# ── Train ─────────────────────────────────────────────────────────────────────

model = YOLO(MODEL)

results = model.train(
    data        = DATA_YAML,
    epochs      = EPOCHS,
    batch       = BATCH_SIZE,
    imgsz       = IMG_SIZE,
    patience    = PATIENCE,
    workers     = WORKERS,
    device      = 0,            # GPU 0
    project     = PROJECT_DIR,
    name        = RUN_NAME,
    exist_ok    = True,

    # Optimizer
    optimizer   = "AdamW",      # better than SGD for small datasets
    lr0         = 0.001,        # initial learning rate
    lrf         = 0.01,         # final lr = lr0 * lrf
    warmup_epochs = 3,          # warmup for 3 epochs

    # Regularization — important for small datasets to avoid overfitting
    dropout     = 0.1,
    weight_decay= 0.0005,

    # Augmentation overrides
    **AUGMENTATION,

    # Logging
    plots       = True,         # save training plots
    save        = True,         # save best and last weights
    save_period = 10,           # save checkpoint every 10 epochs
    verbose     = True,
)

# ── Results summary ───────────────────────────────────────────────────────────

print("\n" + "=" * 55)
print("  Training Complete")
print("=" * 55)

best_weights = Path(PROJECT_DIR) / RUN_NAME / "weights" / "best.pt"
print(f"  Best weights : {best_weights}")
print(f"  Results      : {Path(PROJECT_DIR) / RUN_NAME}")
print(f"  mAP50        : {results.results_dict.get('metrics/mAP50(B)', 'N/A'):.4f}")
print(f"  mAP50-95     : {results.results_dict.get('metrics/mAP50-95(B)', 'N/A'):.4f}")
print("=" * 55)

# ── Quick validation ──────────────────────────────────────────────────────────

print("\nRunning validation on val set...")
val_results = model.val(data=DATA_YAML, imgsz=IMG_SIZE)
print(f"  Val mAP50    : {val_results.results_dict.get('metrics/mAP50(B)', 'N/A'):.4f}")
print(f"  Val Precision: {val_results.results_dict.get('metrics/precision(B)', 'N/A'):.4f}")
print(f"  Val Recall   : {val_results.results_dict.get('metrics/recall(B)', 'N/A'):.4f}")