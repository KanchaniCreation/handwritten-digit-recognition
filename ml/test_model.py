"""
ml/test_model.py
------------------
Quick sanity check of the saved model + the real preprocessing pipeline,
without starting Flask:

    python ml/test_model.py path/to/digit.png
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "backend"))

from model.model_loader import load_model  # noqa: E402
from services.prediction_service import predict_digit  # noqa: E402

if len(sys.argv) != 2:
    sys.exit("usage: python ml/test_model.py <image.png>")

load_model(os.path.join(HERE, "digit_model.keras"))
with open(sys.argv[1], "rb") as fh:
    result = predict_digit(fh)
print(f"Predicted {result['predicted_digit']}  (confidence {result['confidence']:.2%})")
for t in result["top3"]:
    print(f"   {t['digit']}: {t['confidence']:.2%}")
