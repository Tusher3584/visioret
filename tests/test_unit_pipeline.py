"""Unit tests for the model-side pipeline pieces that need no trained weights:
preprocessing, the overlay geometry, the grayscale OOD stage, the written
explanation, and model-version fingerprinting."""

import numpy as np
import torch
from PIL import Image

from backend.db.model_version import checkpoint_fingerprint
from model.explanations import CLINICAL_EXPLANATIONS, build_explanation, describe_heatmap_location
from model.inference import CLASS_NAMES, overlay_gradcam, preprocess_image
from model.ood_detector import is_grayscale_heuristic


# --- preprocessing ---------------------------------------------------------

def test_preprocess_produces_model_input_shape():
    t = preprocess_image(Image.new("RGB", (768, 496), (40, 40, 40)))
    assert t.shape == (1, 3, 224, 224)
    assert t.dtype == torch.float32


def test_preprocess_accepts_grayscale_and_rgba():
    # Regression: a 1-channel grayscale JPEG once failed at Normalize.
    for mode in ("L", "RGBA", "P"):
        assert preprocess_image(Image.new(mode, (300, 200))).shape == (1, 3, 224, 224)


def test_preprocess_applies_imagenet_normalisation():
    # A mid-gray pixel (128) is (0.502 - mean) / std per channel, not 0.502.
    t = preprocess_image(Image.new("RGB", (224, 224), (128, 128, 128)))
    expected_red = (128 / 255 - 0.485) / 0.229
    assert abs(float(t[0, 0, 100, 100]) - expected_red) < 1e-3


# --- overlay geometry ------------------------------------------------------

def test_overlay_keeps_the_original_image_size():
    # Regression (R2-3): the original was once squashed to 224x224, so a
    # 768x496 scan's overlay no longer lined up with the scan beside it.
    original = Image.new("L", (768, 496), 60)
    heatmap = np.random.rand(7, 7).astype(np.float32)
    overlay = overlay_gradcam(original, heatmap)
    assert overlay.size == (768, 496)


# --- grayscale OOD stage ---------------------------------------------------

def test_grayscale_image_passes_colour_stage():
    assert is_grayscale_heuristic(Image.new("RGB", (100, 100), (90, 90, 90)))


def test_colour_image_fails_colour_stage():
    assert not is_grayscale_heuristic(Image.new("RGB", (100, 100), (200, 40, 40)))


# --- explanations ----------------------------------------------------------

def _heatmap_with_blob(col_start, col_end, size=100):
    h = np.zeros((size, size), dtype=np.float32)
    h[40:60, col_start:col_end] = 1.0
    return h


def test_location_left_centre_right():
    assert "left side" in describe_heatmap_location(_heatmap_with_blob(5, 15))
    assert "central region" in describe_heatmap_location(_heatmap_with_blob(45, 55))
    assert "right side" in describe_heatmap_location(_heatmap_with_blob(85, 95))


def test_location_spread_wording():
    tight = describe_heatmap_location(_heatmap_with_blob(45, 55))  # 2% of the area
    broad = np.ones((100, 100), dtype=np.float32)
    assert "tightly concentrated" in tight
    assert "broader area" in describe_heatmap_location(broad)


def test_all_zero_heatmap_is_reported_as_diffuse_not_located():
    assert "too diffuse" in describe_heatmap_location(np.zeros((50, 50), dtype=np.float32))


def test_every_class_has_a_clinical_explanation():
    heatmap = _heatmap_with_blob(45, 55)
    for cls in CLASS_NAMES:
        assert CLINICAL_EXPLANATIONS.get(cls), cls
        text = build_explanation(cls, heatmap)
        assert text.startswith(CLINICAL_EXPLANATIONS[cls])


def test_explanation_never_claims_a_retinal_layer():
    # The design rule: no segmentation exists, so no layer may be named in the
    # DYNAMIC (geometry) sentence.
    sentence = describe_heatmap_location(_heatmap_with_blob(45, 55)).lower()
    for layer in ("rpe", "ellipsoid", "bruch", "nerve fiber", "photoreceptor", "choroid"):
        assert layer not in sentence


# --- model-version fingerprint ---------------------------------------------

def test_fingerprint_is_content_based(tmp_path):
    a, b, c = tmp_path / "a.pth", tmp_path / "b.pth", tmp_path / "c.pth"
    a.write_bytes(b"same weights")
    b.write_bytes(b"same weights")
    c.write_bytes(b"different weights")
    assert checkpoint_fingerprint(str(a)) == checkpoint_fingerprint(str(b))  # copy/clone: same version
    assert checkpoint_fingerprint(str(a)) != checkpoint_fingerprint(str(c))  # retrain: new version


def test_fingerprint_missing_file_is_none(tmp_path):
    assert checkpoint_fingerprint(str(tmp_path / "nope.pth")) is None
