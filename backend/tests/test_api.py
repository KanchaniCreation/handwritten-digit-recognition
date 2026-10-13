"""
Backend tests — run from the project root:

    python -m unittest discover -s backend/tests -v

They need NO database and NO trained model: PostgreSQL is replaced by an
in-memory fake repository and the TensorFlow model by a tiny stub, so you
can run them anywhere (and in CI).
"""

import io
import os
import sys
import types
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

# psycopg2 may not be installed where tests run — stub it before db.py imports it.
if "psycopg2" not in sys.modules:
    try:
        import psycopg2  # noqa: F401
    except ImportError:
        fake = types.ModuleType("psycopg2")
        fake.pool = types.ModuleType("psycopg2.pool")
        fake.pool.PoolError = Exception
        fake.pool.SimpleConnectionPool = object
        fake.OperationalError = Exception
        sys.modules["psycopg2"] = fake
        sys.modules["psycopg2.pool"] = fake.pool

import numpy as np
from flask import Flask
from PIL import Image, ImageDraw, ImageFont

from model import model_loader
from services import prediction_service
from routes import predict_routes
from routes.predict_routes import predict_bp
from routes.health_routes import health_bp
from database.db import DatabaseError


# ---------- helpers ----------

def digit_png(text="7", invert=False, size=280, with_alpha=False) -> io.BytesIO:
    """Renders a digit with PIL. Default: black ink on white (like paper)."""
    bg, fg = (0, 255) if invert else (255, 0)
    img = Image.new("L", (size, size), bg)
    try:
        font = ImageFont.load_default(size=int(size * 0.6))
    except TypeError:
        font = ImageFont.load_default()
    ImageDraw.Draw(img).text((size * 0.3, size * 0.15), text, fill=fg, font=font)
    if with_alpha:
        img = img.convert("RGBA")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


class StubModel:
    """Always 'sees' a 3, with 90% confidence."""
    def predict(self, x, verbose=0):
        assert x.shape == (1, 28, 28, 1)
        p = np.full((1, 10), 0.1 / 9, dtype=np.float32)
        p[0, 3] = 0.9
        return p


class FakeRepo:
    def __init__(self):
        self.rows, self.next_id = {}, 1

    def insert(self, digit, conf, source="upload", probabilities=None):
        row = {"id": self.next_id, "predicted_digit": digit, "confidence": conf,
               "created_at": datetime.now(timezone.utc).isoformat(), "source": source,
               "corrected_digit": None, "probabilities": probabilities}
        self.rows[self.next_id] = row
        self.next_id += 1
        return row

    def list(self, limit=50, offset=0, digit=None):
        rows = sorted(self.rows.values(), key=lambda r: -r["id"])
        if digit is not None:
            rows = [r for r in rows if r["predicted_digit"] == digit]
        return rows[offset:offset + limit]

    def get(self, i):
        return self.rows.get(i)

    def delete(self, i):
        return self.rows.pop(i, None) is not None

    def clear(self):
        n = len(self.rows)
        self.rows.clear()
        return n

    def feedback(self, i, d):
        if i not in self.rows:
            return None
        self.rows[i]["corrected_digit"] = d
        return self.rows[i]

    def stats(self):
        return {"total_predictions": len(self.rows)}


# ---------- preprocessing ----------

class PreprocessingTests(unittest.TestCase):
    def test_output_shape_and_range(self):
        x = prediction_service.preprocess_image(digit_png("7"))
        self.assertEqual(x.shape, (1, 28, 28, 1))
        self.assertEqual(x.dtype, np.float32)
        self.assertGreaterEqual(x.min(), 0.0)
        self.assertLessEqual(x.max(), 1.0)
        self.assertAlmostEqual(float(x.max()), 1.0, places=3)

    def test_ink_polarity_does_not_matter(self):
        a = prediction_service.preprocess_image(digit_png("4", invert=False))
        b = prediction_service.preprocess_image(digit_png("4", invert=True))
        self.assertLess(float(np.abs(a - b).mean()), 0.01)

    def test_digit_is_centred_and_fits_box(self):
        x = prediction_service.preprocess_image(digit_png("8"))[0, :, :, 0]
        ys, xs = np.nonzero(x)
        self.assertGreaterEqual(ys.min(), 3)
        self.assertLessEqual(ys.max(), 24)
        cy = (x.sum(axis=1) * np.arange(28)).sum() / x.sum()
        cx = (x.sum(axis=0) * np.arange(28)).sum() / x.sum()
        self.assertAlmostEqual(cy, 14, delta=2.0)
        self.assertAlmostEqual(cx, 14, delta=2.0)

    def test_transparent_png_is_supported(self):
        x = prediction_service.preprocess_image(digit_png("2", with_alpha=True))
        self.assertEqual(x.shape, (1, 28, 28, 1))

    def test_blank_image_rejected(self):
        buf = io.BytesIO()
        Image.new("L", (100, 100), 255).save(buf, format="PNG")
        buf.seek(0)
        with self.assertRaises(prediction_service.PredictionError):
            prediction_service.preprocess_image(buf)

    def test_garbage_rejected(self):
        with self.assertRaises(prediction_service.PredictionError):
            prediction_service.preprocess_image(io.BytesIO(b"not an image"))


# ---------- API ----------

