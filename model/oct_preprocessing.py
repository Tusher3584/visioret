"""OCT-domain-specific preprocessing: speckle-noise reduction, B-scan
flattening, and retinal region cropping.

This is what makes the pipeline actually specific to OCT B-scans, rather
than generic resize+normalize that would work identically for any imaging
modality. None of these three steps make sense applied to, say, a chest
X-ray or a skin lesion photo -- they specifically address how OCT scans are
formed (coherent-light interferometry speckle) and how the eye is shaped
(curved retina, tilt-dependent scan geometry).

Order: strip border artifact -> downscale -> denoise -> flatten -> crop.
Border-stripping first so artifact pixels can't get smeared into the image
during flattening; downscaling before the expensive steps since the model
input is 224x224 regardless (~3x speedup, no quality lost); denoising
before curve detection makes it more robust; cropping last is trivial once
the tissue band is flattened into a consistent horizontal strip.
"""

import cv2
import numpy as np
from PIL import Image


def limit_worker_cv2_threads(_worker_id=None):
    """DataLoader worker_init_fn (or call directly in a single-process
    context). OpenCV defaults to using all available cores *per call*
    (e.g. inside the denoising/morphology steps below). With
    num_workers>1, each worker process independently trying to do that
    causes severe CPU oversubscription -- observed in practice: 4 worker
    processes each burning 100+ minutes of CPU time without finishing a
    single training epoch, on a machine with 16 logical cores. Restricting
    each worker process to 1 OpenCV thread gives clean parallelism across
    worker *processes* instead of contention between threads within them.
    Any DataLoader that uses preprocess_oct with num_workers > 0 should
    pass this as worker_init_fn.
    """
    cv2.setNumThreads(1)


def reduce_speckle_noise(gray: np.ndarray) -> np.ndarray:
    """Non-local means denoising -- targets OCT's characteristic speckle
    noise (from coherent-light interferometry) while preserving retinal
    layer edges better than a simple blur would."""
    return cv2.fastNlMeansDenoising(gray, h=10, templateWindowSize=7, searchWindowSize=21)


def _find_border_artifact_depth(gray: np.ndarray, max_check_rows: int = 20) -> int:
    """Some source images have a few rows of uniform white/black border at
    the very top (a saving/cropping artifact, not tissue) -- real retinal
    tissue has high row-to-row texture variance, a uniform border has
    near-zero variance. Returns how many leading rows to skip."""
    h = gray.shape[0]
    for row in range(min(max_check_rows, h)):
        if float(gray[row].std()) > 5.0:
            return row
    return 0


def _largest_connected_component(mask: np.ndarray) -> np.ndarray:
    """Keeps only the single largest connected white region in a binary
    mask, discarding smaller disconnected islands. On low-contrast scans,
    a global Otsu threshold can fragment into scattered noise specks plus
    the real tissue band; without this, boundary detection can jump between
    unrelated islands from one column to the next."""
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if num_labels <= 1:
        return mask  # nothing but background
    areas = stats[1:, cv2.CC_STAT_AREA]  # skip label 0 (background)
    largest_label = 1 + int(np.argmax(areas))
    return np.where(labels == largest_label, 255, 0).astype(np.uint8)


def strip_border_artifact(gray: np.ndarray) -> np.ndarray:
    """Removes the border-artifact rows (if any) from the image itself.
    This must happen before flattening -- otherwise those artifact pixels
    are still present in the data and get scattered to different row
    positions per column once each column is shifted independently,
    smearing a jagged white/black band across the flattened result."""
    depth = _find_border_artifact_depth(gray)
    return gray[depth:] if depth > 0 else gray


def detect_surface_curve(gray: np.ndarray) -> np.ndarray:
    """Estimates the retinal tissue position per column as the centroid
    (center of mass) of a binary tissue mask for that column, below any
    border artifact.

    Two earlier versions of this function were tried and rejected:
    - A hard "first row crossing an intensity threshold" was too fragile --
      a single stray bright pixel or a slightly-off threshold could make the
      detected boundary jump by hundreds of pixels.
    - A brightness-*weighted* centroid (using raw pixel value as weight) was
      more stable, but got skewed by real saturated/overexposed patches in
      some scans (occasional sensor clipping to pure white over a chunk of
      the image) -- those pixels dominated the weighted average despite
      carrying no real gradient information once clipped.

    Using the *topmost* pixel of a binary tissue mask (Otsu-thresholded,
    with small noise specks cleaned up morphologically) rather than the
    centroid of the whole mask: a bright lesion or saturated patch deep
    within the tissue band still counts as "tissue" for the mask, but no
    longer pulls the detected boundary down toward it, since we only care
    where the mask *starts*, not its center of mass. Combined with the
    outlier-robust polynomial fit below, this held up across a random
    sample of real training images where ~45% have a significant saturated
    region somewhere in the scan -- common enough that a fragile detector
    silently corrupts a large fraction of the dataset, not just a rare edge
    case.
    """
    h, w = gray.shape
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    border_depth = _find_border_artifact_depth(blurred)
    search_region = blurred[border_depth:]

    _, mask = cv2.threshold(search_region, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((9, 25), np.uint8))
    mask = _largest_connected_component(mask)

    boundary = np.full(w, search_region.shape[0] / 2, dtype=np.float32)
    for x in range(w):
        rows_with_tissue = np.where(mask[:, x] > 0)[0]
        if len(rows_with_tissue) > 0:
            boundary[x] = rows_with_tissue[0]
    boundary += border_depth
    return _fit_smooth_curve(boundary)


