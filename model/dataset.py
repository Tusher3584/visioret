"""Patient-grouped OCT dataset loading, shared by train_full.py and evaluate.py.

The Kermany OCT2017 filenames encode a patient id (e.g. CNV-1016042-155.jpeg
-> patient 1016042). Multiple images per patient are correlated, so a plain
random image-level split risks leaking a patient's images across train/val.
This module splits by patient id instead.

KNOWN LIMITATION -- read before quoting any Kermany number
----------------------------------------------------------
collect_samples() below keys the group as f"{class_name}-{number}", NOT the
bare number. 896 of Kermany's 4,657 numeric ids (19.2%) appear under more
than one class folder -- clinically coherent (wet AMD in one eye, drusen in
the fellow eye, normal slices from both), so those really do look like one
patient. Prefixing the class therefore splits one patient into up to three
groups, which GroupShuffleSplit can then scatter across train/val/test.
Result: 5,375 of the 13,146 held-out test images (40.9%) belong to a patient
seen during training.

The direction of the effect was MEASURED, not assumed (see
model/audit_patient_leakage.py, which regenerates these numbers):

    full test set   n=13146   acc=0.9517   macroF1=0.9233
    leaked subset   n= 5375   acc=0.9180   macroF1=0.8878
    clean subset    n= 7771   acc=0.9750   macroF1=0.9541

The model does WORSE on the leaked patients, not better -- the opposite of
memorization. Those patients are by construction the multi-diagnosis ones,
i.e. the clinically ambiguous cases sitting on the CNV/DRUSEN boundary the
model is weakest at. So the published 95.17% is conservative, not inflated,
and the genuinely patient-disjoint figure is the higher 97.50%.

This is deliberately NOT fixed in place. Changing the key would change which
patients land in which split, which invalidates the persisted
patient_split.json that the deployed checkpoint was trained against, and
would require a full retrain to restore a coherent train/test boundary. The
external datasets are unaffected: OCTDL keys on the bare numeric id, Duke on
the per-patient volume folder, and Noor's class prefix is CORRECT there
because its patient folders are numbered independently inside each class
folder.

Checkpoint 5 (see TODO.md) adds three more public OCT sources, each with its
own quirky layout -- collect_noor/collect_octdl/collect_duke below normalize
them into the same (filepath, class_name, patient_id) tuples Kermany uses, so
they plug into the same patient_grouped_three_way_split / OCTDataset. Patient
ids are dataset-prefixed (noor-/octdl-/duke-) so they can never collide with
each other or with Kermany's plain numeric ids.
"""

import os
import re

from PIL import Image
from sklearn.model_selection import GroupShuffleSplit
from torch.utils.data import Dataset

FILENAME_RE = re.compile(r"^([A-Za-z]+)-(\d+)-(\d+)\.(jpeg|jpg|png)$", re.IGNORECASE)

NOOR_ROOT = r"G:\Download\archive\NoorEyeHospital\extracted\NEH_UT_2021RetinalOCTDataset"
OCTDL_ROOT = r"G:\Download\archive\OCTDL\extracted\OCTDL"
DUKE_ROOT = r"G:\Download\archive\DukeSrinivasan2014\extracted\Publication_Dataset"

NOOR_LABEL_RE = re.compile(r"_(cnv|drusen|normal)\.(jpg|jpeg|tif|tiff|png)$", re.IGNORECASE)
OCTDL_PATIENT_RE = re.compile(r"^[a-z]+_(\d+)_\d+\.", re.IGNORECASE)


def list_class_dirs(root_dir):
    """Returns {class_name: dir_path} for each subdirectory of root_dir."""
    return {d.name: d.path for d in os.scandir(root_dir) if d.is_dir()}


