import hmac
import logging
import os
import sqlite3
import threading
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
# Standardfragen bei jedem Start abgleichen (fehlende werden ergaenzt). SEED_SYNC=0 schaltet das ab.
SEED_SYNC = os.environ.get("SEED_SYNC", "1") != "0"

# Alte Datenbank, die beim ersten Start automatisch uebernommen wird
LEGACY_DB_PATHS = [
    p for p in (
        os.environ.get("LEGACY_DB_PATH", ""),
        os.path.join(BASE_DIR, "jeopardy.db"),
    ) if p
]

ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
WEAK_PASSWORDS = {"", "technik2016", "bitte-aendern", "admin", "password", "changeme"}
ADMIN_ENABLED = ADMIN_PASSWORD not in WEAK_PASSWORDS
DEBUG_MODE = os.environ.get("FLASK_DEBUG", "0") == "1"
DEFAULT_POINT_LEVELS = "100,200,300,400,500"
VALID_GRADES = {"6", "7", "8", "9", "10"}

# Themes (Auswahl im Adminbereich, gilt global). Die Farben stehen in static/styles.css.
DEFAULT_THEME = "nacht"
THEMES = {
    "nacht": {"label": "Nacht", "desc": "Dunkles Blau-Violett (Standard)", "bar": "#0b1020",
              "swatches": ["#0b1020", "#6d7cff", "#ffd166"]},
    "hell": {"label": "Hell", "desc": "Klar und hell, gut bei Tageslicht", "bar": "#f4f6fb",
             "swatches": ["#f4f6fb", "#4f46e5", "#b45309"]},
    "auto": {"label": "Automatisch", "desc": "Folgt dem Ger\u00e4t (hell/dunkel)", "bar": "#0b1020",
             "swatches": ["#0b1020", "#f4f6fb", "#6d7cff"]},
    "neon": {"label": "Neon", "desc": "Cyberpunk mit Leuchteffekt", "bar": "#07040f",
             "swatches": ["#07040f", "#ff2bd6", "#00f0ff"]},
    "sunset": {"label": "Sunset", "desc": "Warm: Orange und Pink", "bar": "#1a0f14",
               "swatches": ["#1a0f14", "#ff7a45", "#ff4d8d"]},
    "wald": {"label": "Wald", "desc": "Ruhiges Gr\u00fcn", "bar": "#0a1511",
             "swatches": ["#0a1511", "#34d399", "#a3e635"]},
    "kontrast": {"label": "Hoher Kontrast", "desc": "Schwarz, Wei\u00df, Gelb \u2013 gut lesbar", "bar": "#000000",
                 "swatches": ["#000000", "#ffee00", "#ffffff"]},
}
ASSET_V = str(int(time.time()))

DEFAULT_CATEGORIES = [
    ("Werkstoffe und Produkte", "Bildungsplan Technik 2016: Werkstoffe und Produkte"),
    ("Systeme und Prozesse", "Bildungsplan Technik 2016: Systeme und Prozesse"),
    ("Mensch und Technik", "Produktion, Versorgung/Entsorgung, Bautechnik, Mobilitaet"),
    ("Medienbildung & Digitalisierung", "Digitale Technik, IT-Sicherheit, Medienbildung"),
]

if not ADMIN_ENABLED:
    log.warning(
        "ADMIN_PASSWORD fehlt oder ist unsicher/Standard - Adminbereich ist DEAKTIVIERT. "
        "Bitte ADMIN_PASSWORD setzen."
    )

# einfacher Brute-Force-Schutz (pro IP, im Speicher)
MAX_FAILS = 5
LOCK_SECONDS = 300
_fails = {}

_init_lock = threading.Lock()
_seeded = False


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


def migrate_legacy_db():
    """Uebernimmt eine alte jeopardy.db einmalig nach DB_PATH (nur lesend auf der alten Datei)."""
    if os.path.exists(DB_PATH):
        return
    for legacy in LEGACY_DB_PATHS:
        if not os.path.isfile(legacy):
            continue
        if os.path.abspath(legacy) == os.path.abspath(DB_PATH):
            continue
        src = None
        dst = None
        try:
            src = sqlite3.connect(legacy)
            count = src.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
            if count <= 0:
                log.info("Alte DB %s enthaelt keine Fragen - uebersprungen.", legacy)
                continue
            os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
            dst = sqlite3.connect(DB_PATH)
            src.backup(dst)
            dst.commit()
            log.info("Alte DB %s mit %d Fragen nach %s uebernommen.", legacy, count, DB_PATH)
            return
        except Exception as exc:
            log.warning("Uebernahme der alten DB %s fehlgeschlagen: %s", legacy, exc)
            if dst is not None:
                dst.close()
                dst = None
            if os.path.exists(DB_PATH):
                try:
                    os.remove(DB_PATH)
                except OSError:
                    pass
        finally:
            if src is not None:
                src.close()
            if dst is not None:
                dst.close()


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


