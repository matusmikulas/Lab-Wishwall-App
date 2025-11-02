import os
import re
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, render_template, render_template_string, request, redirect, url_for, flash
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

INDEX_TEMPLATE_HEAD = """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Wish Wall</title>
    <style>
      body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 2rem; }
      .container { max-width: 700px; margin: 0 auto; }
      header { margin-bottom: 1.5rem; }
      form { display: grid; gap: .75rem; margin-bottom: 1.5rem; }
      input, textarea, button { font-size: 1rem; padding: .6rem .7rem; }
      textarea { min-height: 90px; resize: vertical; }
      .flash { padding: .6rem .8rem; border-radius: 6px; margin-bottom: 1rem; }
      .flash.success { background: #e6ffed; border: 1px solid #b7ebc6; }
      .flash.error   { background: #ffecec; border: 1px solid #ffb3b3; }
      .wish { border: 1px solid #eee; border-radius: 8px; padding: .9rem; margin-bottom: .8rem; }
      .wish small { color: #666; display:block; margin-top:.25rem; }
      footer { color:#777; margin-top:2rem; font-size:.9rem; }
    </style>
  </head>
  <body>
    <div class="container">
      <header>
        <h1>✨ Wish Wall</h1>
        <p>Drop a short wish and see it appear below.</p>
      </header>

      {# flashed messages - same semantics as your base.html #}
      {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
          {% for category, msg in messages %}
            <div class="flash {{ category }}">{{ msg }}</div>
          {% endfor %}
        {% endif %}
      {% endwith %}

      <form method="POST" action="{{ url_for('create_wish') }}">
        <label for="name">Your name (optional)</label>
        <input id="name" name="name" maxlength="80" placeholder="e.g., Peter" />

        <label for="message">Your wish</label>
        <textarea id="message" name="message" maxlength="280" required placeholder="I wish..."></textarea>

        <button type="submit">Post wish</button>
      </form>

      <section aria-label="Recent wishes">
"""
INDEX_TEMPLATE_FOOT = """
      </section>

      <footer>
        Built with Flask, Jinja2, and PostgreSQL.
      </footer>
    </div>
  </body>
</html>
"""

def render_wish(wish):
    return f'<article> <div>{ wish.message }</div> <small> { wish.name }, { wish.created_at.strftime("%Y-%m-%d %H:%M") if wish.created_at is not None else "" } </small> </article>'

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
    INDEX_TEMPLATE = INDEX_TEMPLATE_HEAD
    for wish in wishes:
        INDEX_TEMPLATE += render_wish(wish)
    INDEX_TEMPLATE += INDEX_TEMPLATE_FOOT
    return render_template_string(INDEX_TEMPLATE)

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
#            conn.execute(
#                text("INSERT INTO wishes (name, message, created_at) VALUES (:name, :message, :created_at)"),
#                {"name": name or None, "message": message, "created_at": datetime.utcnow()},
#            )
            sql = f"""
                INSERT INTO wishes (name, message, created_at)
                VALUES ('{name}', '{message}', '{datetime.utcnow()}');
            """
            conn.exec_driver_sql(sql)
        flash("Your wish has been posted ✨", "success")
    except OperationalError:
        flash("Database connection failed. Check your DATABASE_URL and that Postgres is running.", "error")

    return redirect(url_for("index"))

if __name__ == "__main__":
    # Run with: python app.py
    app.run(host="0.0.0.0", port=5000, debug=bool(int(os.getenv("FLASK_DEBUG", "1"))))
