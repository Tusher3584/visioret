"""Optional quick fine-tune on a local data/ subset. Not required for the demo
to run -- app.py works with the ImageNet backbone + random head if this was
never run or if data/ is empty.

Usage:
    python model/train_quick.py
"""

import os
import sys

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, random_split
from torchvision import datasets, transforms

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from model.inference import IMAGENET_MEAN, IMAGENET_STD, build_model  # noqa: E402

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT_DIR, "data")
CHECKPOINT_PATH = os.path.join(ROOT_DIR, "model", "checkpoints", "resnet50_oct.pth")

EPOCHS = 5
BATCH_SIZE = 16
LEARNING_RATE = 1e-3
VAL_SPLIT = 0.2


def has_data(data_dir: str) -> bool:
    if not os.path.isdir(data_dir):
        return False
    class_dirs = [d for d in os.scandir(data_dir) if d.is_dir()]
    return any(any(os.scandir(d.path)) for d in class_dirs)


def evaluate(model, loader, device):
    model.eval()
    correct, total = 0, 0
    with torch.no_grad():
        for images, labels in loader:
            images, labels = images.to(device), labels.to(device)
            outputs = model(images)
            correct += (outputs.argmax(1) == labels).sum().item()
            total += images.size(0)
    return correct / total if total else 0.0


def main():
    if not has_data(DATA_DIR):
        print(
            f"No images found under '{DATA_DIR}'. "
            "Populate data/{CNV,DME,DRUSEN,NORMAL}/*.jpg (or .png) and rerun this script."
        )
        return

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

    transform = transforms.Compose(
        [
            transforms.Grayscale(num_output_channels=3),
            transforms.Resize((224, 224)),
            transforms.RandomHorizontalFlip(),
            transforms.ToTensor(),
            transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
        ]
    )

    dataset = datasets.ImageFolder(DATA_DIR, transform=transform)
    classes = dataset.classes
    print(f"Detected classes (alphabetical folder order): {classes}")

    val_size = max(1, int(len(dataset) * VAL_SPLIT))
    train_size = len(dataset) - val_size
    train_ds, val_ds = random_split(dataset, [train_size, val_size])

    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=BATCH_SIZE, shuffle=False)

    model = build_model(num_classes=len(classes))
    model.to(device)

    # Freeze the pretrained backbone, fine-tune only the new head for a quick demo run.
    for name, param in model.named_parameters():
        param.requires_grad = name.startswith("fc.")

    optimizer = torch.optim.Adam(filter(lambda p: p.requires_grad, model.parameters()), lr=LEARNING_RATE)
    criterion = nn.CrossEntropyLoss()

    for epoch in range(EPOCHS):
        model.train()
        running_loss, correct, total = 0.0, 0, 0
        for images, labels in train_loader:
            images, labels = images.to(device), labels.to(device)
            optimizer.zero_grad()
            outputs = model(images)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()

            running_loss += loss.item() * images.size(0)
            correct += (outputs.argmax(1) == labels).sum().item()
            total += images.size(0)

        train_acc = correct / total if total else 0.0
        val_acc = evaluate(model, val_loader, device)
        print(
            f"Epoch {epoch + 1}/{EPOCHS} - loss: {running_loss / max(total, 1):.4f} "
            f"- train_acc: {train_acc:.4f} - val_acc: {val_acc:.4f}"
        )

    os.makedirs(os.path.dirname(CHECKPOINT_PATH), exist_ok=True)
    torch.save({"model_state_dict": model.state_dict(), "classes": classes}, CHECKPOINT_PATH)
    print(f"Saved checkpoint to {CHECKPOINT_PATH}")


if __name__ == "__main__":
    main()
