# Brief erstellen – Prototyp

Neue Durchläufe öffnen standardmäßig die bisherige Anlageansicht. Der Schalter
„Bisherige Ansicht / Assistent (Prototyp)“ wechselt zum Assistenten mit fünf
Schritten: Vorlage, Empfänger, Angaben, Vorschau, Speichern. Beide Eingabestände
bleiben beim Umschalten erhalten; es erfolgt dabei keine Speicherung. Vorlagenbearbeitung bleibt eine
eigene Aktion. Bestehende Durchläufe öffnen weiterhin den bisherigen Viewer.

## Ausprobieren

```sh
cd mail_merge_frontend/src_react
npm run dev -- --host 127.0.0.1 --port 5174
```

Demo: `http://127.0.0.1:5174/assets/mail_merge/durchlauf.html?composer=1`.
Die eigenständige Demo verwendet ausschließlich Beispieldaten, speichert keine
Dokumente und ruft keine KI auf. Im Frappe-iframe sind dieselben Schritte über die
RPC-Bridge mit den echten Daten verbunden.

Frontend für Frappe bauen: `npm run build:frappe -- durchlauf`. Änderungen am
Backend und an beiden Frappe-Host-Seiten gehören gemeinsam mit dem Build auf die
Zielinstallation. Es ist keine DocType-Migration nötig.

## Verhalten

- Bis zu zehn lesbare Empfänger pro Vorschau; gemeinsame und individuelle Werte.
- Briefe werden über Kontextwerte sowie die Eingaben der Vorlage und ihrer Bausteine ausgefüllt.
  Die Vorlage bestimmt die Position und bedingte Anzeige ihrer Inhalte.
- Beispiel: `hinweis_anzeigen` (Bool, Standard Nein) und `hinweistext` (optionaler
  Text). Die Vorlage verwendet `{% if hinweis_anzeigen and hinweistext %}<p>{{
  hinweistext }}</p>{% endif %}` an der gewünschten Stelle. Gemeinsame Werte können
  pro Empfänger überschrieben werden, insbesondere mit ausdrücklich `false`.
- Die Vorschau zeigt die ausgefüllte Vorlage und die Herkunft der Variablenwerte.
- Pro Empfänger werden fehlende Pflichtwerte und Renderfehler angezeigt.
  Unvollständige Vorschauen können nicht gespeichert werden.
- Speichern übernimmt die geprüften PDF-Bytes als private Entwürfe. Weder Versand
  noch Einreichen erfolgt. Vorschautokens gelten 30 Minuten, sind benutzergebunden
  und können ohne doppelte Durchläufe erneut gespeichert werden. Änderungen an
  Vorlage/Textbausteinen oder Empfängerdatensätzen erfordern eine neue Vorschau.
- Ein Eingabe-Fingerabdruck kennzeichnet geänderte Angaben bestehender Durchläufe.
  Ältere Dokumente ohne Fingerabdruck werden ausdrücklich als nicht vergleichbar
  angezeigt. Dies ist kein Vollvergleich nachträglich geänderter verknüpfter
  Stammdaten oder Vorlagen. Downloads verwenden weiterhin gespeicherte PDFs.

## KI und Grenzen

Das Kernsystem enthält keine eigene KI-Formulierung, Anbieteranbindung oder
KI-Schaltfläche. Eine externe KI kann über die bestehende MCP-Anbindung die
Vorlage und ihre Variablen lesen, gemeinsame Werte (`values`) und individuelle
Werte (`per_recipient`) setzen, prüfen und Briefe als Entwürfe speichern.
Texte und Ja/Nein-Werte werden dabei wie manuelle Eingaben verarbeitet.

Oberfläche und MCP verwenden dieselbe Eingabebeschreibung aus `render_inputs.py`.
Skalare Kontextwerte, Vorlagenvariablen und Eingabepfade der Bausteine sind
bearbeitbar. Ein gesetzter Wert ersetzt auch einen ansonsten nicht auflösbaren
Quellpfad. Die Vorlage bestimmt den Iterationstyp; die MCP-Anbindung hat dafür
keine feste Liste von Fach-DocTypes. Dokumentzugriffe prüfen weiterhin Rechte.