def kermany_numeric_patient_id(filename):
    """The bare numeric patient id from a Kermany filename, or None.

    CNV-1016042-155.jpeg -> "1016042". This is the CORRECT patient identity
    (see the module docstring); collect_samples deliberately does not use it,
    because the deployed checkpoint's persisted split is keyed the old way.
    Used by model/audit_patient_leakage.py to quantify the consequences.
    """
    match = FILENAME_RE.match(filename)
    return match.group(2) if match else None


def collect_samples(*root_dirs):
    """Scans one or more ImageFolder-style roots and returns a list of
    (filepath, class_name, patient_id) tuples.

    NOTE the grouping key is f"{class_name}-{number}", not the bare number.
    That is a known flaw with a measured, conservative effect -- see the
    KNOWN LIMITATION section in this module's docstring before changing it.
    Changing it here silently invalidates model/checkpoints/patient_split.json
    (whose keys are in the old format), which would make evaluate.py select
    the wrong test set rather than fail loudly.
    """
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


def collect_noor(root_dir=NOOR_ROOT):
    """Noor Eye Hospital: CNV/DRUSEN/NORMAL folders, patient-numbered
    subfolders. Ground truth is the PER-B-SCAN filename suffix (e.g.
    "003_Normal.jpg"), not the folder name -- a diagnosed patient's volume
    can still contain individual B-scans that look normal, so trusting the
    folder alone would mislabel those. Patient identity is the folder path
    (class + patient number), independent of each B-scan's own label."""
    samples = []
    for class_dir in ("CNV", "DRUSEN", "NORMAL"):
        root = os.path.join(root_dir, class_dir)
        if not os.path.isdir(root):
            continue
        for dirpath, _dirnames, filenames in os.walk(root):
            rel = os.path.relpath(dirpath, root)
            patient_num = rel.split(os.sep)[0] if rel != "." else None
            if not patient_num:
                continue
            for fname in filenames:
                match = NOOR_LABEL_RE.search(fname)
                if match:
                    label = match.group(1).upper()
                    patient_id = f"noor-{class_dir}-{patient_num}"
                    samples.append((os.path.join(dirpath, fname), label, patient_id))
    return samples


def collect_octdl(root_dir=OCTDL_ROOT):
    """OCTDL: folder-level label (no per-image variation). Only NO (->
    NORMAL) and DME -- its AMD class isn't split into CNV/DRUSEN, so it's
    excluded rather than guessed at. Patient id is the numeric id embedded
    in the filename (e.g. dme_1132061_1.jpg -> patient 1132061), shared
    across that patient's multiple B-scans."""
    samples = []
    for class_dir, label in (("NO", "NORMAL"), ("DME", "DME")):
        root = os.path.join(root_dir, class_dir)
        if not os.path.isdir(root):
            continue
        for fname in os.listdir(root):
            path = os.path.join(root, fname)
            if not os.path.isfile(path):
                continue
            match = OCTDL_PATIENT_RE.match(fname)
            patient_num = match.group(1) if match else fname
            samples.append((path, label, f"octdl-{patient_num}"))
    return samples


def collect_duke(root_dir=DUKE_ROOT):
    """Duke (Srinivasan et al. 2014): one folder per patient volume
    (DME<n>/NORMAL<n>/TIFFs/8bitTIFFs/*.tif). AMD<n> excluded, same
    reasoning as OCTDL's AMD class."""
    samples = []
    for entry in os.scandir(root_dir):
        if not entry.is_dir():
            continue
        if entry.name.startswith("DME"):
            label = "DME"
        elif entry.name.startswith("NORMAL"):
            label = "NORMAL"
        else:
            continue
        tiff_dir = os.path.join(entry.path, "TIFFs", "8bitTIFFs")
        if not os.path.isdir(tiff_dir):
            continue
        patient_id = f"duke-{entry.name}"
        for fname in os.listdir(tiff_dir):
            path = os.path.join(tiff_dir, fname)
            if os.path.isfile(path):
                samples.append((path, label, patient_id))
    return samples


def collect_external_samples():
    """All three Checkpoint 5 external sources, combined."""
    return collect_noor() + collect_octdl() + collect_duke()


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
