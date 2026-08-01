# Visioret: Explainable AI for Retinal OCT Disease Classification

Visioret is a minimal, local demo that classifies retinal OCT scans into four
categories — **CNV, DME, Drusen, Normal** — using a ResNet50 backbone, and
explains each prediction with a Grad-CAM heatmap over the region the model
focused on. This is a midterm progress demo (Streamlit, single machine, no
backend/database/deployment), not the full production system described in the
project proposal.

## Setup

```bash
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux
pip install -r requirements.txt
```

Requires Python 3.10+. Works on CPU; a GPU is used automatically if available.

The first run downloads ImageNet-pretrained ResNet50 weights from
`download.pytorch.org` (a few hundred MB) and caches them under
`~/.cache/torch/hub/checkpoints/`. This is the only network access the
project makes — after that first download, everything runs fully offline.

## Run the demo

```bash
streamlit run app.py
```

Then, in the browser tab Streamlit opens:
1. Upload an OCT image (JPEG/PNG), or pick one of the bundled sample images
   in the sidebar-adjacent dropdown.
2. Click **Predict**.
3. View the original image, the Grad-CAM overlay, the predicted class, its
   confidence score, and the per-class probability chart.

If no fine-tuned checkpoint exists yet at
`model/checkpoints/resnet50_oct.pth`, the app still launches and runs the
full pipeline using the ImageNet-pretrained backbone with a randomly
initialized 4-class head — the sidebar shows a clear warning that
predictions aren't trained yet, but the Grad-CAM visualization is fully
functional either way.

### Sample images and training data

This repo ships with real images from the Kermany OCT2017 dataset, so it
runs and demonstrates results out of the box with no download required:
- `samples/` — 4 crops (one per class) for quick, upload-free demoing.
- `data/` — the 400-image subset (100 per class) used to produce the
  included checkpoint, kept here for transparency/reproducibility.

**Attribution:** OCT2017 is from D.S. Kermany et al., "Identifying Medical
Diagnoses and Treatable Diseases by Image-Based Deep Learning," *Cell*,
2018, distributed under CC BY 4.0
(https://data.mendeley.com/datasets/rscbjbr9sj/2). Images here are an
unmodified subset, redistributed with attribution per that license.

## Optional: GPU-accelerated training

`pip install -r requirements.txt` installs a CPU-only PyTorch build by
default on some platforms. If you have an NVIDIA GPU and want faster
training, reinstall PyTorch with CUDA support inside the venv:

```bash
pip uninstall -y torch torchvision
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
```

Verify it worked:

```bash
python -c "import torch; print(torch.cuda.is_available())"
```

`train_quick.py` and `app.py` both auto-detect CUDA (`torch.device('cuda' if
torch.cuda.is_available() else 'cpu')`) with no code changes needed. A
machine without a GPU should just use the plain `requirements.txt` install
(CPU-only) — inference and Grad-CAM both run fine on CPU, just a bit slower
per image.

## Optional: retraining with more data

`data/` already contains the 400-image subset (100 per class) that produced
the included checkpoint, arranged as an `ImageFolder`-compatible layout:

```
data/
  CNV/*.jpeg
  DME/*.jpeg
  DRUSEN/*.jpeg
  NORMAL/*.jpeg
```

To retrain with more images, add more files to these folders (or replace
them) from the full Kermany OCT2017 dataset:
- Kaggle: https://www.kaggle.com/datasets/paultimothymooney/kermany2018
- Mendeley Data (original source): https://data.mendeley.com/datasets/rscbjbr9sj/2

Then run:

```bash
python model/train_quick.py
```

This freezes the ResNet50 backbone, fine-tunes only the final linear layer
for a few epochs (5 by default), prints train/val accuracy per epoch, and
saves the result to `model/checkpoints/resnet50_oct.pth`. The Streamlit app
picks this checkpoint up automatically on the next launch — no code changes
needed. Training is optional; the app is fully functional without it.

### Presenting on a different machine

Training and inference are decoupled: `resnet50_oct.pth` is just a file of
model weights, not tied to the GPU it was trained on. To present on a
machine without a GPU:
1. Copy the whole project folder to the other machine, excluding `venv/`.
2. On that machine: `python -m venv venv`, activate it, then
   `pip install -r requirements.txt` (plain CPU install is fine there).
3. Make sure `model/checkpoints/resnet50_oct.pth` made it over in the copy.
4. `streamlit run app.py` — it loads the checkpoint via
   `torch.load(path, map_location=device)`, which safely remaps
   GPU-trained tensors onto CPU. No retraining needed.

## Project structure

```
app.py                       # Streamlit UI
model/
  inference.py                # model loading, preprocessing, prediction, Grad-CAM
  train_quick.py               # optional quick fine-tuning script
  checkpoints/                 # resnet50_oct.pth goes here if trained
samples/                      # 4 bundled real OCT2017 images, one per class
data/                         # 400-image training subset (ImageFolder layout)
requirements.txt
```
