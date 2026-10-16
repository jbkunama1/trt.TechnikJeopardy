"""Import und Export von Fragen (JSON und CSV)."""
import csv
import io
import json
import re

MAX_ROWS = 2000
MAX_TEXT = 2000
GRADE_RE = re.compile(r"^\d{1,2}(?:-\d{1,2})?$")
POINTS_RE = re.compile(r"^\d{1,6}$")

FIELDS = ["kategorie", "punkte", "klassenstufe", "kompetenzbereich", "frage", "antwort", "hinweis"]

ALIASES = {
    "kategorie": "category", "category": "category",
    "punkte": "points", "points": "points", "punktzahl": "points",
    "klassenstufe": "grade_level", "klasse": "grade_level",
    "grade_level": "grade_level", "grade": "grade_level",
    "kompetenzbereich": "competence_area", "kompetenz": "competence_area",
    "competence_area": "competence_area",
    "frage": "question_text", "fragetext": "question_text",
    "question": "question_text", "question_text": "question_text",
    "antwort": "answer_text", "antworttext": "answer_text",
    "answer": "answer_text", "answer_text": "answer_text",
    "hinweis": "hint", "hint": "hint",
}

TEMPLATE_ROWS = [
    {
        "kategorie": "Werkstoffe und Produkte", "punkte": 100, "klassenstufe": "7-8",
        "kompetenzbereich": "3.3.1 Werkstoffe und Produkte",
        "frage": "Nenne drei typische metallische Werkstoffe.",
        "antwort": "Stahl, Aluminium, Kupfer.", "hinweis": "",
    },
    {
        "kategorie": "Systeme und Prozesse", "punkte": 300, "klassenstufe": "9",
        "kompetenzbereich": "3.3.2 Systeme und Prozesse",
        "frage": "Was ist ein Aktor?",
        "antwort": "Ein Bauteil, das eine Wirkung ausübt, z. B. ein Motor.",
        "hinweis": "Gegenstück zum Sensor",
    },
    {
        "kategorie": "Medienbildung & Digitalisierung", "punkte": 500, "klassenstufe": "10",
        "kompetenzbereich": "Leitperspektive Medienbildung",
        "frage": "Was versteht man unter einem Algorithmus?",
        "antwort": "Eine eindeutige Schrittfolge zur Lösung eines Problems.", "hinweis": "",
    },
]


class ImportFormatError(ValueError):
    """Datei kann nicht als JSON oder CSV gelesen werden."""


def decode_bytes(raw):
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")


def _norm_key(key):
    return str(key).replace("\ufeff", "").strip().lower().replace(" ", "_").replace("-", "_")


def detect_format(filename, text):
    name = (filename or "").lower()
    if name.endswith(".json"):
        return "json"
    if name.endswith(".csv"):
        return "csv"
    return "json" if text.lstrip()[:1] in ("{", "[") else "csv"


def parse_json(text):
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise ImportFormatError("Ungueltiges JSON: %s" % exc)
    if isinstance(data, dict):
        for key in ("fragen", "questions"):
            if key in data:
                data = data[key]
                break
        else:
            raise ImportFormatError('Im JSON fehlt der Schluessel "fragen" (Liste der Fragen).')
    if not isinstance(data, list):
        raise ImportFormatError('"fragen" muss eine Liste sein.')
    if not data:
        raise ImportFormatError("Die Datei enthaelt keine Fragen.")
    if len(data) > MAX_ROWS:
        raise ImportFormatError("Zu viele Eintraege (maximal %d pro Import)." % MAX_ROWS)
    return [("Eintrag %d" % i, item) for i, item in enumerate(data, start=1)]


def parse_csv(text):
    lines = text.splitlines()
    if not lines or not lines[0].strip():
        raise ImportFormatError("Die CSV-Datei ist leer oder hat keine Kopfzeile.")
    head = lines[0]
    delim = max((";", ",", "\t"), key=head.count)
    if head.count(delim) == 0:
        raise ImportFormatError(
            "Kopfzeile nicht erkannt. Erwartet werden Spalten getrennt durch ; oder , "
            "(z. B. kategorie;punkte;klassenstufe;kompetenzbereich;frage;antwort;hinweis)."
        )
    reader = csv.DictReader(io.StringIO(text, newline=""), delimiter=delim)
    rows = []
    try:
        for rec in reader:
            clean = {}
            for k, v in rec.items():
                if k is None:
                    continue
                clean[k] = "" if v is None else v
            if not any(str(v).strip() for v in clean.values()):
                continue
            rows.append(("Zeile %d" % reader.line_num, clean))
            if len(rows) > MAX_ROWS:
                raise ImportFormatError("Zu viele Zeilen (maximal %d pro Import)." % MAX_ROWS)
    except csv.Error as exc:
        raise ImportFormatError("CSV konnte nicht gelesen werden: %s" % exc)
    if not rows:
        raise ImportFormatError("Die CSV-Datei enthaelt keine Fragen.")
    return rows


