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
