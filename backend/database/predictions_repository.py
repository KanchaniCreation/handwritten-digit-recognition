"""
database/predictions_repository.py
-------------------------------------
All SQL for the 'predictions' table lives here — this is the
"repository" layer, so that Flask routes never write raw SQL
directly. Every query below is parameterized (using %s placeholders
that psycopg2 fills in safely) — never string concatenation — to
prevent SQL injection.
"""

import json

from database.db import get_connection, release_connection, DatabaseError

_COLUMNS = "id, predicted_digit, confidence, created_at, source, corrected_digit, probabilities"


def _run(fn, error_message: str):
    """Runs fn(cursor) on a pooled connection with commit/rollback handling."""
    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            result = fn(cur)
        conn.commit()
        return result
    except DatabaseError:
        raise
    except Exception as exc:
        if conn:
            conn.rollback()
        raise DatabaseError(f"{error_message}: {exc}") from exc
    finally:
        release_connection(conn)


def insert_prediction(predicted_digit: int, confidence: float,
                      source: str = "upload", probabilities=None) -> dict:
    """Inserts a new prediction row and returns it."""
    probs_json = json.dumps(probabilities) if probabilities is not None else None

    def work(cur):
        cur.execute(
            f"""
            INSERT INTO predictions (predicted_digit, confidence, source, probabilities)
            VALUES (%s, %s, %s, %s)
            RETURNING {_COLUMNS};
            """,
            (predicted_digit, confidence, source, probs_json),
        )
        return cur.fetchone()

    return _row_to_dict(_run(work, "Failed to insert prediction"))


def get_all_predictions(limit: int = 50, offset: int = 0, digit=None) -> list:
    """Returns the most recent predictions, newest first (optionally filtered by digit)."""
    def work(cur):
        if digit is None:
            cur.execute(
                f"SELECT {_COLUMNS} FROM predictions ORDER BY created_at DESC, id DESC LIMIT %s OFFSET %s;",
                (limit, offset),
            )
        else:
            cur.execute(
                f"SELECT {_COLUMNS} FROM predictions WHERE predicted_digit = %s "
                f"ORDER BY created_at DESC, id DESC LIMIT %s OFFSET %s;",
                (digit, limit, offset),
            )
        return cur.fetchall()

    return [_row_to_dict(r) for r in _run(work, "Failed to fetch predictions")]


def get_prediction_by_id(prediction_id: int):
    """Returns a single prediction dict, or None if no row matches."""
    def work(cur):
        cur.execute(f"SELECT {_COLUMNS} FROM predictions WHERE id = %s;", (prediction_id,))
        return cur.fetchone()

    row = _run(work, f"Failed to fetch prediction {prediction_id}")
    return _row_to_dict(row) if row else None


def delete_prediction(prediction_id: int) -> bool:
    """Deletes one prediction. Returns True if a row was deleted."""
    def work(cur):
        cur.execute("DELETE FROM predictions WHERE id = %s;", (prediction_id,))
        return cur.rowcount > 0

    return _run(work, f"Failed to delete prediction {prediction_id}")


def delete_all_predictions() -> int:
    """Clears the whole history. Returns the number of rows removed."""
    def work(cur):
        cur.execute("DELETE FROM predictions;")
        return cur.rowcount

    return _run(work, "Failed to clear predictions")


def set_corrected_digit(prediction_id: int, corrected_digit: int):
    """Stores user feedback (what the digit really was). Returns the row or None."""
    def work(cur):
        cur.execute(
            f"UPDATE predictions SET corrected_digit = %s WHERE id = %s RETURNING {_COLUMNS};",
            (corrected_digit, prediction_id),
        )
        return cur.fetchone()

    row = _run(work, f"Failed to update prediction {prediction_id}")
    return _row_to_dict(row) if row else None


def get_stats() -> dict:
    """Aggregate numbers for the dashboard / stats endpoint."""
    def work(cur):
        cur.execute("SELECT COUNT(*), COALESCE(AVG(confidence), 0) FROM predictions;")
        total, avg_conf = cur.fetchone()

        cur.execute("SELECT predicted_digit, COUNT(*) FROM predictions GROUP BY predicted_digit;")
        counts = {int(d): int(c) for d, c in cur.fetchall()}

        cur.execute(
            "SELECT COUNT(*), COALESCE(SUM(CASE WHEN corrected_digit = predicted_digit THEN 1 ELSE 0 END), 0) "
            "FROM predictions WHERE corrected_digit IS NOT NULL;"
        )
        reviewed, correct = cur.fetchone()
        return total, avg_conf, counts, reviewed, correct

    total, avg_conf, counts, reviewed, correct = _run(work, "Failed to compute stats")
    return {
        "total_predictions": int(total),
        "average_confidence": round(float(avg_conf), 4),
        "digit_counts": {str(d): counts.get(d, 0) for d in range(10)},
        "reviewed_predictions": int(reviewed),
        "feedback_accuracy": round(int(correct) / int(reviewed), 4) if reviewed else None,
    }


def _row_to_dict(row) -> dict:
    probs = json.loads(row[6]) if row[6] else None
    return {
        "id": row[0],
        "predicted_digit": row[1],
        "confidence": float(row[2]),
        "created_at": row[3].isoformat(),
        "source": row[4],
        "corrected_digit": row[5],
        "probabilities": probs,
    }