def parse(text, filename=""):
    if detect_format(filename, text) == "json":
        return parse_json(text)
    return parse_csv(text)


def _normalize_row(raw):
    if not isinstance(raw, dict):
        return None
    out = {}
    for key, value in raw.items():
        canon = ALIASES.get(_norm_key(key))
        if canon is None:
            continue
        out[canon] = "" if value is None else str(value).strip()
    return out


def _validate(row):
    category = row.get("category", "")
    if not category:
        return None, "Kategorie fehlt."
    points_raw = row.get("points", "")
    if not POINTS_RE.match(points_raw) or int(points_raw) <= 0:
        return None, "Punkte muessen eine positive ganze Zahl sein (gefunden: '%s')." % points_raw
    question = row.get("question_text", "")
    answer = row.get("answer_text", "")
    if not question:
        return None, "Frage fehlt."
    if not answer:
        return None, "Antwort fehlt."
    grade = row.get("grade_level", "")
    if grade and (not GRADE_RE.match(grade) or len(grade) > 10):
        return None, "Klassenstufe muss z. B. 7 oder 7-8 sein (gefunden: '%s')." % grade
    competence = row.get("competence_area", "")
    if len(competence) > 200:
        return None, "Kompetenzbereich ist laenger als 200 Zeichen."
    hint = row.get("hint", "")
    if max(len(question), len(answer), len(hint)) > MAX_TEXT:
        return None, "Frage, Antwort oder Hinweis ist laenger als %d Zeichen." % MAX_TEXT
    return {
        "category": category,
        "points": int(points_raw),
        "grade_level": grade,
        "competence_area": competence,
        "question_text": question,
        "answer_text": answer,
        "hint": hint,
    }, None


def run_import(conn, rows, dry_run=False, allow_new_categories=False):
    result = {
        "total": len(rows), "imported": 0, "duplicates": 0,
        "errors": [], "new_categories": [], "dry_run": dry_run,
    }
    cats = {r[1].casefold(): r[0] for r in conn.execute("SELECT id, name FROM categories")}
    existing = {r[0] for r in conn.execute("SELECT question_text FROM questions")}
    pending = set()
    try:
        for label, raw in rows:
            row = _normalize_row(raw)
            if row is None:
                result["errors"].append((label, "Eintrag ist kein Objekt mit Feldern."))
                continue
            clean, message = _validate(row)
            if message:
                result["errors"].append((label, message))
                continue
            if clean["question_text"] in existing:
                result["duplicates"] += 1
                continue
            key = clean["category"].casefold()
            if key not in cats and key not in pending:
                if not allow_new_categories:
                    result["errors"].append((
                        label,
                        "Kategorie '%s' existiert nicht (Schreibweise pruefen oder "
                        "'Neue Kategorien anlegen' aktivieren)." % clean["category"],
                    ))
                    continue
                result["new_categories"].append(clean["category"])
                if dry_run:
                    pending.add(key)
                else:
                    cur = conn.execute(
                        "INSERT INTO categories (name, description) VALUES (?, '')",
                        (clean["category"],),
                    )
                    cats[key] = cur.lastrowid
            if not dry_run:
                conn.execute(
                    "INSERT INTO questions "
                    "(category_id, grade_level, competence_area, points, question_text, answer_text, hint) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (cats[key], clean["grade_level"], clean["competence_area"], clean["points"],
                     clean["question_text"], clean["answer_text"], clean["hint"]),
                )
            existing.add(clean["question_text"])
            result["imported"] += 1
        if not dry_run:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    return result


def export_rows(conn):
    cur = conn.execute(
        "SELECT c.name AS kategorie, q.points AS punkte, q.grade_level AS klassenstufe, "
        "q.competence_area AS kompetenzbereich, q.question_text AS frage, "
        "q.answer_text AS antwort, q.hint AS hinweis "
        "FROM questions q JOIN categories c ON q.category_id = c.id "
        "ORDER BY c.id, q.points, q.id"
    )
    cols = [d[0] for d in cur.description]
    rows = []
    for rec in cur.fetchall():
        data = dict(zip(cols, tuple(rec)))
        rows.append({k: ("" if data[k] is None else data[k]) for k in FIELDS})
    return rows


def to_json(rows):
    return json.dumps({"fragen": rows}, ensure_ascii=False, indent=2) + "\n"


def to_csv(rows):
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=FIELDS, delimiter=";", lineterminator="\r\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: row.get(k, "") for k in FIELDS})
    return "\ufeff" + buf.getvalue()
