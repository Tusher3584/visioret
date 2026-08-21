"""Evaluates the trained checkpoint on the reserved, patient-disjoint test
split (see train_full.py / model/checkpoints/patient_split.json).

The official OCT2017 test/ folder is NOT used directly here: it leaks ~85%
of its patients into the official train/ folder (verified), so a model that
saw those patients during training would report inflated numbers on it. This
script evaluates only on the test patients reserved before any training
happened, pooled from train+val+test and re-split by patient id.

Produces the metrics promised in the proposal: per-class precision/recall/F1
and a confusion matrix.

Usage:
    python model/evaluate.py
"""

import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import torch
from sklearn.metrics import ConfusionMatrixDisplay, classification_report, confusion_matrix
from torch.utils.data import DataLoader
from torchvision import transforms

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from model.dataset import OCTDataset, collect_samples, filter_by_patients  # noqa: E402
from model.inference import IMAGENET_MEAN, IMAGENET_STD, load_model  # noqa: E402
from model.oct_preprocessing import limit_worker_cv2_threads  # noqa: E402

DATA_ROOT = r"G:\Download\archive\OCT2017"
TRAIN_DIR = os.path.join(DATA_ROOT, "train")
VAL_DIR = os.path.join(DATA_ROOT, "val")
TEST_DIR = os.path.join(DATA_ROOT, "test")

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHECKPOINT_PATH = os.path.join(ROOT_DIR, "model", "checkpoints", "resnet50_oct.pth")
SPLIT_PATH = os.path.join(ROOT_DIR, "model", "checkpoints", "patient_split.json")
REPORT_PATH = os.path.join(ROOT_DIR, "model", "checkpoints", "evaluation_report.txt")
CONFUSION_MATRIX_PATH = os.path.join(ROOT_DIR, "model", "checkpoints", "confusion_matrix.png")

BATCH_SIZE = 32


def main():
    if not os.path.isfile(SPLIT_PATH):
        print(f"No patient split found at '{SPLIT_PATH}' -- run train_full.py first (it creates this).")
        return

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model, checkpoint_loaded, class_names, _val_macro_f1 = load_model(CHECKPOINT_PATH, device)
    if not checkpoint_loaded:
        print(f"No checkpoint found at '{CHECKPOINT_PATH}' -- run train_full.py first.")
        return

    # Must match model/inference.py's preprocessing exactly -- this evaluates
    # whatever CHECKPOINT_PATH actually was trained on. See the note in
    # train_full.py's build_dataloaders() re: OCT-specific preprocessing.
    eval_transform = transforms.Compose(
        [
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
        ]
    )

    with open(SPLIT_PATH, "r", encoding="utf-8") as f:
        split = json.load(f)
    test_patients = set(split["test"])

    all_samples = collect_samples(TRAIN_DIR, VAL_DIR, TEST_DIR)
    test_samples = filter_by_patients(all_samples, test_patients)
    test_ds = OCTDataset(test_samples, class_names, eval_transform)
    test_loader = DataLoader(
        test_ds, batch_size=BATCH_SIZE, shuffle=False, num_workers=2, worker_init_fn=limit_worker_cv2_threads
    )

    print(f"Evaluating on {len(test_ds)} patient-disjoint held-out test images, classes: {class_names}")

    all_preds, all_labels = [], []
    with torch.no_grad():
        for images, labels in test_loader:
            images = images.to(device)
            outputs = model(images)
            all_preds.extend(outputs.argmax(1).cpu().tolist())
            all_labels.extend(labels.tolist())

    report = classification_report(all_labels, all_preds, target_names=class_names, digits=4)
    print(report)

    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(
            f"Test set: {len(test_ds)} images from {len(test_patients)} patients, "
            f"reserved from pooled train+val+test before any training (patient_split.json)\n"
        )
        f.write(f"Checkpoint: {CHECKPOINT_PATH}\n\n")
        f.write(report)
    print(f"Report saved to {REPORT_PATH}")

    cm = confusion_matrix(all_labels, all_preds)
    disp = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=class_names)
    fig, ax = plt.subplots(figsize=(6, 6))
    disp.plot(ax=ax, cmap="Blues", colorbar=False)
    plt.title("Visioret -- Confusion Matrix (held-out test set)")
    plt.tight_layout()
    plt.savefig(CONFUSION_MATRIX_PATH, dpi=150)
    print(f"Confusion matrix saved to {CONFUSION_MATRIX_PATH}")


if __name__ == "__main__":
    main()
