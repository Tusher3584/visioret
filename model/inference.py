"""Core inference + Grad-CAM pipeline, shared by app.py and train_quick.py."""

import os

import cv2
import numpy as np
import torch
import torch.nn as nn
from PIL import Image
from torchvision import models, transforms

CLASS_NAMES = ["CNV", "DME", "Drusen", "Normal"]

IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]

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

    Returns (model, checkpoint_loaded, class_names).
    """
    classes = CLASS_NAMES
    checkpoint_loaded = False

    if checkpoint_path and os.path.isfile(checkpoint_path):
        try:
            checkpoint = torch.load(checkpoint_path, map_location=device)
            if isinstance(checkpoint, dict) and "model_state_dict" in checkpoint:
                classes = checkpoint.get("classes", CLASS_NAMES)
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
    return model, checkpoint_loaded, classes


def preprocess_image(image: Image.Image) -> torch.Tensor:
    """PIL image (any mode) -> normalized (1, 3, 224, 224) tensor."""
    image = image.convert("RGB")
    tensor = _preprocess(image)
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
    original = original_pil_image.convert("RGB").resize((224, 224))
    original_np = np.array(original)

    heatmap_uint8 = np.uint8(255 * heatmap)
    heatmap_color = cv2.applyColorMap(heatmap_uint8, cv2.COLORMAP_JET)
    heatmap_color = cv2.cvtColor(heatmap_color, cv2.COLOR_BGR2RGB)

    overlay = original_np.astype(np.float32) * (1 - alpha) + heatmap_color.astype(np.float32) * alpha
    overlay = np.clip(overlay, 0, 255).astype(np.uint8)
    return Image.fromarray(overlay)
