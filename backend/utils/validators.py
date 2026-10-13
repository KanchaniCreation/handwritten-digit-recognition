"""
utils/validators.py
---------------------
Validates the multipart upload for POST /predict before any ML runs.
Expected form field: "image" (file). Optional form field: "source"
('canvas' or 'upload', default 'upload').
"""

import os

from PIL import Image

MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", 2 * 1024 * 1024))  # 2 MB
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp"}
ALLOWED_SOURCES = {"canvas", "upload"}


class ValidationError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def validate_image_upload(files, form):
    """Returns (file_storage, source). Raises ValidationError on bad input."""
    if "image" not in files:
        raise ValidationError("No file part named 'image' in the request.", 400)

    f = files["image"]
    if not f or not f.filename:
        raise ValidationError("No file selected.", 400)

    ext = os.path.splitext(f.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError(
            f"Unsupported file type '{ext or 'none'}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}.", 415
        )

    f.stream.seek(0, os.SEEK_END)
    size = f.stream.tell()
    f.stream.seek(0)
    if size == 0:
        raise ValidationError("The uploaded file is empty.", 400)
    if size > MAX_UPLOAD_BYTES:
        raise ValidationError(f"File too large (max {MAX_UPLOAD_BYTES // 1024} KB).", 413)

    # Make sure it really is an image, not a renamed text file.
    try:
        Image.open(f.stream).verify()
    except Exception:
        raise ValidationError("The file is not a valid image.", 400)
    finally:
        f.stream.seek(0)

    source = (form.get("source") or "upload").strip().lower()
    if source not in ALLOWED_SOURCES:
        raise ValidationError("Field 'source' must be 'canvas' or 'upload'.", 400)

    return f, source
