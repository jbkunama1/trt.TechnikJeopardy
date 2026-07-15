from flask import Flask, render_template, request, redirect, url_for, jsonify
import sqlite3
import os

app = Flask(__name__, static_folder="static", template_folder="templates")
DB_PATH = os.path.join(os.path.dirname(__file__), "jeopardy.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


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

    conn.close()


@app.route("/")
def index():
    return redirect(url_for("play"))


@app.route("/play")
def play():
    init_db()
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT c.id AS category_id, c.name AS category_name, "
        "q.id AS question_id, q.points, q.question_text "
        "FROM categories c "
        "LEFT JOIN questions q ON q.category_id = c.id "
        "ORDER BY c.id, q.points"
    )
    rows = cur.fetchall()
    conn.close()

    gameboard = {}
    for row in rows:
        cid = row["category_id"]
        if cid not in gameboard:
            gameboard[cid] = {"category_name": row["category_name"], "questions": []}
        if row["question_id"] is not None:
            gameboard[cid]["questions"].append(
                {"id": row["question_id"], "points": row["points"], "text": row["question_text"]}
            )

    return render_template("play.html", gameboard=gameboard)


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


@app.route("/admin/new", methods=["GET", "POST"])
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
def admin_delete(qid):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM questions WHERE id = ?", (qid,))
    conn.commit()
    conn.close()
    return redirect(url_for("admin"))


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
