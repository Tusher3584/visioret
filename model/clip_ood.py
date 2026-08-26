"""CLIP zero-shot "is this actually an OCT scan?" check.

Replaces the old feature-distance OOD stage (model/ood_detector.py's
extract_features/ood_distance), which measured distance from a centroid
calibrated on a single dataset's images. That's inherently brittle: any
image from a source not in the calibration set -- even a completely
legitimate OCT scan from a different hospital/scanner, which is exactly
what Checkpoint 5's external datasets are -- can sit far enough from that
one dataset's centroid to get wrongly rejected. Confirmed in practice:
real CNV scans from Noor Eye Hospital were being rejected as "not OCT"
purely because the calibration set was Kermany-only.

CLIP (trained on ~400M image-text pairs) already has a general visual
understanding of what a medical scan looks like vs. a photo, without
needing calibration against any specific OCT dataset at all -- it
generalizes to sources it's never seen, which is exactly the property
the old approach lacked. Validated against 30 real OCT images spanning
all 4 sources (Kermany/Noor/OCTDL/Duke) and 15 real non-OCT photos:
45/45 correct, including the 2 specific Noor images that the old
distance-based gate was wrongly rejecting.

The grayscale heuristic (model/ood_detector.py) still runs first as a
near-zero-cost pre-filter -- real OCT B-scans are reliably near-grayscale
regardless of source, so it's safe to keep and saves a CLIP inference for
the (common) case of an obviously-colorful upload.
"""

import torch
from PIL import Image
from transformers import CLIPModel, CLIPProcessor

CLIP_MODEL_NAME = "openai/clip-vit-base-patch32"

# Index 0 is the only "accept" prompt -- everything else is a negative
# category. Kept broad (not just "photo of X") since abstract/artistic
# images (e.g. wallpapers) don't fit neatly into "photograph of a scene"
# and were the one edge case found during validation that needed an
# explicit negative prompt of its own.
OCT_PROMPT_INDEX = 0
PROMPTS = [
    "a retinal optical coherence tomography (OCT) B-scan medical image",
    "a photograph of a person",
    "a photograph of an everyday object or scene",
    "a photograph of an animal",
    "a natural photograph taken with a camera",
    "an X-ray or CT scan medical image",
    "an abstract digital art image or wallpaper with no real objects",
    "a solid color or smooth gradient background image",
    # Added during the pre-defense review. A grayscale confusion-matrix plot
    # was being ACCEPTED as an OCT scan at p=0.85 and classified DME with 77%
    # confidence. The cause is structural rather than a bad threshold: this is
    # argmax over a fixed prompt set, so the gate can only reject what some
    # prompt actually describes. Nothing here described a chart, so the OCT
    # prompt won by default -- the same failure mode the wallpaper prompt
    # above was added for. Charts and screenshots are realistic mis-uploads
    # (someone pastes a figure from a paper, or a screenshot of a viewer).
    "a chart, graph, plot, heatmap, or data visualization figure",
    "a screenshot of a computer screen, a document, or printed text",
]


def load_clip(device):
    model = CLIPModel.from_pretrained(CLIP_MODEL_NAME).to(device).eval()
    processor = CLIPProcessor.from_pretrained(CLIP_MODEL_NAME)
    return model, processor


@torch.no_grad()
def clip_is_oct(image: Image.Image, clip_model, clip_processor, device) -> tuple[bool, float]:
    """Zero-shot classification against PROMPTS. Decision rule is simply
    "did the OCT prompt win the argmax" -- deliberately not a tunable
    probability threshold, since threshold-tuning against any particular
    calibration set is exactly the brittleness this replaces."""
    inputs = clip_processor(text=PROMPTS, images=image.convert("RGB"), return_tensors="pt", padding=True).to(device)
    outputs = clip_model(**inputs)
    probs = outputs.logits_per_image.softmax(dim=1)[0].cpu().numpy()
    best_index = int(probs.argmax())
    return best_index == OCT_PROMPT_INDEX, float(probs[OCT_PROMPT_INDEX])