class ApiTests(unittest.TestCase):
    def setUp(self):
        self.repo = FakeRepo()
        self._orig = {}
        patches = {
            "insert_prediction": self.repo.insert,
            "get_all_predictions": self.repo.list,
            "get_prediction_by_id": self.repo.get,
            "delete_prediction": self.repo.delete,
            "delete_all_predictions": self.repo.clear,
            "set_corrected_digit": self.repo.feedback,
            "get_stats": self.repo.stats,
        }
        for name, fn in patches.items():
            self._orig[name] = getattr(predict_routes, name)
            setattr(predict_routes, name, fn)

        model_loader._model = StubModel()
        app = Flask(__name__)
        app.register_blueprint(predict_bp)
        app.register_blueprint(health_bp)
        self.client = app.test_client()

    def tearDown(self):
        for name, fn in self._orig.items():
            setattr(predict_routes, name, fn)
        model_loader._model = None

    def post_digit(self, **kw):
        data = {"image": (digit_png("3"), "d.png")}
        data.update(kw)
        return self.client.post("/predict", data=data, content_type="multipart/form-data")

    def test_predict_success_and_saved(self):
        r = self.post_digit(source="canvas")
        self.assertEqual(r.status_code, 200)
        j = r.get_json()
        self.assertTrue(j["success"])
        self.assertEqual(j["predicted_digit"], 3)
        self.assertAlmostEqual(j["confidence"], 0.9, places=3)
        self.assertEqual(j["top3"][0]["digit"], 3)
        self.assertEqual(len(j["probabilities"]), 10)
        self.assertEqual(j["id"], 1)
        self.assertTrue(j["saved"])
        self.assertEqual(self.repo.rows[1]["source"], "canvas")

    def test_predict_still_returns_when_db_down(self):
        def boom(*a, **k):
            raise DatabaseError("down")
        predict_routes.insert_prediction = boom
        j = self.post_digit().get_json()
        self.assertTrue(j["success"])
        self.assertIsNone(j["id"])
        self.assertFalse(j["saved"])

    def test_predict_validation_errors(self):
        self.assertEqual(self.client.post("/predict").status_code, 400)
        r = self.client.post("/predict", data={"image": (io.BytesIO(b"hello"), "x.txt")},
                             content_type="multipart/form-data")
        self.assertEqual(r.status_code, 415)
        r = self.client.post("/predict", data={"image": (io.BytesIO(b"hello"), "x.png")},
                             content_type="multipart/form-data")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.post_digit(source="bogus").status_code, 400)
        r = self.client.post("/predict", data={"image": (io.BytesIO(b""), "x.png")},
                             content_type="multipart/form-data")
        self.assertEqual(r.status_code, 400)

    def test_predict_blank_image_is_422(self):
        buf = io.BytesIO()
        Image.new("L", (50, 50), 255).save(buf, format="PNG")
        buf.seek(0)
        r = self.client.post("/predict", data={"image": (buf, "blank.png")},
                             content_type="multipart/form-data")
        self.assertEqual(r.status_code, 422)

    def test_predict_model_unavailable_is_503(self):
        model_loader._model = None
        self.assertEqual(self.post_digit().status_code, 503)

    def test_history_get_delete(self):
        for _ in range(3):
            self.post_digit()
        j = self.client.get("/predictions").get_json()
        self.assertEqual(j["count"], 3)
        self.assertEqual(j["predictions"][0]["id"], 3)  # newest first
        self.assertEqual(self.client.get("/predictions?limit=1").get_json()["count"], 1)
        self.assertEqual(self.client.get("/predictions?digit=5").get_json()["count"], 0)
        self.assertEqual(self.client.get("/predictions?limit=abc").status_code, 400)
        self.assertEqual(self.client.get("/predictions?digit=11").status_code, 400)

        self.assertEqual(self.client.get("/predictions/2").status_code, 200)
        self.assertEqual(self.client.get("/predictions/99").status_code, 404)
        self.assertEqual(self.client.delete("/predictions/2").status_code, 200)
        self.assertEqual(self.client.delete("/predictions/2").status_code, 404)
        j = self.client.delete("/predictions").get_json()
        self.assertEqual(j["deleted_count"], 2)

    def test_feedback(self):
        self.post_digit()
        r = self.client.patch("/predictions/1/feedback", json={"corrected_digit": 8})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["prediction"]["corrected_digit"], 8)
        self.assertEqual(self.client.patch("/predictions/1/feedback", json={"corrected_digit": 10}).status_code, 400)
        self.assertEqual(self.client.patch("/predictions/1/feedback", json={"corrected_digit": True}).status_code, 400)
        self.assertEqual(self.client.patch("/predictions/1/feedback", json={}).status_code, 400)
        self.assertEqual(self.client.patch("/predictions/99/feedback", json={"corrected_digit": 1}).status_code, 404)

    def test_stats_and_csv_routes_not_shadowed_by_id_route(self):
        self.post_digit()
        self.assertEqual(self.client.get("/predictions/stats").get_json()["stats"]["total_predictions"], 1)
        r = self.client.get("/predictions/export")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data.decode().startswith("id,predicted_digit"))
        self.assertIn("text/csv", r.content_type)

    def test_health(self):
        from routes import health_routes
        orig = health_routes.ping
        try:
            health_routes.ping = lambda: True
            j = self.client.get("/health").get_json()
            self.assertEqual(j["status"], "ok")
            health_routes.ping = lambda: False
            r = self.client.get("/health")
            self.assertEqual(r.status_code, 503)
            self.assertEqual(r.get_json()["status"], "degraded")
        finally:
            health_routes.ping = orig


if __name__ == "__main__":
    unittest.main()
