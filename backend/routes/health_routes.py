"""
routes/health_routes.py
-------------------------
GET /health -> is the API up, is the model loaded, is the database reachable?
"""

from flask import Blueprint, jsonify

from model.model_loader import is_loaded
from database.db import ping

health_bp = Blueprint("health", __name__)


@health_bp.route("/health", methods=["GET"])
def health():
    model_ok = is_loaded()
    db_ok = ping()
    status = "ok" if (model_ok and db_ok) else "degraded"
    return jsonify({
        "success": True,
        "status": status,
        "model_loaded": model_ok,
        "database_connected": db_ok,
    }), (200 if status == "ok" else 503)
