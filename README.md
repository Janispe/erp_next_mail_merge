# Mail Merge

Generic Serienbrief/Mail-Merge core for Frappe.

## PDF-Downloads und Laufstatus

„Sammel-PDF“ führt ausschließlich gespeicherte Einzel-PDFs zusammen und legt
das Ergebnis als private Datei am Durchlauf ab. Vorlagen, Stammdaten und
Druckformate werden dabei nicht erneut gerendert. Fehlt ein gespeichertes PDF,
meldet der Download einen Fehler. Fehlerhafte und übersprungene Empfänger
werden nicht in das Sammel-PDF aufgenommen.

Die Schwarz-Weiß-Option gilt beim Starten bzw. Einreichen des Laufs. Änderungen
an Variablen oder Druckoptionen erfordern bei Entwürfen einen neuen Renderlauf.
Neuerzeugung benötigt Schreibrechte und ist für laufende, eingereichte oder
stornierte Durchläufe gesperrt. Der ältere Endpunkt `generate_pdf` rendert
Entwürfe weiterhin mit Schreibprüfung; bei eingereichten Durchläufen liefert
er ausschließlich den gespeicherten Stand.

Schlägt die Erzeugung fehl und entsteht kein erfolgreiches Dokument, lautet der
Laufstatus „Fehlgeschlagen“. Bei Teilerfolgen bleibt er „Generiert“; die
Zusammenfassung enthält weiterhin sämtliche Empfängerfehler. Ausschließlich
übersprungene Empfänger gelten nicht als Renderfehler.

Regressionstests: `mail_merge.mail_merge.doctype.serienbrief_durchlauf.test_serienbrief_durchlauf`.

## Schreibgeschützte Briefinhalte

Serienbrief-Vorlagen und Textbausteine werden in einer eigenen Jinja-Sandbox
mit ausdrücklich freigegebenen Lesefunktionen gerendert. Das gilt für den Body,
Footer, historische Versionen und die Editor-Vorschau. Datenbankänderungen,
Löschen, Dokumentaktionen, Mailversand, HTTP-Aufrufe, Server-Skripte und weitere
Jinja-Render-Aufrufe sind über die Briefinhalte gesperrt. Gesperrte Aufrufe
melden einen Fehler; in der Editor-Vorschau erscheint eine Fehlermarkierung.

Daten lesen, Datums- und Geldformatierung sowie Jinja-Makros, Schleifen und
lokale Hilfslisten bleiben verfügbar. Die Vorschau verwendet weiterhin ihre
Beispieldaten. Der normale Frappe-Renderer für andere Anwendungen bleibt
unverändert.

Zusätzliche globale Jinja-Helfer und Filter aus App-Hooks werden nicht automatisch
übernommen. Neue Dokumentmethoden benötigen eine geprüfte Freigabe in
`mail_merge/mail_merge/utils/jinja_readonly.py`; ein Name wie `get_*` reicht
nicht aus. Dies betrifft ausführbaren Jinja-Inhalt, nicht die Berechtigungen
zum Bearbeiten von Vorlagen oder zum Erzeugen von Serienbrief-Dokumenten.

Regressionstests: `mail_merge.mail_merge.utils.test_jinja_readonly`.