## Prüfungen

`npm test` prüft unter anderem den vollständigen Ablauf, individuelle Variablenwerte,
fehlende Angaben und veraltete Vorschauen. Die Python-Tests in
`mail_merge.mail_merge.utils.test_letter_composer` prüfen Eingabe-Fingerabdrücke,
Validierung, Vorschauzustand, unveränderte PDF-Bytes beim Speichern,
Wiederholbarkeit und Rollback mit gemocktem Datenbankzugriff.

Desktop- und Mobilansicht wurden in der eigenständigen Demo im Browser geprüft.
PDF-Erzeugung und Speichern wurden auf 8090 mit temporären Datensätzen und
anschließendem Rollback geprüft. KI-Anbieteraufrufe gehören nicht zum Serienbrief-Kernsystem.

## Bestehender Viewer: Variablenbearbeitung

Der linke Bereich startet mit 380 Pixeln und lässt sich an der Trennlinie auf
300 bis 620 Pixel einstellen (auch mit Pfeiltasten); die Breite wird lokal im
Browser gespeichert. „Werte bearbeiten für“ schaltet zwischen gemeinsamen Werten
und dem in der Empfängerliste ausgewählten Empfänger um. Individuelle Werte sind
gekennzeichnet und lassen sich feldweise auf den gemeinsamen Wert zurücksetzen.
Ein leerer Text, Nein oder derselbe Text wie der gemeinsame Wert bleiben bewusst
individuelle Angaben, bis sie ausdrücklich zurückgesetzt werden.

`datum` erscheint in „Variablen & Kontextwerte“ und lässt sich gemeinsam oder
für den ausgewählten Empfänger ändern. Es verwendet denselben Speicherweg und
dieselbe Vorrangfolge wie andere Werte: Kontext-/Vorlagestandard, gemeinsamer
Wert, individueller Wert. Das Durchlaufdatum liefert nur den Anfangswert.
Texte nutzen mehrzeilige Felder; Bool-Variablen eine Ja/Nein-Auswahl.

Bausteine erhalten ausschließlich deklarierte Eingaben. Ihre zugeordneten
Pfade werden im übergeordneten Kontext aufgelöst, auch für `datum` und `objekt`.
Ohne Pfadzuordnung oder Festwert wird kein gleichnamiger Kontextwert übernommen. Standardpfade werden je Startobjekt zentral im
Textbaustein gespeichert. Im Dialog „Standardpfade je Startobjekt“ sind alle
deklarierten Eingaben bearbeitbar, einschließlich Text, Datum und Bool. Die
Zuordnung verwendet Variablennamen, keine IDs der Variablen-Tabellenzeilen.
Vorlagen können einzelne Pfade überschreiben; die übrigen Eingaben verwenden
weiter den Baustein-Standard. Ein absichtlich geleertes sichtbares Pfadfeld
entfernt seine Zuordnung; zusätzliche, nicht bearbeitete Einträge bleiben erhalten.
Deklarierte Ausgaben werden unter `outputs.<baustein>.<ausgabe>` veröffentlicht
und können als Eingabepfad eines folgenden Bausteins dienen. Fachliche Druckprofile und Markenanpassungen liegen in der jeweiligen
Anwendung, für Hausverwaltung in `mail_merge_extensions.py` und
`mail_merge_brand.py`. Der generische Kern ruft optionale Hooks auf und enthält
keine Typabfragen für Mietverträge oder Betriebskostenabrechnungen.

Geprüft: Frontend-Integration mit Einzelwerten, Zurücksetzen und Tastatur-Resize;
Browserdarstellung; echter Datenbank-Roundtrip mit leerem Text, false und
Zurücksetzen, unveränderter PDF und anschließendem Rollback der Testdaten.

Zusätzlich geprüft: Kontextdatum ohne eigene Vorlagendeklaration, gemeinsamer
und individueller Wert im tatsächlichen PDF, Zurücksetzen, gespeicherter
PDF-Stand sowie MCP-Vorbereitung mit generischem Iterationstyp und überschriebenem
Datenpfad. Die Testdatensätze werden zurückgerollt.
