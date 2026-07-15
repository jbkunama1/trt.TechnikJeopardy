# trt.TechnikJeopardy

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
![GitHub last commit](https://img.shields.io/github/last-commit/jbkunama1/trt.TechnikJeopardy?style=flat-square)
![GitHub repo size](https://img.shields.io/github/repo-size/jbkunama1/trt.TechnikJeopardy?style=flat-square)
![GitHub issues](https://img.shields.io/github/issues/jbkunama1/trt.TechnikJeopardy?style=flat-square)
![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg)
![Flask](https://img.shields.io/badge/Flask-backend-lightgrey.svg)
![Docker](https://img.shields.io/badge/Docker-supported-0db7ed.svg)
![GitHub Pages](https://img.shields.io/badge/GitHub%20Pages-docs-success.svg)
![TruffleHog](https://img.shields.io/badge/Security-TruffleHog%20Scan-critical.svg)

Jeopardy-Webapp fuer den Technikunterricht (Bildungsplan Baden-Wuerttemberg 2016, Sekundarstufe I).
Modernes, responsives Spielfeld fuer den Klassenraum, Admin-Oberflaeche mit SQLite-Anbindung, Fragenpool mit 100 Fragen.

---

## Inhaltsverzeichnis

- [Features](#features)
- [Live-Demo / GitHub Pages](#live-demo--github-pages)
- [Installation (lokal)](#installation-lokal)
- [Installation mit Docker / Portainer](#installation-mit-docker--portainer)
- [Fragenpool importieren](#fragenpool-importieren)
- [Adminbereich](#adminbereich)
- [Fragen erweitern](#fragen-erweitern)
- [GitHub Pages einrichten](#github-pages-einrichten)
- [Sicherheit: TruffleHog](#sicherheit-trufflehog)
- [Lizenz](#lizenz)

---

## Features

- **Jeopardy-Spieloberflaeche**: Kategorien und Punktefelder auf einem responsiven Board (Desktop / Tablet / Smartphone).
- **Admin-Bereich**: Uebersicht, Filter, Anlegen/Bearbeiten/Loeschen von Fragen.
- **SQLite-Anbindung**: Alle Fragen liegen in einer lokalen `jeopardy.db`.
- **Fragenpool**: 100 vorbereitete Fragen nach Bildungsplan Technik 2016 BW (Werkstoffe und Produkte, Systeme und Prozesse, Mensch und Technik, Medienbildung/Digitalisierung).
- **Docker/Portainer-Support**: Fertiger `docker-compose.yml`-Stack.
- **Sicherheits-Check**: TruffleHog-Workflow scannt das Repo automatisch auf Secrets.

---

## Live-Demo / GitHub Pages

GitHub Pages hostet nur statische Inhalte, kein Flask-Backend. In diesem Projekt dient GitHub Pages als
Landing Page mit Projektbeschreibung und Links:

- Projektseite: `https://jbkunama1.github.io/trt.TechnikJeopardy/`
- Repo: `https://github.com/jbkunama1/trt.TechnikJeopardy`

---

## Installation (lokal)

### Voraussetzungen

- Python 3.11 oder neuer
- `git`

### Schritte

```bash
git clone https://github.com/jbkunama1/trt.TechnikJeopardy.git
cd trt.TechnikJeopardy

python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -r requirements.txt

python app.py
```

Die App laeuft danach unter `http://localhost:5000`:

- Spielfeld: `http://localhost:5000/play`
- Adminbereich: `http://localhost:5000/admin`

Beim ersten Start wird `jeopardy.db` automatisch angelegt (leer, nur mit den vier Grundkategorien).
Zum Befuellen mit dem 100er-Fragenpool siehe [Fragenpool importieren](#fragenpool-importieren).

---

## Installation mit Docker / Portainer

### Docker Compose (CLI)

```bash
docker compose up -d
```

Der Service ist danach unter `http://<HOST>:5000` erreichbar.

### Portainer-Stack

1. In Portainer zu **Stacks** wechseln.
2. **Add stack** waehlen, Namen z. B. `trt-technikjeopardy` vergeben.
3. Inhalt von `docker-compose.yml` in den Web-Editor einfuegen.
4. **Deploy the stack** klicken.
5. Nach dem Deploy ist die App unter `http://<SERVER-IP>:5000` erreichbar.

Die `docker-compose.yml`:

```yaml
version: "3.9"

services:
  trt-technikjeopardy:
    image: python:3.11-slim
    container_name: trt-technikjeopardy
    working_dir: /app
    volumes:
      - ./:/app
    ports:
      - "5000:5000"
    command: sh -c "pip install -r requirements.txt && python app.py"
    environment:
      - FLASK_ENV=production
      - PORT=5000
    restart: unless-stopped
```

---

## Fragenpool importieren

Im Repo liegt `seed_questions.sql` mit 100 vorbereiteten Fragen. Import in eine frische `jeopardy.db`:

```bash
# einmalig App starten, damit jeopardy.db und die Tabellen existieren
python app.py &
sleep 2
kill %1

# Seed-Daten importieren
sqlite3 jeopardy.db < seed_questions.sql
```

Alternativ direkt beim ersten Aufbau:

```bash
rm -f jeopardy.db
python -c "from app import init_db; init_db()"
sqlite3 jeopardy.db < seed_questions.sql
```

---

## Adminbereich

Der Adminbereich laeuft unter `/admin` und bietet:

- Tabellarische Uebersicht aller Fragen mit Kategorie, Punkten, Klassenstufe und Kompetenzbereich.
- Formulare zum Anlegen (`/admin/new`) und Bearbeiten (`/admin/edit/<id>`) von Fragen.
- Loeschfunktion (`/admin/delete/<id>`) je Frage.

> Hinweis: In dieser Basisversion ist der Adminbereich ungeschuetzt. Fuer den produktiven Einsatz
> empfiehlt sich ein einfacher Passwortschutz (z. B. Flask-BasicAuth oder ein Reverse-Proxy mit
> Login davor).

---

## Fragen erweitern

So fuegst du neue Fragen hinzu oder passt bestehende an:

1. Adminbereich oeffnen: `http://localhost:5000/admin`.
2. Auf **Neue Frage anlegen** klicken.
3. Felder ausfuellen:
   - **Kategorie**: z. B. "Werkstoffe und Produkte", "Systeme und Prozesse", "Mensch und Technik", "Medienbildung & Digitalisierung".
   - **Punkte**: z. B. 100, 200, 300, 400, 500.
   - **Fragentext** / **Antworttext**.
   - **Klassenstufe**: z. B. "7-8" oder "9-10".
   - **Kompetenzbereich**: z. B. "3.3.1 Werkstoffe und Produkte" (Bezug zum Bildungsplan Technik 2016 BW).
   - **Hinweis** (optional): zusaetzlicher Tipp fuer Schueler.
4. **Speichern** klicken - die Frage erscheint sofort im Spielfeld unter `/play`.

Bestehende Fragen aendern: In der Adminuebersicht auf **Bearbeiten** klicken, Werte anpassen, speichern.
Fragen loeschen: In der Adminuebersicht auf **Loeschen** klicken (mit Bestaetigung).

Neue Kategorien koennen direkt per SQL ergaenzt werden:

```sql
INSERT INTO categories (name, description) VALUES ('Neue Kategorie', 'Beschreibung');
```

---

## GitHub Pages einrichten

1. Im Repo zu **Settings > Pages** wechseln.
2. Als **Source** den Branch `main` und Ordner `/ (root)` waehlen.
3. Speichern - die Seite ist danach unter `https://jbkunama1.github.io/trt.TechnikJeopardy/` erreichbar.
4. Die Datei `index.html` im Root dient als Landing Page mit Projektbeschreibung und Links zum Repo.

---

## Sicherheit: TruffleHog

Das Repo enthaelt unter `.github/workflows/trufflehog.yml` einen automatischen Secret-Scan mit
[TruffleHog](https://github.com/trufflesecurity/trufflehog), der bei jedem Push und Pull Request laeuft.

### Lokaler Scan

```bash
git clone https://github.com/jbkunama1/trt.TechnikJeopardy.git
cd trt.TechnikJeopardy
trufflehog filesystem .
```

### GitHub Action

```yaml
name: TruffleHog Secret Scan

on:
  push:
  pull_request:

jobs:
  trufflehog:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repo
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Run TruffleHog OSS
        uses: trufflesecurity/trufflehog@v3
        with:
          extra_args: --results=verified,unknown
```

---

## Lizenz

Dieses Projekt steht unter der [MIT-Lizenz](LICENSE).
