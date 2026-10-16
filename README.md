# trt.TechnikJeopardy
[![Status](https://img.shields.io/badge/status-active-brightgreen?style=for-the-badge)](https://github.com/jbkunama1/trt.TechnikJeopardy)
[![Education](https://img.shields.io/badge/Made%20for-Sek%20I%20Technik-blue?style=for-the-badge)](https://github.com/jbkunama1/trt.TechnikJeopardy)
[![Fragen](https://img.shields.io/badge/Fragenpool-750-6f42c1?style=for-the-badge&logo=quizlet&logoColor=white)](https://github.com/jbkunama1/trt.TechnikJeopardy)
[![Bildungsplan](https://img.shields.io/badge/Bildungsplan-BW%202016-success?style=for-the-badge)](https://github.com/jbkunama1/trt.TechnikJeopardy)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)

[![Buy me a coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-ffdd00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black)](https://www.buymeacoffee.com/highfish)

![trt.TechnikJeopardy Logo](./trtTechnikJeopardy_Logo.png)

Jeopardy-Webapp fuer den Technikunterricht (Bildungsplan Baden-Wuerttemberg 2016, Sekundarstufe I). Responsives Spielfeld fuer den Klassenraum, Admin-Oberflaeche mit SQLite-Anbindung, Fragenpool mit 750 Fragen fuer Klasse 6 bis 10.

## Inhaltsverzeichnis

- [Features](#features)
- [Installation (lokal)](#installation-lokal)
- [Installation mit Docker / Portainer](#installation-mit-docker--portainer)
- [Fragenpool](#fragenpool)
- [Alte Datenbank uebernehmen](#alte-datenbank-uebernehmen)
- [Konfiguration](#konfiguration)
- [Sicherheit](#sicherheit)
- [Klassenstufen-Filter](#klassenstufen-filter)
- [Lizenz](#lizenz)

## Features

- **Jeopardy-Spieloberflaeche**: Kategorien und Punktefelder auf einem responsiven Board.
- **Teammodus**: 1-6 Teams, Namen vergeben, Punkte direkt im Spiel verteilen.
- **Klassenstufen-Filter**: Optional im Team-Setup (Klasse 6-10), serverseitig umgesetzt.
- **Admin-Bereich**: Fragen anlegen/bearbeiten/loeschen und Einstellungen (Shuffle, Punktestufen), per Basic-Auth geschuetzt.
- **SQLite**: Die Datenbank `data/jeopardy.db` wird beim ersten Start automatisch angelegt. Die Standardfragen werden bei jedem Start abgeglichen.
- **Docker/Portainer**: Fertiger Stack mit Healthcheck, gunicorn und Non-Root-User.

## Installation (lokal)

```bash
git clone https://github.com/jbkunama1/trt.TechnikJeopardy.git
cd trt.TechnikJeopardy
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Pflicht fuer den Adminbereich (ohne sicheres Passwort bleibt er deaktiviert)
export ADMIN_USER="dein_benutzername"
export ADMIN_PASSWORD="ein_sicheres_passwort"

python app.py
```

- Spielfeld: `http://localhost:5000/play`
- Adminbereich: `http://localhost:5000/admin`
- Healthcheck: `http://localhost:5000/healthz`

## Installation mit Docker / Portainer

### Docker Compose (CLI)

```bash
ADMIN_PASSWORD="ein_sicheres_passwort" docker compose up -d --build
```

Der Service ist danach unter `http://localhost:5050` erreichbar. Ohne `ADMIN_PASSWORD` bricht `docker compose` mit einer Fehlermeldung ab.

### Portainer-Stack (empfohlen)

1. In Portainer zu **Stacks** und **Add stack**.
2. Namen vergeben, z. B. `trt-technikjeopardy`.
3. **Build method**: "Repository" mit `https://github.com/jbkunama1/trt.TechnikJeopardy` und Compose-Pfad `docker-compose.yml`.
4. Unter **Environment variables** `ADMIN_USER` und `ADMIN_PASSWORD` mit eigenen, sicheren Werten setzen.
5. **Deploy the stack**.
6. Erreichbar unter `http://<server-ip>:5050`.

Die Datenbank liegt im benannten Volume `trt_jeopardy_db` (`/app/data`) und bleibt bei Neustart und Recreate erhalten.

### Update

```bash
git pull
docker compose up -d --build
```

In Portainer: Stack oeffnen, **Pull and redeploy** mit aktivierter Option "Re-build image".

## Fragenpool

Im Repo liegen `seed_questions.sql` (100 Fragen), `seed_questions_extra.sql` (200), `seed_questions_more.sql` (200) und `seed_questions_round3.sql` (250) mit insgesamt 750 Fragen.

Bei **jedem Start** gleicht die App diese Standardfragen mit der Datenbank ab: Fehlende Fragen werden ergaenzt (Abgleich ueber den Fragetext), vorhandene und eigene Fragen bleiben unveraendert. Die Seed-Dateien laufen dabei in einer temporaeren In-Memory-Datenbank, ihre `DELETE`-Statements koennen die echte Datenbank nicht treffen.

- Geloeschte Standardfragen kommen beim naechsten Start wieder. Mit `SEED_SYNC=0` schaltest du den Abgleich ab.
- Aenderst du den Text einer Standardfrage im Admin-Bereich, wird die Originalfrage beim naechsten Start zusaetzlich wieder angelegt.

DB bewusst neu aufbauen (lokal):

```bash
rm -f data/jeopardy.db
python app.py
```

## Alte Datenbank uebernehmen

Existiert `data/jeopardy.db` noch nicht, kopiert die App beim ersten Start eine alte Datenbank dorthin (die alte Datei wird nur gelesen). Gesucht wird in dieser Reihenfolge:

1. Pfad aus der Umgebungsvariable `LEGACY_DB_PATH`
2. `jeopardy.db` im App-Ordner (im Container `/app/jeopardy.db`)

Nur Datenbanken mit mindestens einer Frage werden uebernommen. Im Docker-Betrieb mountest du die alte Datei zum Beispiel read-only nach `/legacy/jeopardy.db` und setzt `LEGACY_DB_PATH=/legacy/jeopardy.db`. Nach der Uebernahme kannst du den Mount entfernen. Wurde bereits eine neue Datenbank angelegt, loeschst du `data/jeopardy.db` vor dem Neustart.

## Konfiguration

| Variable | Standard | Bedeutung |
|---|---|---|
| `ADMIN_USER` | `admin` | Benutzername fuer `/admin` |
| `ADMIN_PASSWORD` | leer | Pflicht. Leere oder bekannte Standardwerte deaktivieren den Adminbereich |
| `PORT` | `5000` | Port im Container bzw. lokal |
| `DB_PATH` | `data/jeopardy.db` | Pfad der SQLite-Datei |
| `LEGACY_DB_PATH` | leer | Pfad einer alten `jeopardy.db`, die beim ersten Start uebernommen wird |
| `SEED_SYNC` | `1` | `0` schaltet den Abgleich der Standardfragen beim Start ab |
| `FLASK_DEBUG` | `0` | Nur lokal zum Entwickeln auf `1` setzen |

## Sicherheit

- Der Adminbereich ist nur aktiv, wenn `ADMIN_PASSWORD` gesetzt und nicht unsicher ist (kein Standardpasswort).
- Passwortpruefung zeitkonstant, nach 5 Fehlversuchen pro IP 5 Minuten Sperre.
- Schreibende Requests werden nur akzeptiert, wenn Origin/Referer zum eigenen Host passen (CSRF-Schutz). Ein Reverse-Proxy muss den `Host`-Header unveraendert weitergeben.
- Basic-Auth sendet Zugangsdaten bei HTTP im Klartext. Im Schulnetz daher HTTPS per Reverse-Proxy (z. B. Nginx Proxy Manager oder Cloudflare Tunnel) vorschalten.
- `FLASK_DEBUG` niemals im Schulnetz oder auf oeffentlichen Servern auf `1` setzen.
- Der Container laeuft als Non-Root-User mit gunicorn.
- Hinweis: `/api/question/<id>` liefert Frage und Antwort ohne Login, damit das Spiel funktioniert. Schueler koennten Antworten ueber IDs abrufen.
- `data/` und `jeopardy.db` sind per `.gitignore` ausgeschlossen. Fragen bleiben bei `git pull` erhalten.
- Ein TruffleHog-Workflow scannt das Repo taeglich auf Secrets.

## Klassenstufen-Filter

Der Filter im Team-Setup laedt das Spielbrett mit `/play?grade=7` neu. Einzelklassen (`6`-`10`) und Bereiche (`7-8`, `8-9`, `9-10`) werden erkannt: Eine Frage mit `grade_level = "7-8"` erscheint bei Klasse 7 und bei Klasse 8.

## Lizenz

Dieses Projekt steht unter der [MIT-Lizenz](./LICENSE).
