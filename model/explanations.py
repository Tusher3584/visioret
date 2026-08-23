"""Per-class clinical context + a lightweight, heatmap-derived location
description, combined into the "why" text shown alongside a prediction.

The clinical text is static (general OCT findings for each class, not a
diagnosis of the specific image). The location sentence is the only
per-image ("dynamic") part -- it is computed directly from the Grad-CAM
heatmap's geometry (centroid position, spread), not from any anatomical
segmentation we don't have, so it only ever describes coarse image
position (left/center/right, tight/broad), never a specific retinal layer.
"""

import numpy as np

CLINICAL_EXPLANATIONS = {
    "CNV": (
        "CNV (choroidal neovascularization) occurs when abnormal blood vessels grow from the "
        "choroid through Bruch's membrane into the retina, typically as a feature of wet "
        "age-related macular degeneration. On OCT, this usually appears as a dome-shaped "
        "elevation beneath the retinal surface, often accompanied by fluid pooling around it. "
        "The model looks for this elevated, fluid-associated structure."
    ),
    "DME": (
        "DME (diabetic macular edema) results from leaking retinal blood vessels, a complication "
        "of diabetic retinopathy, that let fluid build up within the retina itself. On OCT, this "
        "shows up as dark, rounded cystoid spaces inside the retinal layers along with overall "
        "retinal thickening. The model looks for these intraretinal fluid pockets."
    ),
    "DRUSEN": (
        "Drusen are deposits of extracellular material that accumulate between the retinal "
        "pigment epithelium (RPE) and Bruch's membrane, an early sign of age-related macular "
        "degeneration. On OCT, they appear as small, discrete, dome-shaped elevations of the RPE "
        "layer, without the fluid pooling seen in CNV. The model looks for these RPE elevations."
    ),
    "NORMAL": (
        "A normal OCT scan shows a clearly defined foveal contour and distinct, evenly layered "
        "retinal architecture, with no fluid, cystic spaces, or abnormal elevations. The model "
        "checks the foveal region most closely, since that is where the findings above would "
        "appear if present."
    ),
}


def describe_heatmap_location(heatmap: np.ndarray) -> str:
    """One sentence describing where in THIS image the heatmap concentrated.

    Deliberately coarse (image-geometry only: left/center/right, tight/broad)
    -- we have no retinal-layer segmentation, so anything more specific would
    be an unverified claim dressed up as a finding.
    """
    height, width = heatmap.shape
    total = float(heatmap.sum())
    if total <= 0:
        return "The model's attention was too diffuse to localize to a specific region of this scan."

    col_indices = np.arange(width)
    centroid_col = float((heatmap.sum(axis=0) * col_indices).sum() / total)
    col_fraction = centroid_col / width
    if col_fraction < 0.33:
        horizontal = "the left side of the scan"
    elif col_fraction > 0.67:
        horizontal = "the right side of the scan"
    else:
        horizontal = "the central region of the scan"

    area_fraction = float((heatmap > 0.5).sum()) / (height * width)
    if area_fraction < 0.08:
        spread = "tightly concentrated"
    elif area_fraction < 0.20:
        spread = "concentrated"
    else:
        spread = "spread across a broader area"

    return f"For this image, the model's attention was {spread} in {horizontal}."


def build_explanation(predicted_class: str, heatmap: np.ndarray) -> str:
    clinical = CLINICAL_EXPLANATIONS.get(predicted_class.upper(), "")
    location = describe_heatmap_location(heatmap)
    return f"{clinical} {location}"
