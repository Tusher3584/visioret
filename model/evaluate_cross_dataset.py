"""Cross-dataset generalization check (Checkpoint 5).

Two distinct modes, controlled by whether the deployed checkpoint was
fine-tuned on the external data (model/dataset.py's collect_external_samples
sources are now folded into training -- see train_full.py):

  - Before fine-tuning: evaluates against ALL external images (nothing was
    held out, since none of it had been seen).
  - After fine-tuning: most external images are now in the training set, so
    evaluating against all of them would leak train data into a
    "generalization" number. This script filters down to just the RESERVED
    external test patients (model/checkpoints/external_patient_split.json,
    written by train_full.py) so this stays a genuine held-out check.

Sources: Noor Eye Hospital (Tehran, Iran; CNV/DRUSEN/NORMAL, all classes,
ground truth is the per-B-scan filename label not the folder name -- see
model/dataset.py), OCTDL (NORMAL+DME only, different scanner vendor --
Optovue vs Kermany's Heidelberg Spectralis), Duke Srinivasan 2014
(NORMAL+DME only, different institution/population). All three exclude
their "AMD" class since it isn't split into CNV vs DRUSEN and mapping it
would require a clinician's relabeling, not a guess.

Usage:
    python -m model.evaluate_cross_dataset
"""

import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import torch
from PIL import Image
from sklearn.metrics import ConfusionMatrixDisplay, classification_report, confusion_matrix

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from model.dataset import collect_external_samples, filter_by_patients  # noqa: E402
from model.inference import load_model, predict, preprocess_image  # noqa: E402

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHECKPOINT_PATH = os.path.join(ROOT_DIR, "model", "checkpoints", "resnet50_oct.pth")
EXTERNAL_SPLIT_PATH = os.path.join(ROOT_DIR, "model", "checkpoints", "external_patient_split.json")
OUT_DIR = os.path.join(ROOT_DIR, "model", "checkpoints")


def collect_test_only_samples():
    """{source_name: [(filepath, label), ...]} -- if a reserved external
    test split exists (i.e. this checkpoint was fine-tuned on the rest of
    the external data), filters down to just those held-out patients so
    this stays a genuine generalization check rather than leaking train
    data into the number. Otherwise (no fine-tune has happened yet) uses
    everything. Patient ids are dataset-prefixed (noor-/octdl-/duke-, see
    model/dataset.py), so the source is recovered from the id for
    per-dataset reporting."""
    all_samples = collect_external_samples()  # (filepath, class_name, patient_id)
    fine_tuned = os.path.isfile(EXTERNAL_SPLIT_PATH)
    if fine_tuned:
        with open(EXTERNAL_SPLIT_PATH, "r", encoding="utf-8") as f:
            split = json.load(f)
        test_patients = set(split["test"])
        all_samples = filter_by_patients(all_samples, test_patients)
        print(
            f"Using RESERVED external test split only: {len(all_samples)} images from "
            f"{len(test_patients)} patients -- the rest is now in training, see "
            "external_patient_split.json"
        )
    else:
        print(f"No {EXTERNAL_SPLIT_PATH} found -- using all external images (nothing held out yet).")

    by_source = {"Noor Eye Hospital (Tehran, Iran)": [], "OCTDL (NORMAL+DME only)": [], "Duke Srinivasan 2014 (NORMAL+DME only)": []}
    for path, label, patient_id in all_samples:
        if patient_id.startswith("noor-"):
            by_source["Noor Eye Hospital (Tehran, Iran)"].append((path, label))
        elif patient_id.startswith("octdl-"):
            by_source["OCTDL (NORMAL+DME only)"].append((path, label))
        elif patient_id.startswith("duke-"):
            by_source["Duke Srinivasan 2014 (NORMAL+DME only)"].append((path, label))
    return by_source, fine_tuned


def evaluate_dataset(name, samples, model, device, classes):
    if not samples:
        print(f"{name}: no samples found, skipping")
        return None, None

    all_labels, all_preds = [], []
    for i, (filepath, true_label) in enumerate(samples):
        try:
            image = Image.open(filepath).convert("RGB")
        except Exception as exc:
            print(f"  skipping unreadable file {filepath}: {exc}")
            continue
        tensor = preprocess_image(image)
        pred_class, _confidence, _probs = predict(model, tensor, device, class_names=classes)
        all_labels.append(true_label)
        all_preds.append(pred_class.upper())
        if (i + 1) % 2000 == 0:
            print(f"  {name}: {i + 1}/{len(samples)} done")

    present_labels = sorted(set(all_labels) | set(all_preds), key=lambda c: classes.index(c) if c in classes else 99)
    report = classification_report(all_labels, all_preds, labels=present_labels, zero_division=0)
    print(f"\n=== {name} ({len(all_labels)} images) ===")
    print(report)
    return report, (all_labels, all_preds, present_labels)


def main():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model, checkpoint_loaded, classes, _val_macro_f1 = load_model(CHECKPOINT_PATH, device)
    if not checkpoint_loaded:
        print(f"No checkpoint found at '{CHECKPOINT_PATH}'.")
        return
    classes = [c.upper() for c in classes]
    datasets, fine_tuned = collect_test_only_samples()
    mode_desc = "held-out external test split only (fine-tuned checkpoint)" if fine_tuned else "all external images (not yet fine-tuned)"
    print(f"Evaluating checkpoint against {mode_desc}, classes:", classes)

    lines = [f"Cross-dataset generalization check -- evaluating against {mode_desc}",
             f"Checkpoint: {CHECKPOINT_PATH}", ""]
    combined_labels, combined_preds = [], []
    all_present_labels = set()

    for name, samples in datasets.items():
        report, raw = evaluate_dataset(name, samples, model, device, classes)
        if report is None:
            continue
        lines.append(f"=== {name} ({len(samples)} images) ===")
        lines.append(report)
        lines.append("")
        labels, preds, present = raw
        combined_labels.extend(labels)
        combined_preds.extend(preds)
        all_present_labels.update(present)

    if combined_labels:
        present_labels = sorted(all_present_labels, key=lambda c: classes.index(c) if c in classes else 99)
        combined_report = classification_report(combined_labels, combined_preds, labels=present_labels, zero_division=0)
        print(f"\n=== COMBINED ({len(combined_labels)} images across all 3 external datasets) ===")
        print(combined_report)
        lines.append(f"=== COMBINED ({len(combined_labels)} images across all 3 external datasets) ===")
        lines.append(combined_report)

        cm = confusion_matrix(combined_labels, combined_preds, labels=present_labels)
        disp = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=present_labels)
        fig, ax = plt.subplots(figsize=(6, 6))
        disp.plot(ax=ax, cmap="Blues", colorbar=False)
        ax.set_title("Visioret -- Cross-dataset confusion matrix (external data)")
        fig.tight_layout()
        fig.savefig(os.path.join(OUT_DIR, "cross_dataset_confusion_matrix.png"), dpi=150)
        print(f"Confusion matrix saved to {os.path.join(OUT_DIR, 'cross_dataset_confusion_matrix.png')}")

    report_path = os.path.join(OUT_DIR, "cross_dataset_evaluation_report.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"\nReport saved to {report_path}")


if __name__ == "__main__":
    main()
