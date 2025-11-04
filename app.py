import os
import re
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

# --- Config ---
load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "dev-key")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/wishwall")

engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)

# --- One-time table bootstrap (idempotent) ---
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS wishes (
    id SERIAL PRIMARY KEY,
    name VARCHAR(80),
    message VARCHAR(280) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
"""

with engine.begin() as conn:
    conn.exec_driver_sql(CREATE_TABLE_SQL)

# --- Helpers ---
def _sanitize_name(raw: str) -> str:
    """Allow letters, numbers, spaces, and a few punctuation marks."""
    safe = re.sub(r"[^a-zA-Z0-9 \-_'.,]", "", raw or "")
    return safe.strip()[:80]

def _sanitize_message(raw: str) -> str:
    msg = (raw or "").strip()
    return msg[:280]

# --- Routes ---
@app.route("/", methods=["GET"])
def index():
    """Show the submission form + recent wishes."""
    with engine.connect() as conn:
        wishes = conn.execute(
            text("SELECT id, name, message, created_at FROM wishes ORDER BY created_at DESC LIMIT 20;")
        ).mappings().all()
    return render_template("index.html", wishes=wishes)

@app.route("/wish", methods=["POST"])
def create_wish():
    """Handle form submission and persist to Postgres."""
    name = _sanitize_name(request.form.get("name", ""))
    message = _sanitize_message(request.form.get("message", ""))

    if not message:
        flash("Please write a short wish (1–280 characters).", "error")
        return redirect(url_for("index"))

    try:
        with engine.begin() as conn:
            conn.execute(
                text("INSERT INTO wishes (name, message, created_at) VALUES (:name, :message, :created_at)"),
                {"name": name or None, "message": message, "created_at": datetime.utcnow()},
            )
        flash("Your wish has been posted ✨", "success")
    except OperationalError:
        flash("Database connection failed. Check your DATABASE_URL and that Postgres is running.", "error")

    return redirect(url_for("index"))

if __name__ == "__main__":
    # Run with: python app.py
    app.run(host="0.0.0.0", port=5000, debug=bool(int(os.getenv("FLASK_DEBUG", "1"))))
