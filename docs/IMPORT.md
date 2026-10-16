# Fragen importieren

Unter **Admin > Import** (`/admin/import`) kannst du Fragen als **JSON** oder **CSV** hochladen oder einfuegen.

## Welches Format?

| Format | Wann? |
|---|---|
| **JSON** (empfohlen) | Fragen kommen aus einem Skript oder von einer KI, oder Texte enthalten Zeilenumbrueche, Semikolons oder Anfuehrungszeichen. Keine Probleme mit Trennzeichen oder Zeichensaetzen. |
| **CSV** | Du pflegst die Fragen in Excel oder LibreOffice. Als "CSV UTF-8" speichern, Trennzeichen `;` oder `,` wird automatisch erkannt. |

Vorlagen und ein Export aller vorhandenen Fragen (JSON und CSV) findest du auf der Import-Seite.

## Felder

| Feld | Pflicht | Bedeutung |
|---|---|---|
| `kategorie` | ja | Name einer vorhandenen Kategorie (Gross-/Kleinschreibung egal) |
| `punkte` | ja | Positive ganze Zahl, z. B. `100`. Die Frage erscheint nur auf dem Spielbrett, wenn die Punktzahl zu den Punktestufen unter Einstellungen passt (Standard 100 bis 500) |
| `frage` | ja | Fragetext, bis 2000 Zeichen |
| `antwort` | ja | Antworttext, bis 2000 Zeichen |
| `klassenstufe` | nein | Eine Klasse (`7`) oder ein Bereich (`7-8`) |
| `kompetenzbereich` | nein | Freitext, bis 200 Zeichen |
| `hinweis` | nein | Optionaler Hinweis |

Auch englische Feldnamen werden akzeptiert: `category`, `points`, `grade_level`, `competence_area`, `question`, `answer`, `hint`. Unbekannte Spalten werden ignoriert.

## Beispiel JSON

```json
{
  "fragen": [
    {
      "kategorie": "Werkstoffe und Produkte",
      "punkte": 100,
      "klassenstufe": "7-8",
      "kompetenzbereich": "3.3.1 Werkstoffe und Produkte",
      "frage": "Nenne drei typische metallische Werkstoffe.",
      "antwort": "Stahl, Aluminium, Kupfer.",
      "hinweis": ""
    },
    {
      "kategorie": "Systeme und Prozesse",
      "punkte": 300,
      "frage": "Was ist ein Aktor?",
      "antwort": "Ein Bauteil, das eine Wirkung ausuebt."
    }
  ]
}
```

Eine blanke Liste `[ {...}, {...} ]` ohne `fragen` wird ebenfalls akzeptiert.

## Beispiel CSV

```csv
kategorie;punkte;klassenstufe;kompetenzbereich;frage;antwort;hinweis
Werkstoffe und Produkte;100;7-8;3.3.1 Werkstoffe und Produkte;Nenne drei typische metallische Werkstoffe.;Stahl, Aluminium, Kupfer.;
Systeme und Prozesse;300;9;;Was ist ein Aktor?;Ein Bauteil, das eine Wirkung ausuebt.;Gegenstueck zum Sensor
```

Die erste Zeile enthaelt die Spaltennamen. Texte mit Trennzeichen oder Zeilenumbruechen stehen in Anfuehrungszeichen.

## Ablauf und Regeln

1. Datei waehlen oder Inhalt einfuegen.
2. **Nur pruefen** zeigt, was passieren wuerde, und speichert nichts.
3. **Importieren** uebernimmt alle gueltigen Eintraege. Fehlerhafte Eintraege werden uebersprungen und mit Nummer und Grund aufgelistet.

- Maximal 2000 Fragen pro Import, Dateigroesse bis 2 MB.
- Eine Frage mit gleichem Fragetext wie eine vorhandene gilt als Duplikat und wird uebersprungen.
- Unbekannte Kategorien sind standardmaessig ein Fehler. Mit der Option "Unbekannte Kategorien automatisch anlegen" werden sie neu erstellt.
- Kodierung: UTF-8 (auch mit BOM), alte Windows-1252-Dateien werden ebenfalls gelesen.
- Hinweis zum Standardfragen-Abgleich: Beim Start ergaenzt die App fehlende Standardfragen aus den Seed-Dateien. Importierte Fragen bleiben davon unberuehrt.
