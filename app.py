import hmac
import logging
import os
import sqlite3
import time
from functools import wraps
from urllib.parse import urlparse

from flask import (
    Flask, Response, abort, jsonify, redirect, render_template, request,
    send_from_directory, url_for,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder="static", template_folder="templates")
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("technikjeopardy")

# DB liegt im Unterordner data/ (Docker: Volume auf /app/data)
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "data", "jeopardy.db"))
SEED_FILES = [
    os.path.join(BASE_DIR, "seed_questions.sql"),
    os.path.join(BASE_DIR, "seed_questions_extra.sql"),
    os.path.join(BASE_DIR, "seed_questions_more.sql"),
    os.path.join(BASE_DIR, "seed_questions_round3.sql"),
]

ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
WEAK_PASSWORDS = {"", "technik2016", "bitte-aendern", "admin", "password", "changeme"}
ADMIN_ENABLED = ADMIN_PASSWORD not in WEAK_PASSWORDS
DEBUG_MODE = os.environ.get("FLASK_DEBUG", "0") == "1"
DEFAULT_POINT_LEVELS = "100,200,300,400,500"
VALID_GRADES = {"6", "7", "8", "9", "10"}

if not ADMIN_ENABLED:
    log.warning(
        "ADMIN_PASSWORD fehlt oder ist unsicher/Standard - Adminbereich ist DEAKTIVIERT. "
        "Bitte ADMIN_PASSWORD setzen."
    )

# einfacher Brute-Force-Schutz (pro IP, im Speicher)
MAX_FAILS = 5
LOCK_SECONDS = 300
_fails = {}


def client_ip():
    return request.remote_addr or "unknown"


def is_locked(ip):
    entry = _fails.get(ip)
    if not entry:
        return False
    count, first = entry
    if time.time() - first > LOCK_SECONDS:
        _fails.pop(ip, None)
        return False
    return count >= MAX_FAILS


def register_fail(ip):
    count, first = _fails.get(ip, (0, time.time()))
    if time.time() - first > LOCK_SECONDS:
        count, first = 0, time.time()
    _fails[ip] = (count + 1, first)


def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def check_auth(username, password):
    user_ok = hmac.compare_digest(username.encode("utf-8"), ADMIN_USER.encode("utf-8"))
    pw_ok = hmac.compare_digest(password.encode("utf-8"), ADMIN_PASSWORD.encode("utf-8"))
    return user_ok and pw_ok


def authenticate():
    return Response(
        "Zugriff auf den Adminbereich erfordert eine Anmeldung.",
        401,
        {"WWW-Authenticate": 'Basic realm="trt.TechnikJeopardy Admin"'},
    )


def requires_admin_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not ADMIN_ENABLED:
            return Response(
                "Adminbereich deaktiviert: ADMIN_PASSWORD ist nicht (sicher) gesetzt.",
                503,
            )
        ip = client_ip()
        if is_locked(ip):
            return Response("Zu viele Fehlversuche. Bitte spaeter erneut versuchen.", 429)
        auth = request.authorization
        if not auth or not check_auth(auth.username or "", auth.password or ""):
            if auth:
                register_fail(ip)
                log.warning("Fehlgeschlagener Admin-Login von %s", ip)
            return authenticate()
        _fails.pop(ip, None)
        return f(*args, **kwargs)
    return decorated


@app.before_request
def same_origin_for_writes():
    # CSRF-Schutz ohne Token: schreibende Requests muessen vom eigenen Host kommen
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        source = request.headers.get("Origin") or request.headers.get("Referer")
        if not source or urlparse(source).netloc != request.host:
            abort(403)


@app.after_request
def security_headers(resp):
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "same-origin")
    return resp


def run_seed_files(conn):
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS c FROM questions")
    if cur.fetchone()["c"] > 0:
        return
    for seed_file in SEED_FILES:
        if os.path.exists(seed_file):
            with open(seed_file, "r", encoding="utf-8") as f:
                conn.executescript(f.read())
        else:
            log.warning("Seed-Datei fehlt: %s", seed_file)
    conn.commit()


