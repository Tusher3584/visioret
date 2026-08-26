"""RETIRED -- calibration script for an OOD stage that is no longer used.

    +---------------------------------------------------------------+
    | Nothing in the running system calls this, and running it        |
    | changes nothing. check_is_oct() uses the grayscale heuristic    |
    | plus CLIP (model/clip_ood.py) and never touches the stats this  |
    | script produces. Kept as a record of the experiment.            |
    +---------------------------------------------------------------+

What it did: computed the OCT-training-set feature centroid/std used by the
old feature-distance stage in model/ood_detector.py, from the already-trained
disease classifier. No training happened here -- just forward passes over a
sample of real OCT images to characterize "what OCT images look like" in
feature space, saved to model/checkpoints/ood_stats.pth.

Why it was retired: the calibration only ever saw Kermany images, so
"is this an OCT scan?" quietly became "does this look like a *Kermany* OCT
scan?". Real Noor Eye Hospital scans were rejected 3 times out of 5 -- a
different scanner produces legitimately different feature statistics, and a
single-dataset centroid has no way to know that. A gate that refuses real
patient data is worse than no gate. Replaced by a CLIP zero-shot check, which
needs no per-dataset calibration; see model/clip_ood.py and TODO.md.

A second, subtler problem it had: because the stats characterized the disease
model's own feature space, they went stale on every retrain, so forgetting to
re-run this after training was a live bug. The CLIP gate has no such coupling.

Usage (only if you are deliberately reproducing the retired experiment):
    python model/compute_ood_stats.py
"""

import os
import random
import sys

import torch

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from model.dataset import collect_samples  # noqa: E402
from model.inference import load_model, preprocess_image  # noqa: E402
from model.ood_detector import compute_ood_stats, save_ood_stats  # noqa: E402

DATA_ROOT = r"G:\Download\archive\OCT2017"
TRAIN_DIR = os.path.join(DATA_ROOT, "train")

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHECKPOINT_PATH = os.path.join(ROOT_DIR, "model", "checkpoints", "resnet50_oct.pth")

SAMPLES_PER_CLASS = 400  # -> ~1600 images, enough to characterize the feature distribution


def main():
    if not os.path.isdir(TRAIN_DIR):
        print(f"OCT dataset not found at '{TRAIN_DIR}'.")
        return

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

    model, checkpoint_loaded, classes, _val_macro_f1 = load_model(CHECKPOINT_PATH, device)
    if not checkpoint_loaded:
        print("No trained checkpoint found -- run train_full.py first.")
        return
    print(f"Loaded checkpoint, classes: {classes}")

    samples = collect_samples(TRAIN_DIR)
    by_class = {}
    for filepath, class_name, _patient_id in samples:
        by_class.setdefault(class_name, []).append(filepath)

    random.seed(42)
    selected_paths = []
    for class_name, paths in by_class.items():
        random.shuffle(paths)
        selected_paths.extend(paths[:SAMPLES_PER_CLASS])
    print(f"Calibrating on {len(selected_paths)} OCT images ({SAMPLES_PER_CLASS}/class)")

    from PIL import Image

    images, image_tensors = [], []
    for i, path in enumerate(selected_paths):
        image = Image.open(path).convert("RGB")
        images.append(image)
        image_tensors.append(preprocess_image(image))
        if (i + 1) % 200 == 0:
            print(f"  processed {i + 1}/{len(selected_paths)}")

    stats = compute_ood_stats(model, images, image_tensors, device)
    print(f"Centroid dim: {stats['centroid'].shape}, distance threshold: {stats['threshold']:.4f}")
    print(f"Intra-OCT distance p50/p90/p99: {stats['calibration_distances_p50_p90_p99']}")
    print(f"Brightness threshold: {stats['brightness_threshold']:.2f}")
    print(f"Intra-OCT brightness p50/p90/p99: {stats['calibration_brightness_p50_p90_p99']}")

    save_ood_stats(stats)
    print("Saved OOD stats to model/checkpoints/ood_stats.pth")


if __name__ == "__main__":
    main()