def _fit_smooth_curve(boundary: np.ndarray, degree: int = 2, outlier_std: float = 2.5) -> np.ndarray:
    """Fits a low-degree polynomial to the per-column boundary estimates
    instead of just smoothing them with a moving average. Real retinal
    curvature is a smooth arc (roughly parabolic across a B-scan), so a
    polynomial fit is both more physically appropriate and structurally
    incapable of producing the sharp single-column spikes a moving average
    can still leave behind when a handful of adjacent columns are all
    thrown off the same way (e.g. by a saturated patch). Fits twice,
    dropping columns that are far from the first fit, so a cluster of bad
    columns doesn't drag the curve toward them.
    """
    x = np.arange(len(boundary))
    coeffs = np.polyfit(x, boundary, degree)
    first_fit = np.polyval(coeffs, x)

    residuals = boundary - first_fit
    std = residuals.std()
    inliers = np.abs(residuals) <= outlier_std * std if std > 1e-6 else np.ones_like(x, dtype=bool)
    if inliers.sum() < degree + 1:
        return first_fit  # not enough inliers to refit -- fall back to the first pass

    coeffs = np.polyfit(x[inliers], boundary[inliers], degree)
    return np.polyval(coeffs, x)


def flatten_bscan(gray: np.ndarray, max_shift_fraction: float = 0.15, max_curve_span_fraction: float = 0.4) -> np.ndarray:
    """Shifts each column vertically so the detected retinal surface curve
    becomes a flat horizontal line -- corrects the natural curvature of the
    eye / scan tilt. Standard preprocessing step in OCT layer analysis
    pipelines.

    Two safety nets, because on real training images (low contrast, noise,
    saturated patches) curve detection sometimes gets it wrong in ways that
    are worse than doing nothing:

    1. Quality gate: if the *fitted* curve's total span exceeds
       `max_curve_span_fraction` of the image height, that's more curvature
       than a real single B-scan plausibly has -- treat the detection as
       unreliable and skip flattening for this image entirely (return it
       denoised but otherwise unchanged) rather than applying a
       transformation we have no confidence in.
    2. Per-column shift cap: even when the gate passes, an individual
       column's shift is capped at `max_shift_fraction` of the image
       height, so one still-noisy column can't produce a wild local jump.
    """
    h, w = gray.shape
    curve = detect_surface_curve(gray)

    curve_span = curve.max() - curve.min()
    if curve_span > h * max_curve_span_fraction:
        return gray.copy()

    reference_row = int(np.median(curve))
    max_shift = int(h * max_shift_fraction)

    flattened = np.zeros_like(gray)
    for x in range(w):
        shift = int(np.clip(reference_row - int(curve[x]), -max_shift, max_shift))
        column = np.roll(gray[:, x], shift)
        if shift > 0:
            column[:shift] = 0
        elif shift < 0:
            column[shift:] = 0
        flattened[:, x] = column
    return flattened


def crop_to_retina(gray: np.ndarray, margin: int = 10) -> np.ndarray:
    """Crops to the vertical extent of the bright tissue band, discarding
    the black background above/below present in essentially all OCT
    B-scans."""
    h = gray.shape[0]
    row_brightness = gray.mean(axis=1)
    threshold = row_brightness.max() * 0.15
    bright_rows = np.where(row_brightness > threshold)[0]
    if len(bright_rows) == 0:
        return gray  # degrade gracefully -- shouldn't happen on real OCT images
    top = max(0, int(bright_rows.min()) - margin)
    bottom = min(h, int(bright_rows.max()) + margin)
    return gray[top:bottom, :]


_INTERMEDIATE_HEIGHT = 280  # downscale target before the expensive steps below


def _downscale_before_processing(gray: np.ndarray, target_height: int = _INTERMEDIATE_HEIGHT) -> np.ndarray:
    """Denoising/flattening cost scales with pixel count, and the final
    model input is 224x224 regardless -- so running the expensive steps at
    native resolution (up to ~500x768) wastes most of that compute on
    detail that gets thrown away at the final resize anyway. Downscaling
    first (measured ~3x speedup on real training images) doesn't lose
    anything the model would have kept."""
    h, w = gray.shape
    if h <= target_height:
        return gray
    scale = target_height / h
    new_w = max(1, int(round(w * scale)))
    return cv2.resize(gray, (new_w, target_height), interpolation=cv2.INTER_AREA)


def preprocess_oct(image: Image.Image) -> Image.Image:
    """Full OCT-specific preprocessing pipeline. Runs before the generic
    resize/normalize step. Takes any PIL image, returns an RGB PIL image
    (grayscale result duplicated across channels, same convention used
    elsewhere in this codebase for feeding grayscale scans into ResNet50)."""
    gray = np.asarray(image.convert("L"))
    stripped = strip_border_artifact(gray)
    downscaled = _downscale_before_processing(stripped)
    denoised = reduce_speckle_noise(downscaled)
    flattened = flatten_bscan(denoised)
    cropped = crop_to_retina(flattened)
    return Image.fromarray(cropped).convert("RGB")