def create_schema(conn):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS categories ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "name TEXT NOT NULL, "
        "description TEXT)"
    )
    conn.execute(
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
    conn.execute(
        "CREATE TABLE IF NOT EXISTS settings ("
        "key TEXT PRIMARY KEY, "
        "value TEXT NOT NULL)"
    )


def exec_script_tolerant(conn, text):
    """Fuehrt ein SQL-Skript Statement fuer Statement aus und ueberspringt Fehler."""
    buf = ""
    errors = 0
    for line in text.splitlines(keepends=True):
        buf += line
        if sqlite3.complete_statement(buf):
            try:
                conn.execute(buf)
            except sqlite3.Error:
                errors += 1
            buf = ""
    return errors


def sync_seed_questions(conn):
    """Ergaenzt fehlende Standardfragen aus den Seed-Dateien (Abgleich ueber den Fragetext).

    Die Seed-Dateien laufen in einer temporaeren In-Memory-DB (ihre DELETE-Statements
    treffen so nie die echte Datenbank). Eigene und bearbeitete Fragen bleiben unangetastet.
    """
    cur = conn.cursor()
    existing = {r[0] for r in cur.execute("SELECT question_text FROM questions")}
    cat_ids = {r["name"]: r["id"] for r in cur.execute("SELECT id, name FROM categories")}
    added = 0
    for seed_file in SEED_FILES:
        if not os.path.exists(seed_file):
            log.warning("Seed-Datei fehlt: %s", seed_file)
            continue
        with open(seed_file, "r", encoding="utf-8") as f:
            text = f.read()
        scratch = sqlite3.connect(":memory:")
        scratch.row_factory = sqlite3.Row
        create_schema(scratch)
        for idx, (name, desc) in enumerate(DEFAULT_CATEGORIES, start=1):
            scratch.execute(
                "INSERT INTO categories (id, name, description) VALUES (?, ?, ?)",
                (idx, name, desc),
            )
        errors = exec_script_tolerant(scratch, text)
        if errors:
            log.warning("Seed-Datei %s: %d Statements uebersprungen.", seed_file, errors)
        scratch_cats = {r["id"]: r["name"] for r in scratch.execute("SELECT id, name FROM categories")}
        rows = scratch.execute(
            "SELECT category_id, grade_level, competence_area, points, question_text, "
            "answer_text, hint FROM questions ORDER BY id"
        ).fetchall()
        for q in rows:
            if q["question_text"] in existing:
                continue
            cat_name = scratch_cats.get(q["category_id"])
            if cat_name is None:
                continue
            cid = cat_ids.get(cat_name)
            if cid is None:
                cur.execute("INSERT INTO categories (name, description) VALUES (?, ?)", (cat_name, ""))
                cid = cur.lastrowid
                cat_ids[cat_name] = cid
            cur.execute(
                "INSERT INTO questions "
                "(category_id, grade_level, competence_area, points, question_text, answer_text, hint) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (cid, q["grade_level"], q["competence_area"], q["points"],
                 q["question_text"], q["answer_text"], q["hint"]),
            )
            existing.add(q["question_text"])
            added += 1
        scratch.close()
    conn.commit()
    log.info("Seed-Abgleich fertig: %d fehlende Standardfragen ergaenzt.", added)


def init_db():
    global _seeded
    with _init_lock:
        migrate_legacy_db()
        conn = get_db()
        create_schema(conn)

        if conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0] == 0:
            conn.executemany(
                "INSERT INTO categories (name, description) VALUES (?, ?)", DEFAULT_CATEGORIES
            )
        conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('shuffle_enabled', '1')")
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES ('point_levels', ?)",
            (DEFAULT_POINT_LEVELS,),
        )
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES ('theme', ?)",
            (DEFAULT_THEME,),
        )
        conn.commit()

        if SEED_SYNC and not _seeded:
            try:
                sync_seed_questions(conn)
            except Exception:
                conn.rollback()
                log.exception("Seed-Abgleich fehlgeschlagen")
            _seeded = True
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


def get_theme():
    value = get_setting("theme", DEFAULT_THEME)
    return value if value in THEMES else DEFAULT_THEME


@app.context_processor
def inject_theme():
    try:
        current = get_theme()
    except sqlite3.Error:
        current = DEFAULT_THEME
    return {
        "theme": current,
        "theme_bar": THEMES[current]["bar"],
        "themes": THEMES,
        "asset_v": ASSET_V,
    }


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
        new_theme = request.form.get("theme", "")
        if new_theme in THEMES:
            set_setting("theme", new_theme)
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
