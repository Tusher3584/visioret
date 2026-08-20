"""Full training run on the complete OCT2017 dataset.

Unlike train_quick.py (head-only, 400-image demo fine-tune), this:
- pools official train+val+test (84,484 images) and re-splits by patient id
  into its own train/val/test (the official test/ split leaks ~85% of its
  patients into train -- verified -- so it can't be used as-is)
- persists that patient split once (model/checkpoints/patient_split.json) so
  the held-out test set never changes across reruns or --resume
- unfreezes layer3+layer4+fc (not just the head)
- uses class-weighted loss for the real (imbalanced) class distribution
- uses mixed precision, LR scheduling, and early stopping on val macro-F1
- the reserved test patients are never touched here (see evaluate.py)

Usage:
    python model/train_full.py                 # full run
    python model/train_full.py --smoke-test     # tiny run to sanity-check the code
"""

import argparse
import os
import sys
import time

import torch
import torch.nn as nn
from sklearn.metrics import accuracy_score, f1_score
from torch.utils.data import DataLoader
from torchvision import transforms

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from model.dataset import (  # noqa: E402
    OCTDataset,
    class_counts,
    collect_samples,
    filter_by_patients,
    list_class_dirs,
    patient_grouped_three_way_split,
    patient_ids_of,
)
from model.inference import IMAGENET_MEAN, IMAGENET_STD, build_model  # noqa: E402
from model.oct_preprocessing import limit_worker_cv2_threads, preprocess_oct  # noqa: E402

DATA_ROOT = r"G:\Download\archive\OCT2017"
TRAIN_DIR = os.path.join(DATA_ROOT, "train")
VAL_DIR = os.path.join(DATA_ROOT, "val")
TEST_DIR = os.path.join(DATA_ROOT, "test")
# NOTE: the official train/val/test folders are pooled and re-split by patient
# id below. The official split leaks ~85% of test-set patients into train
# (verified), so it cannot be trusted as a held-out set on its own.

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHECKPOINT_PATH = os.path.join(ROOT_DIR, "model", "checkpoints", "resnet50_oct.pth")
RESUME_STATE_PATH = os.path.join(ROOT_DIR, "model", "checkpoints", "train_full_resume_state.pth")
SPLIT_PATH = os.path.join(ROOT_DIR, "model", "checkpoints", "patient_split.json")
LOG_PATH = os.path.join(ROOT_DIR, "model", "checkpoints", "train_full.log")

MAX_EPOCHS = 30
EARLY_STOP_PATIENCE = 5
BATCH_SIZE = 32
LEARNING_RATE = 1e-4
WEIGHT_DECAY = 1e-4
VAL_FRACTION = 0.15
TEST_FRACTION = 0.15
UNFREEZE_PREFIXES = ("layer3.", "layer4.", "fc.")

RETRY_ATTEMPTS = 5
RETRY_DELAY_SECONDS = 5


def robust_torch_save(obj, path):
    """torch.save with retries -- on Windows, a freshly-written large file can
    be transiently locked (observed repeatedly, likely antivirus scanning),
    which otherwise crashes torch.save with 'File cannot be opened'."""
    last_exc = None
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            torch.save(obj, path)
            return
        except RuntimeError as exc:
            last_exc = exc
            time.sleep(RETRY_DELAY_SECONDS)
    raise last_exc


def get_or_create_patient_split(all_samples, log_file):
    """Loads the persisted train/val/test patient-id split if one exists,
    otherwise creates it once and saves it -- so the held-out test set never
    changes across reruns/resumes."""
    import json

    if os.path.isfile(SPLIT_PATH):
        with open(SPLIT_PATH, "r", encoding="utf-8") as f:
            split = json.load(f)
        log(f"Loaded existing patient split from {SPLIT_PATH}", log_file)
        return set(split["train"]), set(split["val"]), set(split["test"])

    train_samples, val_samples, test_samples = patient_grouped_three_way_split(
        all_samples, val_fraction=VAL_FRACTION, test_fraction=TEST_FRACTION
    )
    train_patients = patient_ids_of(train_samples)
    val_patients = patient_ids_of(val_samples)
    test_patients = patient_ids_of(test_samples)

    os.makedirs(os.path.dirname(SPLIT_PATH), exist_ok=True)
    with open(SPLIT_PATH, "w", encoding="utf-8") as f:
        json.dump(
            {"train": sorted(train_patients), "val": sorted(val_patients), "test": sorted(test_patients)}, f
        )
    log(f"Created new patient-grouped train/val/test split, saved to {SPLIT_PATH}", log_file)
    return train_patients, val_patients, test_patients


def log(message, log_file):
    print(message, flush=True)
    log_file.write(message + "\n")
    log_file.flush()


def _stratified_head(samples, class_names, per_class):
    """Takes up to `per_class` samples from each class -- used only by
    --smoke-test so the tiny run still exercises every class."""
    result = []
    for name in class_names:
        result.extend([s for s in samples if s[1] == name][:per_class])
    return result


