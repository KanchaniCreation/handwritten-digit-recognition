"""
ml/train.py
-------------
Trains a small CNN on MNIST and saves it to ml/digit_model.keras.

    python ml/train.py                 # default: 15 epochs
    python ml/train.py --epochs 5      # quicker

Outputs (all in ml/):
    digit_model.keras      the model the Flask API loads
    training_report.json   test accuracy/loss + per-class accuracy + history
    confusion_matrix.png   (if matplotlib is installed)

Data augmentation (small random rotations / shifts / zoom) is built into
the model as layers. It is only active during training, and is what makes
the model cope with the messier digits people draw on the Swing canvas.
"""

import argparse
import json
import os

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

import numpy as np
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(HERE, "digit_model.keras")
REPORT_PATH = os.path.join(HERE, "training_report.json")


def build_model() -> keras.Model:
    return keras.Sequential([
        layers.Input(shape=(28, 28, 1)),

        # --- augmentation (training only) ---
        layers.RandomRotation(0.08),
        layers.RandomTranslation(0.10, 0.10),
        layers.RandomZoom(0.10),

        layers.Conv2D(32, 3, padding="same", activation="relu"),
        layers.BatchNormalization(),
        layers.Conv2D(32, 3, padding="same", activation="relu"),
        layers.MaxPooling2D(),
        layers.Dropout(0.25),

        layers.Conv2D(64, 3, padding="same", activation="relu"),
        layers.BatchNormalization(),
        layers.Conv2D(64, 3, padding="same", activation="relu"),
        layers.MaxPooling2D(),
        layers.Dropout(0.25),

        layers.Flatten(),
        layers.Dense(128, activation="relu"),
        layers.Dropout(0.4),
        layers.Dense(10, activation="softmax"),
    ], name="digit_cnn")


def main():
    parser = argparse.ArgumentParser(description="Train the digit-recognition CNN on MNIST.")
    parser.add_argument("--epochs", type=int, default=15)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    keras.utils.set_random_seed(args.seed)

    print("Loading MNIST (downloads ~11 MB the first time)...")
    (x_train, y_train), (x_test, y_test) = keras.datasets.mnist.load_data()
    x_train = (x_train.astype("float32") / 255.0)[..., None]
    x_test = (x_test.astype("float32") / 255.0)[..., None]

    model = build_model()
    model.compile(optimizer=keras.optimizers.Adam(1e-3),
                  loss="sparse_categorical_crossentropy",
                  metrics=["accuracy"])
    model.summary()

    callbacks = [
        keras.callbacks.EarlyStopping(monitor="val_accuracy", patience=4, restore_best_weights=True),
        keras.callbacks.ReduceLROnPlateau(monitor="val_loss", factor=0.5, patience=2, verbose=1),
    ]
    history = model.fit(x_train, y_train, validation_split=0.1,
                        epochs=args.epochs, batch_size=args.batch_size, callbacks=callbacks)

    test_loss, test_acc = model.evaluate(x_test, y_test, verbose=0)
    print(f"\nTest accuracy: {test_acc:.4f}   Test loss: {test_loss:.4f}")

    preds = np.argmax(model.predict(x_test, verbose=0), axis=1)
    confusion = np.zeros((10, 10), dtype=int)
    for t, p in zip(y_test, preds):
        confusion[t, p] += 1
    per_class = {str(d): round(float(confusion[d, d] / confusion[d].sum()), 4) for d in range(10)}

    model.save(MODEL_PATH)
    print(f"Model saved to {MODEL_PATH}")

    with open(REPORT_PATH, "w") as fh:
        json.dump({
            "test_accuracy": round(float(test_acc), 4),
            "test_loss": round(float(test_loss), 4),
            "per_class_accuracy": per_class,
            "confusion_matrix": confusion.tolist(),
            "epochs_run": len(history.history["loss"]),
            "history": {k: [round(float(v), 4) for v in vals] for k, vals in history.history.items()},
        }, fh, indent=2)
    print(f"Report saved to {REPORT_PATH}")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(6, 6))
        ax.imshow(confusion, cmap="Blues")
        ax.set_xlabel("Predicted"); ax.set_ylabel("Actual"); ax.set_title("MNIST confusion matrix")
        ax.set_xticks(range(10)); ax.set_yticks(range(10))
        for i in range(10):
            for j in range(10):
                ax.text(j, i, confusion[i, j], ha="center", va="center", fontsize=7,
                        color="white" if confusion[i, j] > confusion.max() / 2 else "black")
        fig.tight_layout()
        fig.savefig(os.path.join(HERE, "confusion_matrix.png"), dpi=120)
        print("Confusion matrix saved.")
    except ImportError:
        print("(matplotlib not installed — skipping confusion_matrix.png)")


if __name__ == "__main__":
    main()
