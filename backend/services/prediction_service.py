"""
services/prediction_service.py
--------------------------------
Turns an uploaded image into a digit prediction.

The model was trained on MNIST: 28x28 grayscale, WHITE digit on BLACK
background, digit scaled to fit a 20x20 box and centred (by centre of
mass) inside the 28x28 frame. Real-world images (a drawing from the
Swing canvas, a phone photo, a scanned page) rarely look like that, so
the preprocessing below makes them look like it:

  1. convert to grayscale
  2. invert if the background is bright (dark ink on white paper)
  3. threshold away faint noise
  4. crop to the digit's bounding box
  5. scale so the longest side is 20px (keep aspect ratio)
  6. paste into a 28x28 canvas, centred by centre of mass
  7. scale pixels to 0..1

Step 4-6 matter a lot — skipping them is the #1 reason MNIST models do
badly on hand-drawn input.
"""

import numpy as np
from PIL import Image, ImageOps

from model.model_loader import get_model

IMG_SIZE = 28
BOX_SIZE = 20
NOISE_THRESHOLD = 0.15  # fraction of max brightness treated as "ink"


class PredictionError(Exception):
    """Raised when the image can't be turned into a prediction."""
    pass


def preprocess_image(stream) -> np.ndarray:
    """Returns an array of shape (1, 28, 28, 1), float32, values in [0, 1]."""
    try:
        img = Image.open(stream)
        img = ImageOps.exif_transpose(img)
        # Flatten transparency onto white so transparent PNG canvases work.
        if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
            rgba = img.convert("RGBA")
            bg = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
            img = Image.alpha_composite(bg, rgba)
        img = img.convert("L")
    except Exception as exc:
        raise PredictionError("Could not read the image file.") from exc

    arr = np.asarray(img, dtype=np.float32) / 255.0

    # Dark ink on a light background -> invert so the digit is bright.
    if np.median(arr) > 0.5:
        arr = 1.0 - arr

    # Stretch contrast, drop faint noise.
    peak = arr.max()
    if peak <= 0.05:
        raise PredictionError("The image appears to be blank — no digit found.")
    arr = arr / peak
    arr[arr < NOISE_THRESHOLD] = 0.0

    ys, xs = np.nonzero(arr)
    if len(ys) == 0:
        raise PredictionError("The image appears to be blank — no digit found.")
    arr = arr[ys.min():ys.max() + 1, xs.min():xs.max() + 1]

    # Scale the longest side to BOX_SIZE, preserving aspect ratio.
    h, w = arr.shape
    scale = BOX_SIZE / max(h, w)
    new_w, new_h = max(1, round(w * scale)), max(1, round(h * scale))
    small = Image.fromarray((arr * 255).astype(np.uint8)).resize((new_w, new_h), Image.LANCZOS)
    small = np.asarray(small, dtype=np.float32) / 255.0

    # Paste into 28x28 so the centre of mass sits at the centre.
    total = small.sum()
    cy = (small.sum(axis=1) * np.arange(new_h)).sum() / total
    cx = (small.sum(axis=0) * np.arange(new_w)).sum() / total
    off_y = int(round(IMG_SIZE / 2 - cy))
    off_x = int(round(IMG_SIZE / 2 - cx))
    off_y = min(max(off_y, 0), IMG_SIZE - new_h)
    off_x = min(max(off_x, 0), IMG_SIZE - new_w)

    canvas = np.zeros((IMG_SIZE, IMG_SIZE), dtype=np.float32)
    canvas[off_y:off_y + new_h, off_x:off_x + new_w] = small
    return canvas.reshape(1, IMG_SIZE, IMG_SIZE, 1)


def predict_digit(stream) -> dict:
    """
    Returns:
        {
          "predicted_digit": int,
          "confidence": float (0..1),
          "probabilities": [10 floats],
          "top3": [{"digit": int, "confidence": float}, ...]
        }
    """
    x = preprocess_image(stream)
    model = get_model()  # raises ModelLoadError if not loaded

    try:
        probs = np.asarray(model.predict(x, verbose=0)[0], dtype=np.float64)
    except Exception as exc:
        raise PredictionError(f"Model inference failed: {exc}") from exc

    digit = int(np.argmax(probs))
    top_idx = np.argsort(probs)[::-1][:3]
    return {
        "predicted_digit": digit,
        "confidence": round(float(probs[digit]), 6),
        "probabilities": [round(float(p), 6) for p in probs],
        "top3": [{"digit": int(i), "confidence": round(float(probs[i]), 6)} for i in top_idx],
    }
