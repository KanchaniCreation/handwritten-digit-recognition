"""
app.py
-------
Flask application entry point.

Run from the project root (with the venv activated):
    python backend/app.py

Startup sequence (deliberately in this order):
1. Load environment variables from .env
2. Load the trained model into memory ONCE (see model/model_loader.py)
3. Initialize the PostgreSQL connection pool (see database/db.py)
   - if either the model or the database fails to load/connect, we
     print a clear error and exit immediately rather than starting an
     API that can't actually do its job
4. Register route blueprints
5. Start the Flask dev server
"""

import os
import sys

from flask import Flask, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# Add this directory to sys.path so "model.*" / "services.*" / "routes.*"
# imports work regardless of the working directory the script is run from.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from model.model_loader import load_model, ModelLoadError  # noqa: E402
from database.db import init_pool, DatabaseError  # noqa: E402
from routes.health_routes import health_bp  # noqa: E402
from routes.predict_routes import predict_bp  # noqa: E402


def create_app():
    load_dotenv()

    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_UPLOAD_BYTES", 2 * 1024 * 1024)) + 64 * 1024
    CORS(app)  # allows the Java Swing client (or anything else) to call this API

    # ---- Load the model once, at startup ----
    default_model_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "ml", "digit_model.keras"
    )
    model_path = os.getenv("MODEL_PATH", default_model_path)
    model_path = os.path.abspath(model_path)

    try:
        load_model(model_path)
        print(f"Model loaded successfully from: {model_path}")
    except ModelLoadError as exc:
        print(f"FATAL: {exc}")
        sys.exit(1)

    # ---- Initialize the database connection pool, at startup ----
    try:
        init_pool()
        print("Database connection pool initialized successfully.")
    except DatabaseError as exc:
        print(f"FATAL: {exc}")
        sys.exit(1)

    # ---- Register routes ----
    app.register_blueprint(health_bp)
    app.register_blueprint(predict_bp)

    # ---- Global error handlers (never leak stack traces to the client) ----
    @app.errorhandler(404)
    def not_found(_error):
        return jsonify({"success": False, "error": "Endpoint not found."}), 404

    @app.errorhandler(413)
    def too_large(_error):
        return jsonify({"success": False, "error": "Request too large."}), 413

    @app.errorhandler(405)
    def method_not_allowed(_error):
        return jsonify({"success": False, "error": "Method not allowed on this endpoint."}), 405

    @app.errorhandler(500)
    def internal_error(_error):
        return jsonify({"success": False, "error": "Internal server error."}), 500

    return app


if __name__ == "__main__":
    flask_app = create_app()
    port = int(os.getenv("API_PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    flask_app.run(host="0.0.0.0", port=port, debug=debug)
