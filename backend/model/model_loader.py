"""
model/model_loader.py
-----------------------
Loads the trained TensorFlow/Keras model ONCE at startup and keeps it in
memory. Everything else calls get_model().

TensorFlow is imported lazily inside load_model() so that tools that only
need the validators/routes (e.g. unit tests) don't have to import it.
"""

import os

_model = None
_model_path = None


class ModelLoadError(Exception):
    """Raised when the model file is missing/corrupt or not loaded yet."""
    pass


def load_model(path: str):
    global _model, _model_path

    if not os.path.isfile(path):
        raise ModelLoadError(
            f"Model file not found at '{path}'. Train it first with:  python ml/train.py"
        )
    try:
        import tensorflow as tf  # noqa: WPS433 (lazy import on purpose)
        os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
        _model = tf.keras.models.load_model(path)
        _model_path = path
    except Exception as exc:
        raise ModelLoadError(f"Could not load model from '{path}': {exc}") from exc
    return _model


def get_model():
    if _model is None:
        raise ModelLoadError("Model is not loaded.")
    return _model


def is_loaded() -> bool:
    return _model is not None


def model_path():
    return _model_path