def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "CREATE TABLE IF NOT EXISTS categories ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "name TEXT NOT NULL, "
        "description TEXT)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS questions ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "category_id INTEGER NOT NULL, "
        "grade_level TEXT, "
        "competence_area TEXT, "
        "points INTEGER NOT NULL, "
        "question_text TEXT NOT NULL, "
        "answer_text TEXT NOT NULL, "
        "hint TEXT, "
        "FOREIGN KEY (category_id) REFERENCES categories(id))"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS settings ("
        "key TEXT PRIMARY KEY, "
        "value TEXT NOT NULL)"
    )

    cur.execute("SELECT COUNT(*) AS c FROM categories")
    if cur.fetchone()["c"] == 0:
        categories = [
            ("Werkstoffe und Produkte", "Bildungsplan Technik 2016: Werkstoffe und Produkte"),
            ("Systeme und Prozesse", "Bildungsplan Technik 2016: Systeme und Prozesse"),
            ("Mensch und Technik", "Produktion, Versorgung/Entsorgung, Bautechnik, Mobilitaet"),
            ("Medienbildung & Digitalisierung", "Digitale Technik, IT-Sicherheit, Medienbildung"),
        ]
        cur.executemany(
            "INSERT INTO categories (name, description) VALUES (?, ?)", categories
        )
        conn.commit()

    cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('shuffle_enabled', '1')")
    cur.execute(
        "INSERT OR IGNORE INTO settings (key, value) VALUES ('point_levels', ?)",
        (DEFAULT_POINT_LEVELS,),
    )
    conn.commit()

    run_seed_files(conn)
    conn.close()


def get_setting(key, default=""):
    conn = get_db()
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default


def set_setting(key, value):
    conn = get_db()
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    conn.commit()
    conn.close()


def get_point_levels():
    raw = get_setting("point_levels", DEFAULT_POINT_LEVELS)
    try:
        levels = [int(p.strip()) for p in raw.split(",") if p.strip()]
        return levels if levels else [int(p) for p in DEFAULT_POINT_LEVELS.split(",")]
    except ValueError:
        return [int(p) for p in DEFAULT_POINT_LEVELS.split(",")]


def is_shuffle_enabled():
    return get_setting("shuffle_enabled", "1") == "1"


def parse_question_form(conn):
    """Validiert das Fragenformular. Gibt dict zurueck oder bricht mit 400 ab."""
    try:
        category_id = int(request.form["category_id"])
        points = int(request.form["points"])
    except (KeyError, ValueError):
        abort(400)
    if points <= 0 or points > 100000:
        abort(400)
    if not conn.execute("SELECT 1 FROM categories WHERE id = ?", (category_id,)).fetchone():
        abort(400)
    question_text = request.form.get("question_text", "").strip()
    answer_text = request.form.get("answer_text", "").strip()
    if not question_text or not answer_text:
        abort(400)
    return {
        "category_id": category_id,
        "points": points,
        "question_text": question_text,
        "answer_text": answer_text,
        "grade_level": request.form.get("grade_level", "").strip()[:10],
        "competence_area": request.form.get("competence_area", "").strip()[:200],
        "hint": request.form.get("hint", "").strip(),
    }


@app.route("/")
def index():
    return redirect(url_for("play"))


@app.route("/healthz")
def healthz():
    return jsonify({"status": "ok"})


@app.route("/trtTechnikJeopardy_Logo.png")
def logo():
    return send_from_directory(BASE_DIR, "trtTechnikJeopardy_Logo.png")


@app.route("/play")
def play():
    init_db()
    grade = request.args.get("grade", "").strip()
    if grade not in VALID_GRADES:
        grade = ""

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM categories ORDER BY id")
    categories = cur.fetchall()

    point_levels = get_point_levels()
    order_clause = "ORDER BY RANDOM() LIMIT 1" if is_shuffle_enabled() else "ORDER BY id LIMIT 1"

    # Klassenfilter serverseitig: Einzelklasse ('7') und Bereiche ('7-8') werden erkannt
    grade_sql, grade_params = "", []
    if grade:
        grade_sql = " AND (grade_level = ? OR grade_level LIKE ? OR grade_level LIKE ?)"
        grade_params = [grade, grade + "-%", "%-" + grade]

    gameboard = {}
    for cat in categories:
        cid = cat["id"]
        gameboard[cid] = {"category_name": cat["name"], "questions": []}
        for pts in point_levels:
            cur.execute(
                "SELECT id, points, question_text, grade_level "
                "FROM questions WHERE category_id = ? AND points = ?"
                + grade_sql + " " + order_clause,
                [cid, pts] + grade_params,
            )
            row = cur.fetchone()
            if row:
                gameboard[cid]["questions"].append(
                    {
                        "id": row["id"],
                        "points": row["points"],
                        "text": row["question_text"],
                        "grade_level": row["grade_level"],
                    }
                )

    conn.close()
    return render_template(
        "play.html",
        gameboard=gameboard,
        selected_grade=grade,
        root_logo_path="/trtTechnikJeopardy_Logo.png",
    )


