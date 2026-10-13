"""
routes/predict_routes.py
--------------------------
POST   /predict                       run a prediction on an uploaded image, store it, return it
GET    /predictions                   history, newest first (?limit=&offset=&digit=)
GET    /predictions/<id>              one stored prediction
DELETE /predictions/<id>              delete one prediction
DELETE /predictions                   clear the whole history
PATCH  /predictions/<id>/feedback     tell the system what the digit really was
GET    /predictions/stats             aggregate statistics
GET    /predictions/export            download history as CSV
"""

import csv
import io

from flask import Blueprint, request, jsonify, Response

from services.prediction_service import predict_digit, PredictionError
from model.model_loader import ModelLoadError
from utils.validators import validate_image_upload, ValidationError
from database.predictions_repository import (
    insert_prediction,
    get_all_predictions,
    get_prediction_by_id,
    delete_prediction,
    delete_all_predictions,
    set_corrected_digit,
    get_stats,
)
from database.db import DatabaseError

predict_bp = Blueprint("predict", __name__)


def _err(message, status):
    return jsonify({"success": False, "error": message}), status


@predict_bp.route("/predict", methods=["POST"])
def predict():
    try:
        image_file, source = validate_image_upload(request.files, request.form)
    except ValidationError as exc:
        return _err(exc.message, exc.status_code)

    try:
        result = predict_digit(image_file.stream)
    except ModelLoadError:
        return _err("Model is unavailable. Please try again later.", 503)
    except PredictionError as exc:
        return _err(str(exc), 422)
    except Exception:
        return _err("An unexpected error occurred while predicting.", 500)

    # If the DB write fails we still return the prediction (the ML result is
    # valid either way) but flag that history-saving failed.
    prediction_id = None
    created_at = None
    try:
        saved = insert_prediction(
            result["predicted_digit"], result["confidence"],
            source=source, probabilities=result["probabilities"],
        )
        prediction_id = saved["id"]
        created_at = saved["created_at"]
    except DatabaseError as exc:
        print(f"WARNING: prediction succeeded but DB save failed: {exc}")

    return jsonify({
        "success": True,
        "predicted_digit": result["predicted_digit"],
        "confidence": result["confidence"],
        "top3": result["top3"],
        "probabilities": result["probabilities"],
        "id": prediction_id,
        "created_at": created_at,
        "saved": prediction_id is not None,
    }), 200


def _int_arg(name, default, minimum, maximum):
    raw = request.args.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ValidationError(f"Query parameter '{name}' must be an integer.", 400)
    if not (minimum <= value <= maximum):
        raise ValidationError(f"Query parameter '{name}' must be between {minimum} and {maximum}.", 400)
    return value


@predict_bp.route("/predictions", methods=["GET"])
def list_predictions():
    try:
        limit = _int_arg("limit", 50, 1, 500)
        offset = _int_arg("offset", 0, 0, 10_000_000)
        digit = _int_arg("digit", None, 0, 9)
    except ValidationError as exc:
        return _err(exc.message, exc.status_code)

    try:
        predictions = get_all_predictions(limit=limit, offset=offset, digit=digit)
    except DatabaseError:
        return _err("Could not fetch prediction history.", 503)

    return jsonify({"success": True, "count": len(predictions), "predictions": predictions}), 200


@predict_bp.route("/predictions/stats", methods=["GET"])
def prediction_stats():
    try:
        stats = get_stats()
    except DatabaseError:
        return _err("Could not compute statistics.", 503)
    return jsonify({"success": True, "stats": stats}), 200


@predict_bp.route("/predictions/export", methods=["GET"])
def export_predictions():
    try:
        rows = get_all_predictions(limit=500)
    except DatabaseError:
        return _err("Could not export prediction history.", 503)

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id", "predicted_digit", "confidence", "corrected_digit", "source", "created_at"])
    for r in rows:
        writer.writerow([r["id"], r["predicted_digit"], r["confidence"],
                         r["corrected_digit"] if r["corrected_digit"] is not None else "",
                         r["source"], r["created_at"]])
    return Response(
        buf.getvalue(), mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=predictions.csv"},
    )


@predict_bp.route("/predictions/<int:prediction_id>", methods=["GET"])
def get_prediction(prediction_id):
    try:
        prediction = get_prediction_by_id(prediction_id)
    except DatabaseError:
        return _err("Could not fetch prediction.", 503)

    if prediction is None:
        return _err(f"No prediction found with id {prediction_id}.", 404)
    return jsonify({"success": True, "prediction": prediction}), 200


@predict_bp.route("/predictions/<int:prediction_id>", methods=["DELETE"])
def remove_prediction(prediction_id):
    try:
        deleted = delete_prediction(prediction_id)
    except DatabaseError:
        return _err("Could not delete prediction.", 503)

    if not deleted:
        return _err(f"No prediction found with id {prediction_id}.", 404)
    return jsonify({"success": True, "deleted_id": prediction_id}), 200


@predict_bp.route("/predictions", methods=["DELETE"])
def clear_predictions():
    try:
        count = delete_all_predictions()
    except DatabaseError:
        return _err("Could not clear prediction history.", 503)
    return jsonify({"success": True, "deleted_count": count}), 200


@predict_bp.route("/predictions/<int:prediction_id>/feedback", methods=["PATCH"])
def feedback(prediction_id):
    body = request.get_json(silent=True) or {}
    corrected = body.get("corrected_digit")
    if isinstance(corrected, bool) or not isinstance(corrected, int) or not (0 <= corrected <= 9):
        return _err("JSON body must contain 'corrected_digit' as an integer 0-9.", 400)

    try:
        updated = set_corrected_digit(prediction_id, corrected)
    except DatabaseError:
        return _err("Could not save feedback.", 503)

    if updated is None:
        return _err(f"No prediction found with id {prediction_id}.", 404)
    return jsonify({"success": True, "prediction": updated}), 200
