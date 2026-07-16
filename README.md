# trt.TechnikJeopardy

![trt.TechnikJeopardy Logo](./trtTechnikJeopardy_Logo.png)

Jeopardy-Webapp fuer den Technikunterricht (Bildungsplan Baden-Wuerttemberg 2016, Sekundarstufe I). Modernes, responsives Spielfeld fuer den Klassenraum, Admin-Oberflaeche mit SQLite-Anbindung, Fragenpool mit 750 Fragen fuer Klasse 6 bis 10.

## Inhaltsverzeichnis

- [Features](#features)
- [Installation (lokal)](#installation-lokal)
- [Installation mit Docker / Portainer](#installation-mit-docker--portainer)
- [Fragenpool](#fragenpool)
- [Adminbereich absichern](#adminbereich-absichern)
- [Sicherheitshinweise fuer den Schuleinsatz](#sicherheitshinweise-fuer-den-schuleinsatz)
- [Klassenstufen-Format](#klassenstufen-format)
- [Lizenz](#lizenz)

## Features

- **Jeopardy-Spieloberflaeche**: Kategorien und Punktefelder auf einem responsiven Board.
- **Teammodus**: Anzahl Teams festlegen, Namen vergeben, Punkte direkt im Spiel verteilen.
- **Klassenstufen-Filter**: Optionaler Filter im Team-Setup (Klasse 6-10).
- **Admin-Bereich**: Uebersicht, Anlegen/Bearbeiten/Loeschen von Fragen — durch Basic-Auth geschuetzt.
- **SQLite-Anbindung**: Alle Fragen liegen in einer lokalen `jeopardy.db`, wird beim ersten Start automatisch angelegt und befuellt.
- **Fragenpool**: 750 vorbereitete Fragen nach Bildungsplan Technik 2016 BW fuer Klasse 6 bis 10.
- **Docker/Portainer-Support**: Fertiger `docker-compose.yml`-Stack.

## Installation (lokal)

```bash
git clone https://github.com/jbkunama1/trt.TechnikJeopardy.git
cd trt.TechnikJeopardy
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Admin-Zugangsdaten setzen (siehe unten) - Pflicht fuer den Schuleinsatz!
export ADMIN_USER="dein_benutzername"
export ADMIN_PASSWORD="ein_sicheres_passwort"

python app.py
```

Die App laeuft danach unter `http://localhost:5000`:

- Spielfeld: `http://localhost:5000/play`
- Adminbereich (Login erforderlich): `http://localhost:5000/admin`

Beim ersten Start werden `jeopardy.db`, die Grundtabellen sowie beide Seed-Dateien (`seed_questions.sql`, `seed_questions_extra.sql`) automatisch importiert, sofern die Datenbank noch keine Fragen enthaelt.

## Installation mit Docker / Portainer

```bash
docker compose up -d
```

In der `docker-compose.yml` unbedingt `ADMIN_USER` und `ADMIN_PASSWORD` als Umgebungsvariablen setzen, bevor der Stack im Schulnetz laeuft.

## Fragenpool

Im Repo liegen `seed_questions.sql` (100 Fragen), `seed_questions_extra.sql` (200 Fragen, 50 je Klassenstufe 7-10), `seed_questions_more.sql` (200 Fragen: 50 fuer Klasse 6, je 30 zusaetzlich fuer Klasse 7-10) und `seed_questions_round3.sql` (250 weitere Fragen: 40 fuer Klasse 6, je ca. 52-53 fuer Klasse 7-10) mit insgesamt 750 Fragen. Der Import erfolgt automatisch bei einer frischen Datenbank.

DB bewusst neu aufbauen:

```bash
rm -f jeopardy.db
python app.py
```

## Adminbereich absichern

Der Adminbereich (`/admin`, `/admin/new`, `/admin/edit/<id>`, `/admin/delete/<id>`) ist per **HTTP Basic-Auth** geschuetzt.

Zugangsdaten werden ueber Umgebungsvariablen gesetzt:

```bash
export ADMIN_USER="dein_benutzername"
export ADMIN_PASSWORD="ein_sicheres_passwort"
```

Werden diese nicht gesetzt, greifen die Standardwerte `admin` / `technik2016` — **diese unbedingt vor dem Schuleinsatz aendern**, da sie oeffentlich in diesem Repo stehen.

## Sicherheitshinweise fuer den Schuleinsatz

- `FLASK_DEBUG` ist standardmaessig deaktiviert. Niemals `FLASK_DEBUG=1` im Schulnetz oder auf einem oeffentlich erreichbaren Server setzen — der Werkzeug-Debugger erlaubt sonst das Ausfuehren beliebigen Codes.
- Admin-Zugangsdaten (`ADMIN_USER`, `ADMIN_PASSWORD`) vor dem ersten Einsatz aendern.
- `jeopardy.db` liegt lokal und wird durch `.gitignore` nicht versioniert — Fragen bleiben so auch bei Updates per `git pull` erhalten.
- Bei Einsatz im offenen Schulnetz zusaetzlich HTTPS (z. B. per Reverse-Proxy) empfehlen.

## Klassenstufen-Format

Die 100 urspruenglichen Fragen nutzen teilweise Klassenstufen-Bereiche (`7-8`, `8-9`, `9-10`), alle 400 neuen Fragen (inkl. Klasse 6) nutzen Einzelklassen (`6`, `7`, `8`, `9`, `10`). Der Klassenstufen-Filter im Spiel (Team-Setup) beruecksichtigt beide Formate: Eine Frage mit `grade_level = "7-8"` erscheint z. B. sowohl bei Filter "Klasse 7" als auch "Klasse 8".

## Lizenz

Dieses Projekt steht unter der [MIT-Lizenz](./LICENSE).