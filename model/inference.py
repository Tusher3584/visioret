"""Core inference + Grad-CAM pipeline, shared by app.py and train_quick.py."""

import os

import cv2
import numpy as np
import torch
import torch.nn as nn
from PIL import Image
from torchvision import models, transforms

# Fallback class list, used ONLY when no fine-tuned checkpoint is present
# (load_model then builds an untrained 4-class head). Whenever a checkpoint
# IS loaded, its own stored `classes` list wins and every caller passes that
# through explicitly.
#
# Casing matters and must match what training produced: train_full.py derives
# class names from the Kermany folder names, which are upper-case. Having this
# fallback read "Drusen"/"Normal" meant the two spellings could differ
# depending on whether a checkpoint had loaded -- and downstream code compares
# these strings (explanations.py keys on them, evaluate_cross_dataset.py has
# to .upper() around it). Keep them upper-case.
CLASS_NAMES = ["CNV", "DME", "DRUSEN", "NORMAL"]

IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]

# Must match model/train_full.py's eval_transform exactly -- this is what the
# deployed checkpoint was actually trained on. model/oct_preprocessing.py
# has a tested OCT-specific pipeline (denoise/flatten/crop) that was
# evaluated for Checkpoint 2 and intentionally left out: a clean fine-tune
# against it did not beat this plain resize+normalize baseline.
_preprocess = transforms.Compose(
    [
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
    ]
)


def build_model(num_classes: int = len(CLASS_NAMES)) -> nn.Module:
    model = models.resnet50(weights=models.ResNet50_Weights.IMAGENET1K_V2)
    model.fc = nn.Linear(model.fc.in_features, num_classes)
    return model


def load_model(checkpoint_path, device):
    """Loads a fine-tuned checkpoint if present, otherwise falls back to an
    ImageNet-pretrained backbone with a freshly-initialized 4-class head.

    Returns (model, checkpoint_loaded, class_names, val_macro_f1).
    val_macro_f1 is None when no checkpoint is loaded or it predates that field.
    """
    classes = CLASS_NAMES
    checkpoint_loaded = False
    val_macro_f1 = None

    if checkpoint_path and os.path.isfile(checkpoint_path):
        try:
            checkpoint = torch.load(checkpoint_path, map_location=device)
            if isinstance(checkpoint, dict) and "model_state_dict" in checkpoint:
                classes = checkpoint.get("classes", CLASS_NAMES)
                val_macro_f1 = checkpoint.get("val_macro_f1")
                model = build_model(num_classes=len(classes))
                model.load_state_dict(checkpoint["model_state_dict"])
            else:
                model = build_model(num_classes=len(CLASS_NAMES))
                model.load_state_dict(checkpoint)
            checkpoint_loaded = True
        except Exception as exc:
            print(f"Could not load checkpoint '{checkpoint_path}': {exc}")
            model = build_model()
    else:
        model = build_model()

    model.to(device)
    model.eval()
    return model, checkpoint_loaded, classes, val_macro_f1


def preprocess_image(image: Image.Image) -> torch.Tensor:
    """PIL image (any mode) -> normalized (1, 3, 224, 224) tensor. Converts
    to RGB first -- must match model/dataset.py's OCTDataset, which does the
    same before applying its transform, or grayscale uploads (common for
    OCT JPEGs) would produce a 1-channel tensor and fail at Normalize."""
    tensor = _preprocess(image.convert("RGB"))
    return tensor.unsqueeze(0)


def predict(model, image_tensor, device, class_names=CLASS_NAMES):
    image_tensor = image_tensor.to(device)
    with torch.no_grad():
        logits = model(image_tensor)
        probs = torch.softmax(logits, dim=1).squeeze(0).cpu().numpy()

    class_index = int(np.argmax(probs))
    class_name = class_names[class_index]
    confidence = float(probs[class_index])
    probs_dict = {class_names[i]: float(probs[i]) for i in range(len(class_names))}
    return class_name, confidence, probs_dict


class _GradCAMHook:
    """Captures forward activations and backward gradients of a target layer."""

    def __init__(self, target_layer):
        self.activations = None
        self.gradients = None
        self.fwd_handle = target_layer.register_forward_hook(self._save_activation)
        self.bwd_handle = target_layer.register_full_backward_hook(self._save_gradient)

    def _save_activation(self, module, inputs, output):
        self.activations = output.detach()

    def _save_gradient(self, module, grad_input, grad_output):
        self.gradients = grad_output[0].detach()

    def remove(self):
        self.fwd_handle.remove()
        self.bwd_handle.remove()


def generate_gradcam(model, image_tensor, class_index, device):
    """Manual Grad-CAM against model.layer4 (last conv block of ResNet50).

    Returns a numpy heatmap, values in [0, 1], shape (224, 224).
    """
    image_tensor = image_tensor.to(device).clone().requires_grad_(True)
    hook = _GradCAMHook(model.layer4)

    model.zero_grad()
    logits = model(image_tensor)
    if class_index is None:
        class_index = int(torch.argmax(logits, dim=1).item())
    score = logits[0, class_index]
    score.backward()

    activations = hook.activations[0]  # (C, H, W)
    gradients = hook.gradients[0]  # (C, H, W)
    hook.remove()

    weights = gradients.mean(dim=(1, 2))  # (C,) global-average-pooled gradients
    cam = torch.zeros(activations.shape[1:], dtype=torch.float32, device=activations.device)
    for i, w in enumerate(weights):
        cam += w * activations[i]

    cam = torch.relu(cam).cpu().numpy()
    if cam.max() > 0:
        cam = cam / cam.max()
    cam = cv2.resize(cam, (224, 224))
    return cam


def overlay_gradcam(original_pil_image: Image.Image, heatmap: np.ndarray, alpha: float = 0.45) -> Image.Image:
    """Blends the heatmap onto the original image AT THE ORIGINAL'S OWN SIZE.

    The heatmap is resized up to the original's dimensions rather than the
    original being squashed down to 224x224. Both directions "work", but only
    this one is geometrically honest: OCT B-scans are not square (512x496 and
    768x496 are both common), so shrinking a 768x496 scan into a 224x224
    overlay compresses it ~35% horizontally. The overlay would then be a
    different shape from the original shown beside it in the UI's compare
    view, and a reader mapping a hot region back onto the original scan would
    mislocate it.

    The model genuinely saw a squashed 224x224 tensor -- that part is fine and
    unchanged. Resizing the CAM back to (width, height) is simply the inverse
    of that squash, so the overlay lands where the model actually looked.
    """
    original = original_pil_image.convert("RGB")
    original_np = np.array(original)
    height, width = original_np.shape[:2]

    # cv2.resize takes (width, height); heatmap is (rows, cols) = (H, W).
    heatmap_resized = cv2.resize(heatmap, (width, height), interpolation=cv2.INTER_LINEAR)
    heatmap_uint8 = np.uint8(255 * np.clip(heatmap_resized, 0, 1))
    heatmap_color = cv2.applyColorMap(heatmap_uint8, cv2.COLORMAP_JET)
    heatmap_color = cv2.cvtColor(heatmap_color, cv2.COLOR_BGR2RGB)

    overlay = original_np.astype(np.float32) * (1 - alpha) + heatmap_color.astype(np.float32) * alpha
    overlay = np.clip(overlay, 0, 255).astype(np.uint8)
    return Image.fromarray(overlay)
