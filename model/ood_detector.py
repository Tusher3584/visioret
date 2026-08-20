"""Out-of-distribution (OOD) detection: "does this image actually look like
an OCT B-scan?" -- a gate that runs before the 4-class disease model.

Without this, the disease classifier has no notion of "I don't know": fed a
photo of a person, it will still confidently pick one of CNV/DME/DRUSEN/
NORMAL. Two stages, cheapest first:

1. Grayscale heuristic: real OCT B-scans are near-grayscale (R=G=B per
   pixel). A color photo fails this immediately, before any model runs.
2. Feature-space distance: extract the trained disease model's own
   penultimate-layer features (reusing the model already loaded for
   prediction -- no extra network) and measure how far the image sits from
   the centroid of real OCT training images in that feature space. This is
   a standard OOD technique (distance-based detection in a pretrained
   feature space) and needs no negative/non-OCT training data at all --
   only statistics computed from OCT images we already have.
"""

import os

import numpy as np
import torch
from PIL import Image

OOD_STATS_PATH_DEFAULT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "checkpoints", "ood_stats.pth")

GRAYSCALE_CHANNEL_DIFF_THRESHOLD = 12.0  # mean |R-G|+|G-B|+|R-B| per pixel, 0-255 scale


def is_grayscale_heuristic(image: Image.Image, threshold: float = GRAYSCALE_CHANNEL_DIFF_THRESHOLD) -> bool:
    """True if the image's channels are close enough to be a real (or
    near-)grayscale OCT scan. A full-color photo fails this."""
    rgb = np.asarray(image.convert("RGB"), dtype=np.float32)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    channel_diff = np.abs(r - g) + np.abs(g - b) + np.abs(r - b)
    return float(channel_diff.mean()) <= threshold


def mean_brightness(image: Image.Image) -> float:
    """OCT B-scans are dominated by black background around the tissue
    band, so their overall mean brightness is characteristically low --
    unlike most grayscale photos of real-world scenes/people. Catches
    grayscale non-OCT images that pass the color heuristic above."""
    return float(np.asarray(image.convert("L"), dtype=np.float32).mean())


def is_dark_enough_heuristic(image: Image.Image, threshold: float) -> bool:
    return mean_brightness(image) <= threshold


class _FeatureHook:
    """Captures the flattened output of model.avgpool (the 2048-dim feature
    vector ResNet50 normally feeds into its final fc layer)."""

    def __init__(self, model):
        self.features = None
        self.handle = model.avgpool.register_forward_hook(self._save)

    def _save(self, module, inputs, output):
        self.features = torch.flatten(output, 1).detach()

    def remove(self):
        self.handle.remove()


@torch.no_grad()
def extract_features(model, image_tensor, device) -> np.ndarray:
    hook = _FeatureHook(model)
    model(image_tensor.to(device))
    features = hook.features[0].cpu().numpy()
    hook.remove()
    return features


def compute_ood_stats(model, images, image_tensors, device) -> dict:
    """Computes the OCT-training-set feature centroid/std (for the
    feature-distance stage) and the brightness distribution (for the
    dark-background heuristic), both calibrated from real OCT images."""
    all_features = np.stack([extract_features(model, t, device) for t in image_tensors])
    centroid = all_features.mean(axis=0)
    std = all_features.std(axis=0) + 1e-6  # avoid div-by-zero on dead dims

    distances = np.sqrt(((all_features - centroid) / std) ** 2).mean(axis=1)
    distance_threshold = float(np.percentile(distances, 99))

    brightness_values = np.array([mean_brightness(img) for img in images])
    # 99th percentile of real OCT brightness -- reject anything brighter
    # than almost every real OCT scan we've seen.
    brightness_threshold = float(np.percentile(brightness_values, 99))

    return {
        "centroid": centroid,
        "std": std,
        "threshold": distance_threshold,
        "brightness_threshold": brightness_threshold,
        "n_samples": len(image_tensors),
        "calibration_distances_p50_p90_p99": [
            float(np.percentile(distances, 50)),
            float(np.percentile(distances, 90)),
            float(np.percentile(distances, 99)),
        ],
        "calibration_brightness_p50_p90_p99": [
            float(np.percentile(brightness_values, 50)),
            float(np.percentile(brightness_values, 90)),
            float(np.percentile(brightness_values, 99)),
        ],
    }


def save_ood_stats(stats: dict, path: str = OOD_STATS_PATH_DEFAULT):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    torch.save(stats, path)


def load_ood_stats(path: str = OOD_STATS_PATH_DEFAULT):
    if not os.path.isfile(path):
        return None
    # weights_only=False: this file is our own locally-generated stats dict
    # (numpy arrays + floats), not a checkpoint from an untrusted source.
    return torch.load(path, map_location="cpu", weights_only=False)


def ood_distance(features: np.ndarray, stats: dict) -> float:
    """Normalized distance from the OCT training centroid -- larger means
    less OCT-like."""
    return float(np.sqrt((((features - stats["centroid"]) / stats["std"]) ** 2)).mean())


def check_is_oct(image: Image.Image, image_tensor, model, device, ood_stats: dict | None):
    """Runs all three stages, cheapest first. Returns (is_oct: bool, reason: str, detail: dict)."""
    if not is_grayscale_heuristic(image):
        return False, "not_grayscale", {"stage": "color_heuristic"}

    if ood_stats is None:
        # Stats not computed yet -- degrade gracefully rather than block the app.
        return True, "ood_stats_unavailable", {"stage": "skipped"}

    if not is_dark_enough_heuristic(image, ood_stats["brightness_threshold"]):
        return False, "too_bright_for_oct", {
            "stage": "brightness_heuristic",
            "brightness": mean_brightness(image),
            "threshold": ood_stats["brightness_threshold"],
        }

    features = extract_features(model, image_tensor, device)
    distance = ood_distance(features, ood_stats)
    is_oct = distance <= ood_stats["threshold"]
    return is_oct, ("within_distribution" if is_oct else "feature_distance_too_high"), {
        "stage": "feature_distance",
        "distance": distance,
        "threshold": ood_stats["threshold"],
    }