def build_dataloaders(train_samples, val_samples, class_names, batch_size, smoke_test):
    train_transform = transforms.Compose(
        [
            transforms.Lambda(preprocess_oct),
            transforms.Resize((224, 224)),
            transforms.RandomHorizontalFlip(),
            transforms.RandomRotation(5),
            transforms.ColorJitter(brightness=0.1, contrast=0.1),
            transforms.ToTensor(),
            transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
        ]
    )
    eval_transform = transforms.Compose(
        [
            transforms.Lambda(preprocess_oct),
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
        ]
    )

    if smoke_test:
        train_samples = _stratified_head(train_samples, class_names, per_class=16)
        val_samples = _stratified_head(val_samples, class_names, per_class=8)

    train_ds = OCTDataset(train_samples, class_names, train_transform)
    val_ds = OCTDataset(val_samples, class_names, eval_transform)

    train_loader = DataLoader(
        train_ds, batch_size=batch_size, shuffle=True, num_workers=4, pin_memory=True,
        persistent_workers=True, worker_init_fn=limit_worker_cv2_threads,
    )
    val_loader = DataLoader(
        val_ds, batch_size=batch_size, shuffle=False, num_workers=2, pin_memory=True,
        persistent_workers=True, worker_init_fn=limit_worker_cv2_threads,
    )

    train_counts = class_counts(train_samples, class_names)
    return train_loader, val_loader, train_counts, len(train_samples), len(val_samples)


def compute_class_weights(train_counts, class_names, device):
    total = sum(train_counts.values())
    num_classes = len(class_names)
    weights = [total / (num_classes * max(train_counts[name], 1)) for name in class_names]
    return torch.tensor(weights, dtype=torch.float32, device=device)


def set_trainable_layers(model):
    for name, param in model.named_parameters():
        param.requires_grad = name.startswith(UNFREEZE_PREFIXES)


@torch.no_grad()
def run_validation(model, loader, criterion, device):
    model.eval()
    total_loss, all_preds, all_labels = 0.0, [], []
    for images, labels in loader:
        images, labels = images.to(device), labels.to(device)
        outputs = model(images)
        loss = criterion(outputs, labels)
        total_loss += loss.item() * images.size(0)
        all_preds.extend(outputs.argmax(1).cpu().tolist())
        all_labels.extend(labels.cpu().tolist())
    avg_loss = total_loss / max(len(all_labels), 1)
    acc = accuracy_score(all_labels, all_preds) if all_labels else 0.0
    macro_f1 = f1_score(all_labels, all_preds, average="macro", zero_division=0) if all_labels else 0.0
    return avg_loss, acc, macro_f1


