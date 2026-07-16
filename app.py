from flask import Flask, render_template, request, redirect, url_for, jsonify, Response, send_from_directory
from functools import wraps
import sqlite3
import os

app = Flask(__name__, static_folder="static", template_folder="templates")
DB_PATH = os.path.join(os.path.dirname(__file__), "jeopardy.db")
BASE_DIR = os.path.dirname(__file__)
SEED_FILES = [
    os.path.join(BASE_DIR, "seed_questions.sql"),
    os.path.join(BASE_DIR, "seed_questions_extra.sql"),
    os.path.join(BASE_DIR, "seed_questions_more.sql"),
    os.path.join(BASE_DIR, "seed_questions_round3.sql"),
]

ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "technik2016")
DEBUG_MODE = os.environ.get("FLASK_DEBUG", "0") == "1"

DEFAULT_POINT_LEVELS = "100,200,300,400,500"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def check_auth(username, password):
    return username == ADMIN_USER and password == ADMIN_PASSWORD


def authenticate():
    return Response(
        "Zugriff auf den Adminbereich erfordert eine Anmeldung.",
        401,
        {"WWW-Authenticate": 'Basic realm="trt.TechnikJeopardy Admin"'},
    )


def requires_admin_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated


def run_seed_files(conn):
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS c FROM questions")
    if cur.fetchone()["c"] > 0:
        return

    for seed_file in SEED_FILES:
        if os.path.exists(seed_file):
            with open(seed_file, "r", encoding="utf-8") as f:
                conn.executescript(f.read())
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
            "INSERT INTO categories (name, description) VALUES (?, ?)",
            categories,
        )
        conn.commit()

    cur.execute("SELECT COUNT(*) AS c FROM settings WHERE key = 'shuffle_enabled'")
    if cur.fetchone()["c"] == 0:
        cur.execute("INSERT INTO settings (key, value) VALUES ('shuffle_enabled', '1')")
    cur.execute("SELECT COUNT(*) AS c FROM settings WHERE key = 'point_levels'")
    if cur.fetchone()["c"] == 0:
        cur.execute(
            "INSERT INTO settings (key, value) VALUES ('point_levels', ?)",
            (DEFAULT_POINT_LEVELS,),
        )
    conn.commit()

    run_seed_files(conn)
    conn.close()


def get_setting(key, default=""):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cur.fetchone()
    conn.close()
    return row["value"] if row else default


def set_setting(key, value):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
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


@app.route("/")
def index():
    return redirect(url_for("play"))


@app.route("/trtTechnikJeopardy_Logo.png")
def logo():
    return send_from_directory(BASE_DIR, "trtTechnikJeopardy_Logo.png")


@app.route("/play")
def play():
    init_db()
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT id, name FROM categories ORDER BY id")
    categories = cur.fetchall()

    point_levels = get_point_levels()
    shuffle = is_shuffle_enabled()
    order_clause = "ORDER BY RANDOM() LIMIT 1" if shuffle else "ORDER BY id LIMIT 1"

    gameboard = {}
    for cat in categories:
        cid = cat["id"]
        gameboard[cid] = {"category_name": cat["name"], "questions": []}
        for pts in point_levels:
            cur.execute(
                "SELECT id, points, question_text, grade_level "
                "FROM questions WHERE category_id = ? AND points = ? " + order_clause,
                (cid, pts),
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
        root_logo_path="/trtTechnikJeopardy_Logo.png",
    )


@app.route("/api/question/<int:qid>")
def api_question(qid):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM questions WHERE id = ?", (qid,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return jsonify({"error": "not found"}), 404
    return jsonify(
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
        cleaned = [p.strip() for p in raw_levels.split(",") if p.strip().isdigit()]
        point_levels = ",".join(cleaned) if cleaned else DEFAULT_POINT_LEVELS

        set_setting("shuffle_enabled", shuffle_enabled)
        set_setting("point_levels", point_levels)
        return redirect(url_for("admin_settings"))

    current_shuffle = is_shuffle_enabled()
    current_levels = get_setting("point_levels", DEFAULT_POINT_LEVELS)
    return render_template(
        "admin_settings.html",
        shuffle_enabled=current_shuffle,
        point_levels=current_levels,
    )


@app.route("/admin/new", methods=["GET", "POST"])
@requires_admin_auth
def admin_new():
    init_db()
    conn = get_db()
    cur = conn.cursor()
    if request.method == "POST":
        category_id = request.form["category_id"]
        question_text = request.form["question_text"]
        answer_text = request.form["answer_text"]
        points = int(request.form["points"])
        grade_level = request.form.get("grade_level", "")
        competence_area = request.form.get("competence_area", "")
        hint = request.form.get("hint", "")
        cur.execute(
            "INSERT INTO questions "
            "(category_id, question_text, answer_text, points, grade_level, competence_area, hint) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (category_id, question_text, answer_text, points, grade_level, competence_area, hint),
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
        category_id = request.form["category_id"]
        question_text = request.form["question_text"]
        answer_text = request.form["answer_text"]
        points = int(request.form["points"])
        grade_level = request.form.get("grade_level", "")
        competence_area = request.form.get("competence_area", "")
        hint = request.form.get("hint", "")
        cur.execute(
            "UPDATE questions SET category_id = ?, question_text = ?, answer_text = ?, "
            "points = ?, grade_level = ?, competence_area = ?, hint = ? WHERE id = ?",
            (category_id, question_text, answer_text, points, grade_level, competence_area, hint, qid),
        )
        conn.commit()
        conn.close()
        return redirect(url_for("admin"))

    cur.execute("SELECT * FROM questions WHERE id = ?", (qid,))
    question = cur.fetchone()
    cur.execute("SELECT id, name FROM categories ORDER BY name")
    categories = cur.fetchall()
    conn.close()
    return render_template("admin_edit.html", question=question, categories=categories)


@app.route("/admin/delete/<int:qid>", methods=["POST"])
@requires_admin_auth
def admin_delete(qid):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM questions WHERE id = ?", (qid,))
    conn.commit()
    conn.close()
    return redirect(url_for("admin"))


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=DEBUG_MODE)