"""Patient-grouped OCT2017 dataset loading, shared by train_full.py and evaluate.py.

The Kermany OCT2017 filenames encode a patient id (e.g. CNV-1016042-155.jpeg
-> patient 1016042). Multiple images per patient are correlated, so a plain
random image-level split risks leaking a patient's images across train/val.
This module splits by patient id instead.
"""

import os
import re

from PIL import Image
from sklearn.model_selection import GroupShuffleSplit
from torch.utils.data import Dataset

FILENAME_RE = re.compile(r"^([A-Za-z]+)-(\d+)-(\d+)\.(jpeg|jpg|png)$", re.IGNORECASE)


def list_class_dirs(root_dir):
    """Returns {class_name: dir_path} for each subdirectory of root_dir."""
    return {d.name: d.path for d in os.scandir(root_dir) if d.is_dir()}


def collect_samples(*root_dirs):
    """Scans one or more ImageFolder-style roots and returns a list of
    (filepath, class_name, patient_id) tuples."""
    samples = []
    for root_dir in root_dirs:
        if not os.path.isdir(root_dir):
            continue
        for class_name, class_dir in sorted(list_class_dirs(root_dir).items()):
            for entry in os.scandir(class_dir):
                match = FILENAME_RE.match(entry.name)
                patient_id = f"{class_name}-{match.group(2)}" if match else entry.name
                samples.append((entry.path, class_name, patient_id))
    return samples


def patient_grouped_split(samples, val_fraction=0.15, random_state=42):
    """Splits (filepath, class_name, patient_id) samples into train/val so
    that no patient appears in both splits."""
    groups = [s[2] for s in samples]
    splitter = GroupShuffleSplit(n_splits=1, test_size=val_fraction, random_state=random_state)
    train_idx, val_idx = next(splitter.split(samples, groups=groups))
    train_samples = [samples[i] for i in train_idx]
    val_samples = [samples[i] for i in val_idx]
    return train_samples, val_samples


def patient_grouped_three_way_split(samples, val_fraction=0.15, test_fraction=0.15, random_state=42):
    """Splits into train/val/test by patient id so no patient appears in more
    than one split. Returns (train_samples, val_samples, test_samples)."""
    groups = [s[2] for s in samples]
    test_splitter = GroupShuffleSplit(n_splits=1, test_size=test_fraction, random_state=random_state)
    remainder_idx, test_idx = next(test_splitter.split(samples, groups=groups))

    remainder = [samples[i] for i in remainder_idx]
    test_samples = [samples[i] for i in test_idx]

    remainder_val_fraction = val_fraction / (1 - test_fraction)
    remainder_groups = [s[2] for s in remainder]
    val_splitter = GroupShuffleSplit(n_splits=1, test_size=remainder_val_fraction, random_state=random_state)
    train_idx, val_idx = next(val_splitter.split(remainder, groups=remainder_groups))

    train_samples = [remainder[i] for i in train_idx]
    val_samples = [remainder[i] for i in val_idx]
    return train_samples, val_samples, test_samples


def patient_ids_of(samples):
    return set(s[2] for s in samples)


def filter_by_patients(samples, patient_ids):
    return [s for s in samples if s[2] in patient_ids]


class OCTDataset(Dataset):
    """(filepath, class_name, patient_id) samples -> (tensor, label_index)."""

    def __init__(self, samples, class_names, transform):
        self.samples = samples
        self.class_to_idx = {name: i for i, name in enumerate(class_names)}
        self.transform = transform

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        filepath, class_name, _patient_id = self.samples[idx]
        image = Image.open(filepath).convert("RGB")
        tensor = self.transform(image)
        return tensor, self.class_to_idx[class_name]


def class_counts(samples, class_names):
    counts = {name: 0 for name in class_names}
    for _filepath, class_name, _patient_id in samples:
        counts[class_name] += 1
    return counts