def save_resume_state(path, epoch, model, optimizer, scheduler, scaler, best_macro_f1, epochs_without_improvement, class_names):
    robust_torch_save(
        {
            "epoch": epoch,
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
            "scheduler_state_dict": scheduler.state_dict(),
            "scaler_state_dict": scaler.state_dict(),
            "best_macro_f1": best_macro_f1,
            "epochs_without_improvement": epochs_without_improvement,
            "classes": class_names,
        },
        path,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke-test", action="store_true", help="Tiny run (1 epoch, ~64 train images) to check the code works before committing to a full run.")
    parser.add_argument("--resume", action="store_true", help=f"Resume from {RESUME_STATE_PATH} (full optimizer/scheduler/epoch state) if it exists.")
    args = parser.parse_args()

    if not os.path.isdir(TRAIN_DIR):
        print(f"Dataset not found at '{TRAIN_DIR}'. Check DATA_ROOT in this script.")
        return

    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as log_file:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        log(f"\n=== Run started {time.strftime('%Y-%m-%d %H:%M:%S')} (smoke_test={args.smoke_test}) ===", log_file)
        log(f"Using device: {device}", log_file)

        class_names = sorted(list_class_dirs(TRAIN_DIR).keys())
        log(f"Classes detected from folder names: {class_names}", log_file)

        all_samples = collect_samples(TRAIN_DIR, VAL_DIR, TEST_DIR)
        train_patients, val_patients, test_patients = get_or_create_patient_split(all_samples, log_file)
        train_samples = filter_by_patients(all_samples, train_patients)
        val_samples = filter_by_patients(all_samples, val_patients)
        log(
            f"Patient split -> train: {len(train_patients)} patients / val: {len(val_patients)} patients / "
            f"test: {len(test_patients)} patients (test reserved, untouched during training)",
            log_file,
        )

        train_loader, val_loader, train_counts, n_train, n_val = build_dataloaders(
            train_samples, val_samples, class_names, BATCH_SIZE, args.smoke_test
        )
        log(f"Train samples: {n_train} | Val samples: {n_val}", log_file)
        log(f"Train class counts: {train_counts}", log_file)

        model = build_model(num_classes=len(class_names))
        model.to(device)
        set_trainable_layers(model)
        trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
        total = sum(p.numel() for p in model.parameters())
        log(f"Trainable params: {trainable:,} / {total:,} (unfrozen: {UNFREEZE_PREFIXES})", log_file)

        class_weights = compute_class_weights(train_counts, class_names, device)
        criterion = nn.CrossEntropyLoss(weight=class_weights)
        optimizer = torch.optim.Adam(
            filter(lambda p: p.requires_grad, model.parameters()), lr=LEARNING_RATE, weight_decay=WEIGHT_DECAY
        )
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode="max", factor=0.5, patience=2)

        use_amp = device.type == "cuda"
        scaler = torch.amp.GradScaler("cuda", enabled=use_amp)

        start_epoch = 0
        best_macro_f1 = -1.0
        epochs_without_improvement = 0

        if args.resume and os.path.isfile(RESUME_STATE_PATH):
            state = torch.load(RESUME_STATE_PATH, map_location=device)
            model.load_state_dict(state["model_state_dict"])
            optimizer.load_state_dict(state["optimizer_state_dict"])
            scheduler.load_state_dict(state["scheduler_state_dict"])
            scaler.load_state_dict(state["scaler_state_dict"])
            best_macro_f1 = state["best_macro_f1"]
            epochs_without_improvement = state["epochs_without_improvement"]
            start_epoch = state["epoch"] + 1
            log(
                f"Resumed from {RESUME_STATE_PATH}: starting at epoch {start_epoch + 1}, "
                f"best_macro_f1={best_macro_f1:.4f}, epochs_without_improvement={epochs_without_improvement}",
                log_file,
            )
        elif os.path.isfile(CHECKPOINT_PATH):
            checkpoint = torch.load(CHECKPOINT_PATH, map_location=device)
            if isinstance(checkpoint, dict) and "model_state_dict" in checkpoint and checkpoint.get("classes") == class_names:
                model.load_state_dict(checkpoint["model_state_dict"])
                best_macro_f1 = checkpoint.get("val_macro_f1", -1.0)
                log(
                    f"Warm-starting from existing checkpoint {CHECKPOINT_PATH} "
                    f"(prior val_macro_f1={best_macro_f1:.4f}); optimizer/scheduler start fresh.",
                    log_file,
                )

        max_epochs = 1 if args.smoke_test else MAX_EPOCHS

        for epoch in range(start_epoch, max_epochs):
            model.train()
            epoch_start = time.time()
            running_loss, correct, total_seen = 0.0, 0, 0

            for images, labels in train_loader:
                images, labels = images.to(device), labels.to(device)
                optimizer.zero_grad()

                with torch.amp.autocast("cuda", enabled=use_amp):
                    outputs = model(images)
                    loss = criterion(outputs, labels)

                scaler.scale(loss).backward()
                scaler.step(optimizer)
                scaler.update()

                running_loss += loss.item() * images.size(0)
                correct += (outputs.argmax(1) == labels).sum().item()
                total_seen += images.size(0)

            train_loss = running_loss / max(total_seen, 1)
            train_acc = correct / max(total_seen, 1)
            val_loss, val_acc, val_macro_f1 = run_validation(model, val_loader, criterion, device)
            scheduler.step(val_macro_f1)
            epoch_time = time.time() - epoch_start

            log(
                f"Epoch {epoch + 1}/{max_epochs} ({epoch_time:.0f}s) - "
                f"train_loss: {train_loss:.4f} train_acc: {train_acc:.4f} - "
                f"val_loss: {val_loss:.4f} val_acc: {val_acc:.4f} val_macro_f1: {val_macro_f1:.4f} - "
                f"lr: {optimizer.param_groups[0]['lr']:.2e}",
                log_file,
            )

            if val_macro_f1 > best_macro_f1:
                best_macro_f1 = val_macro_f1
                epochs_without_improvement = 0
                os.makedirs(os.path.dirname(CHECKPOINT_PATH), exist_ok=True)
                robust_torch_save(
                    {"model_state_dict": model.state_dict(), "classes": class_names, "val_macro_f1": best_macro_f1},
                    CHECKPOINT_PATH,
                )
                log(f"  -> new best val_macro_f1={best_macro_f1:.4f}, checkpoint saved", log_file)
            else:
                epochs_without_improvement += 1

            if not args.smoke_test:
                save_resume_state(
                    RESUME_STATE_PATH, epoch, model, optimizer, scheduler, scaler,
                    best_macro_f1, epochs_without_improvement, class_names,
                )

            if epochs_without_improvement >= EARLY_STOP_PATIENCE and not args.smoke_test:
                log(f"No improvement for {EARLY_STOP_PATIENCE} epochs, stopping early.", log_file)
                break

        log(f"=== Run finished. Best val_macro_f1: {best_macro_f1:.4f} ===", log_file)


if __name__ == "__main__":
    main()