@app.route("/api/question/<int:qid>")
def api_question(qid):
    conn = get_db()
    row = conn.execute("SELECT * FROM questions WHERE id = ?", (qid,)).fetchone()
    conn.close()
    if not row:
        return jsonify({"error": "not found"}), 404
    resp = jsonify(
        {
            "id": row["id"],
            "question_text": row["question_text"],
            "answer_text": row["answer_text"],
            "points": row["points"],
            "grade_level": row["grade_level"],
            "competence_area": row["competence_area"],
            "hint": row["hint"],
        }
    )
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.route("/admin")
@requires_admin_auth
def admin():
    init_db()
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT q.id, q.question_text, q.answer_text, q.points, "
        "q.grade_level, q.competence_area, c.name AS category_name "
        "FROM questions q JOIN categories c ON q.category_id = c.id "
        "ORDER BY c.name, q.points"
    )
    questions = cur.fetchall()
    cur.execute("SELECT id, name FROM categories ORDER BY name")
    categories = cur.fetchall()
    conn.close()
    return render_template("admin.html", questions=questions, categories=categories)


@app.route("/admin/settings", methods=["GET", "POST"])
@requires_admin_auth
def admin_settings():
    init_db()
    if request.method == "POST":
        shuffle_enabled = "1" if request.form.get("shuffle_enabled") == "on" else "0"
        raw_levels = request.form.get("point_levels", DEFAULT_POINT_LEVELS)
        cleaned = [p.strip() for p in raw_levels.split(",") if p.strip().isdigit() and int(p.strip()) > 0]
        point_levels = ",".join(cleaned) if cleaned else DEFAULT_POINT_LEVELS
        set_setting("shuffle_enabled", shuffle_enabled)
        set_setting("point_levels", point_levels)
        return redirect(url_for("admin_settings"))

    return render_template(
        "admin_settings.html",
        shuffle_enabled=is_shuffle_enabled(),
        point_levels=get_setting("point_levels", DEFAULT_POINT_LEVELS),
    )


@app.route("/admin/new", methods=["GET", "POST"])
@requires_admin_auth
def admin_new():
    init_db()
    conn = get_db()
    cur = conn.cursor()
    if request.method == "POST":
        d = parse_question_form(conn)
        cur.execute(
            "INSERT INTO questions "
            "(category_id, question_text, answer_text, points, grade_level, competence_area, hint) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (d["category_id"], d["question_text"], d["answer_text"], d["points"],
             d["grade_level"], d["competence_area"], d["hint"]),
        )
        conn.commit()
        conn.close()
        return redirect(url_for("admin"))

    cur.execute("SELECT id, name FROM categories ORDER BY name")
    categories = cur.fetchall()
    conn.close()
    return render_template("admin_new.html", categories=categories)


@app.route("/admin/edit/<int:qid>", methods=["GET", "POST"])
@requires_admin_auth
def admin_edit(qid):
    init_db()
    conn = get_db()
    cur = conn.cursor()
    if request.method == "POST":
        d = parse_question_form(conn)
        cur.execute(
            "UPDATE questions SET category_id = ?, question_text = ?, answer_text = ?, "
            "points = ?, grade_level = ?, competence_area = ?, hint = ? WHERE id = ?",
            (d["category_id"], d["question_text"], d["answer_text"], d["points"],
             d["grade_level"], d["competence_area"], d["hint"], qid),
        )
        conn.commit()
        conn.close()
        return redirect(url_for("admin"))

    cur.execute("SELECT * FROM questions WHERE id = ?", (qid,))
    question = cur.fetchone()
    if not question:
        conn.close()
        abort(404)
    cur.execute("SELECT id, name FROM categories ORDER BY name")
    categories = cur.fetchall()
    conn.close()
    return render_template("admin_edit.html", question=question, categories=categories)


@app.route("/admin/delete/<int:qid>", methods=["POST"])
@requires_admin_auth
def admin_delete(qid):
    conn = get_db()
    conn.execute("DELETE FROM questions WHERE id = ?", (qid,))
    conn.commit()
    conn.close()
    return redirect(url_for("admin"))


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=DEBUG_MODE)
