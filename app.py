import glob
import os

import streamlit as st
import torch
from PIL import Image, UnidentifiedImageError

from model.explanations import build_explanation
from model.inference import (
    generate_gradcam,
    load_model,
    overlay_gradcam,
    predict,
    preprocess_image,
)
from model.clip_ood import load_clip
from model.ood_detector import check_is_oct

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
CHECKPOINT_PATH = os.path.join(ROOT_DIR, "model", "checkpoints", "resnet50_oct.pth")
SAMPLES_DIR = os.path.join(ROOT_DIR, "samples")

st.set_page_config(page_title="Visioret", page_icon="👁️", layout="wide")


@st.cache_resource
def get_model():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model, checkpoint_loaded, classes, _val_macro_f1 = load_model(CHECKPOINT_PATH, device)
    return model, checkpoint_loaded, classes, device


model, checkpoint_loaded, classes, device = get_model()


@st.cache_resource
def get_clip():
    return load_clip(device)


clip_model, clip_processor = get_clip()

st.title("Visioret: Explainable AI for Retinal OCT Disease Classification")
st.caption("Upload an OCT scan to get a predicted disease class, a confidence score, and a Grad-CAM visual explanation.")

with st.sidebar:
    st.header("Model status")
    if checkpoint_loaded:
        st.success("Fine-tuned checkpoint loaded")
    else:
        st.warning("Demo model not fine-tuned yet; predictions may be inaccurate, but Grad-CAM pipeline works.")
    st.write(f"**Device:** {device.type.upper()}")
    st.write(f"**Classes:** {', '.join(classes)}")

st.subheader("1. Provide an image")
col_upload, col_sample = st.columns([2, 1])

with col_upload:
    uploaded_file = st.file_uploader("Upload an OCT image (JPEG/PNG)", type=["jpg", "jpeg", "png"])

with col_sample:
    sample_paths = sorted(glob.glob(os.path.join(SAMPLES_DIR, "*.*"))) if os.path.isdir(SAMPLES_DIR) else []
    sample_names = [os.path.basename(p) for p in sample_paths]
    sample_choice = st.selectbox("...or pick a bundled sample image", ["None"] + sample_names)

image = None
image_source = None
if uploaded_file is not None:
    try:
        image = Image.open(uploaded_file)
        image_source = f"uploaded: {uploaded_file.name}"
    except UnidentifiedImageError:
        st.error("Could not read that file as an image. Please upload a valid JPEG or PNG.")
elif sample_choice != "None":
    try:
        image = Image.open(os.path.join(SAMPLES_DIR, sample_choice))
        image_source = f"sample: {sample_choice}"
    except (UnidentifiedImageError, FileNotFoundError):
        st.error("Could not load the selected sample image.")

if image is not None:
    st.caption(f"Loaded {image_source}")
    if st.button("Predict", type="primary"):
        with st.spinner("Running inference..."):
            try:
                image_tensor = preprocess_image(image)

                is_oct, reason, ood_detail = check_is_oct(image, clip_model, clip_processor, device)
                if not is_oct:
                    st.warning(
                        "This doesn't look like a retinal OCT scan, so no diagnosis was made. "
                        "Please upload an OCT B-scan image (JPEG/PNG)."
                    )
                    st.stop()

                class_name, confidence, probs_dict = predict(model, image_tensor, device, class_names=classes)
                class_index = classes.index(class_name)
                heatmap = generate_gradcam(model, image_tensor, class_index, device)
                overlay = overlay_gradcam(image, heatmap)
                explanation = build_explanation(class_name, heatmap)
            except Exception as exc:
                st.error(f"Inference failed: {exc}")
                st.stop()

        st.subheader("2. Results")
        col_left, col_right = st.columns(2)
        with col_left:
            st.image(image.convert("RGB"), caption="Original image", use_container_width=True)
        with col_right:
            st.image(overlay, caption="Grad-CAM overlay", use_container_width=True)

        st.subheader("3. Prediction")
        st.metric("Predicted class", class_name, delta=f"{confidence * 100:.1f}% confidence")
        st.bar_chart(probs_dict)

        st.subheader("4. Why this region?")
        st.write(explanation)
else:
    st.info("Upload an OCT image or pick a bundled sample above, then click Predict.")
