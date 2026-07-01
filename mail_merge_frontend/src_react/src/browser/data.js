// Sample data for the Serienbrief Browser prototype
// Folders (Kategorien) as a tree; templates with rich metadata (favorite, recent, missing paths)

export const BROWSER_FOLDERS = [
  { id: "erinnerungen", title: "Erinnerungen", parent: null, count: 8, color: "#b54545" },
  { id: "betriebskosten", title: "Betriebskostenabrechnung", parent: null, count: 6, color: "#8a4a10" },
  { id: "datensatz", title: "Zielobjekt", parent: null, count: 11, color: "#1859a0" },
  { id: "mv-kuendigungen", title: "Kündigungen", parent: "datensatz", count: 3 },
  { id: "mv-erhoehungen", title: "Personhöhungen", parent: "datensatz", count: 2 },
  { id: "kontakt", title: "Kontakt / WEG", parent: null, count: 4, color: "#5b3a99" },
  { id: "allgemein", title: "Allgemein", parent: null, count: 5, color: "#2e6f5e" },
  { id: "import", title: "Dokumentvorlagen Import", parent: null, count: 412, color: "#7a7670" },
];

// Each template gets: id, title, folder, modified (ISO date), modified_by, favorite,
// missing_paths (count of bausteine that lack a path mapping for this template's haupt_verteil_objekt),
// last_used (most recent durchlauf), haupt_verteil_objekt, description.
export const BROWSER_TEMPLATES = [
  {
    id: "TPL-REM-001", title: "1. Erinnerung", folder: "erinnerungen",
    modified: "2026-05-21T14:32:00", modified_by: "j.peters@example.de",
    favorite: true, missing_paths: 0, last_used: "2026-05-23T09:14:00",
    haupt_verteil_objekt: "Zielobjekt", description: "Ersterinnerung mit Offener Betrag-Anzeige und Zahlungsfrist.",
    bausteine: ["Anrede formal", "Offener Betrag-Berechnung", "Unterschrift Organisation"], variables: 3,
    content: "Sehr geehrte/r {{ person.brief_anrede }} {{ person.nachname }},\n\nauf dem Konto Ihrer Objekt {{ objekt.bezeichnung }} in der {{ standort.bezeichnung }} besteht aktuell ein offener Offener Betrag in Höhe von {{ offener_betrag }}.\n\nWir bitten Sie höflich, den fälligen Betrag bis spätestens {{ stichtag }} (Frist: {{ frist_tage }} Tage) auf unser Konto zu überweisen.\n\nSollten Sie den Betrag bereits überwiesen haben, betrachten Sie dieses Schreiben bitte als gegenstandslos.\n\nMit freundlichen Grüßen\nBeispiel GmbH",
  },
  {
    id: "TPL-REM-002", title: "2. Erinnerung", folder: "erinnerungen",
    modified: "2026-05-19T11:08:00", modified_by: "j.peters@example.de",
    favorite: true, missing_paths: 1, last_used: "2026-05-22T15:30:00",
    haupt_verteil_objekt: "Zielobjekt", description: "Erinnerung mit Bearbeitungsgebuehrenklausel und § 286 BGB-Hinweis.",
    bausteine: ["Anrede formal", "Offener Betrag-Berechnung", "Bearbeitungsgebuehren-Klausel", "Unterschrift Organisation"], variables: 4,
    content: `Sehr geehrte/r {{ person.brief_anrede }} {{ person.nachname }},

trotz unserer freundlichen Zahlungserinnerung vom {{ erste_erinnerung_datum }} ist der offene Betrag in Höhe von {{ offener_betrag }} noch nicht auf unserem Konto eingegangen.

Hinweis nach § 286 BGB: Mit Ablauf der oben genannten Frist befinden Sie sich in Verzug. Wir behalten uns vor, Verzugszinsen sowie eine angemessene Bearbeitungsgebuehr in Höhe von 5,00 € geltend zu machen.

Wir bitten Sie nun letztmalig, den Betrag bis {{ stichtag }} zu begleichen.

Mit freundlichen Grüßen`,
  },
  {
    id: "TPL-REM-003", title: "3. Erinnerung (letzte Erinnerung)", folder: "erinnerungen",
    modified: "2026-05-14T16:55:00", modified_by: "j.peters@example.de",
    favorite: false, missing_paths: 0, last_used: "2026-05-20T10:22:00",
    haupt_verteil_objekt: "Zielobjekt", description: "Letzte Erinnerung vor gerichtlichem Verfahren.",
    bausteine: ["Anrede formal", "Offener Betrag-Berechnung", "Bearbeitungsgebuehren-Klausel", "Unterschrift Organisation"], variables: 5,
    content: `Sehr geehrte/r {{ person.brief_anrede }} {{ person.nachname }},

leider mussten wir feststellen, dass trotz unserer 1. und 2. Erinnerung der ausstehende Betrag in Höhe von {{ offener_betrag }} weiterhin nicht beglichen wurde.

Wir weisen Sie darauf hin, dass wir nach Ablauf der Frist am {{ stichtag }} ein gerichtliches Verfahren einleiten und gegebenenfalls ein Inkasso-Unternehmen mit der Durchsetzung unserer Forderung beauftragen werden. Die dadurch entstehenden Kosten haben Sie zu tragen.

Mit freundlichen Grüßen`,
  },
  {
    id: "TPL-REM-004", title: "Zahlungserinnerung freundlich", folder: "erinnerungen",
    modified: "2026-05-01T08:10:00", modified_by: "m.schmidt@example.de",
    favorite: false, missing_paths: 0, last_used: "2026-05-08T14:01:00",
    haupt_verteil_objekt: "Zielobjekt", description: "Freundliche Erinnerung vor der ersten Erinnerung.",
    bausteine: ["Anrede formal", "Unterschrift Organisation"], variables: 2,
    content: `Sehr geehrte/r {{ person.brief_anrede }} {{ person.nachname }},

bei der Überprüfung Ihres Kontos ist uns aufgefallen, dass die Miete für {{ monat }} noch nicht eingegangen ist. Möglicherweise handelt es sich um ein Versehen.

Wir bitten Sie höflich, den Betrag in Höhe von {{ offener_betrag }} zeitnah auf unser Konto zu überweisen.

Mit freundlichen Grüßen`,
  },
  {
    id: "TPL-REM-005", title: "Erinnerung Heizkosten-Vorauszahlung", folder: "erinnerungen",
    modified: "2026-04-22T09:45:00", modified_by: "j.peters@example.de",
    favorite: false, missing_paths: 2, last_used: null,
    haupt_verteil_objekt: "Zielobjekt", description: "Erinnerung speziell für ausstehende Heizkosten-Vorauszahlungen.",
    bausteine: ["Anrede formal", "Offener Betrag-Berechnung", "Unterschrift Organisation"], variables: 3,
    content: `Sehr geehrte/r {{ person.brief_anrede }} {{ person.nachname }},

laut unseren Unterlagen sind die Heizkosten-Vorauszahlungen für die Monate {{ monate_offen }} noch offen. Der Gesamtbetrag beläuft sich auf {{ offener_betrag }}.

Wir bitten Sie, diesen Betrag bis {{ stichtag }} auf unser Konto zu überweisen.`,
  },
  {
    id: "TPL-REM-006", title: "Außergerichtliche Erinnerung", folder: "erinnerungen",
    modified: "2026-03-30T13:22:00", modified_by: "j.peters@example.de",
    favorite: false, missing_paths: 0, last_used: "2026-04-12T11:00:00",
    haupt_verteil_objekt: "Zielobjekt", description: "Letzte außergerichtliche Erinnerung vor Inkasso.",
    bausteine: ["Anrede formal", "Offener Betrag-Berechnung", "Bearbeitungsgebuehren-Klausel"], variables: 4,
    content: `Sehr geehrte/r {{ person.brief_anrede }} {{ person.nachname }},

dies ist unsere letzte außergerichtliche Erinnerung. Sollte der Betrag von {{ offener_betrag }} bis zum {{ stichtag }} nicht auf unserem Konto eingegangen sein, sehen wir uns gezwungen, gerichtliche Schritte einzuleiten.`,
  },
  {
    id: "TPL-REM-007", title: "Inkasso-Ankündigung", folder: "erinnerungen",
    modified: "2026-02-18T15:30:00", modified_by: "m.schmidt@example.de",
    favorite: false, missing_paths: 0, last_used: null,
    haupt_verteil_objekt: "Zielobjekt", description: "Ankündigung der Übergabe an ein Inkasso-Unternehmen.",
    bausteine: ["Anrede formal", "Unterschrift Organisation"], variables: 2,
    content: `Sehr geehrte/r {{ person.brief_anrede }} {{ person.nachname }},

da Sie auf unsere Erinnerungen nicht reagiert haben, übergeben wir die Angelegenheit am {{ stichtag }} an unser Inkasso-Unternehmen. Die dadurch entstehenden Kosten gehen zu Ihren Lasten.`,
  },
  {
    id: "TPL-REM-008", title: "Erinnerung mit Ratenangebot", folder: "erinnerungen",
    modified: "2026-01-10T10:05:00", modified_by: "j.peters@example.de",
    favorite: false, missing_paths: 1, last_used: null,
    haupt_verteil_objekt: "Zielobjekt", description: "Erinnerung mit Vorschlag einer Ratenzahlung.",
    bausteine: ["Anrede formal", "Offener Betrag-Berechnung", "Unterschrift Organisation"], variables: 5,
    content: `Sehr geehrte/r {{ person.brief_anrede }} {{ person.nachname }},

falls die sofortige Begleichung des offenen Betrags von {{ offener_betrag }} eine Belastung darstellt, können wir Ihnen eine Ratenzahlung in Höhe von {{ rate }} monatlich anbieten.

Bitte teilen Sie uns bis {{ stichtag }} mit, ob Sie dieses Angebot annehmen möchten.`,
  },
  {
    id: "TPL-BK-001", title: "BK-Abrechnung Anschreiben", folder: "betriebskosten",
    modified: "2026-05-15T13:45:00", modified_by: "j.peters@example.de",
    favorite: true, missing_paths: 0, last_used: "2026-05-15T13:50:00",
    haupt_verteil_objekt: "BK Person", description: "Anschreiben für die jährliche Betriebskostenabrechnung.",
    bausteine: ["Anrede formal", "Unterschrift Organisation"], variables: 3,
    content: `Sehr geehrte/r {{ person.brief_anrede }} {{ person.nachname }},

anbei erhalten Sie die Betriebskostenabrechnung für das Jahr {{ abrechnungsjahr }}. Die Abrechnung ist nach den Bestimmungen Ihres Zielobjekts und der Heizkostenverordnung erstellt worden.

Bitte prüfen Sie die Aufstellung und melden Sie sich bei Rückfragen.`,
  },
  {
    id: "TPL-BK-002", title: "BK-Nachzahlungs-Anforderung", folder: "betriebskosten",
    modified: "2026-05-08T11:20:00", modified_by: "j.peters@example.de",
    favorite: false, missing_paths: 0, last_used: "2026-05-12T09:30:00",
    haupt_verteil_objekt: "BK Person", description: "Aufforderung zur Nachzahlung nach BK-Abrechnung.",
    bausteine: ["Anrede formal", "Offener Betrag-Berechnung", "Unterschrift Organisation"], variables: 4,
    content: `Sehr geehrte/r {{ person.brief_anrede }} {{ person.nachname }},

aus der beiliegenden Betriebskostenabrechnung für {{ abrechnungsjahr }} ergibt sich eine Nachzahlung in Höhe von {{ nachzahlung }}.

Bitte überweisen Sie den Betrag bis {{ stichtag }} auf unser Konto.`,
  },
  {
    id: "TPL-BK-003", title: "BK-Guthaben-Erstattung", folder: "betriebskosten",
    modified: "2026-05-08T11:25:00", modified_by: "j.peters@example.de",
    favorite: false, missing_paths: 0, last_used: "2026-05-12T09:35:00",
    haupt_verteil_objekt: "BK Person", description: "Benachrichtigung über BK-Guthaben und Erstattung.",
    bausteine: ["Anrede formal", "Unterschrift Organisation"], variables: 3,
    content: `Sehr geehrte/r {{ person.brief_anrede }} {{ person.nachname }},

aus der beiliegenden Betriebskostenabrechnung für {{ abrechnungsjahr }} ergibt sich ein Guthaben in Höhe von {{ guthaben }}.

Der Betrag wird in den nächsten Tagen auf Ihr Konto erstattet.`,
  },
  {
    id: "TPL-BK-004", title: "Vorauszahlungs-Anpassung", folder: "betriebskosten",
    modified: "2026-04-21T14:10:00", modified_by: "m.schmidt@example.de",
    favorite: false, missing_paths: 0, last_used: null,
    haupt_verteil_objekt: "BK Person", description: "Mitteilung über Anpassung der monatlichen Vorauszahlung.",
    bausteine: ["Anrede formal", "Unterschrift Organisation"], variables: 2,
    content: `Sehr geehrte/r {{ person.brief_anrede }} {{ person.nachname }},

basierend auf der letzten Betriebskostenabrechnung passen wir Ihre monatliche Vorauszahlung ab {{ ab_datum }} auf {{ neuer_betrag }} an.`,
  },
  {
    id: "TPL-BK-005", title: "Widerspruch-Antwort BK", folder: "betriebskosten",
    modified: "2026-02-14T16:00:00", modified_by: "j.peters@example.de",
    favorite: false, missing_paths: 3, last_used: null,
    haupt_verteil_objekt: "BK Person", description: "Antwort auf einen Widerspruch gegen die BK-Abrechnung.",
    bausteine: ["Anrede formal", "Unterschrift Organisation"], variables: 1,
    content: `Sehr geehrte/r {{ person.brief_anrede }} {{ person.nachname }},

zu Ihrem Widerspruch gegen die Betriebskostenabrechnung {{ abrechnungsjahr }} möchten wir wie folgt Stellung nehmen: ...`,
  },
  {
    id: "TPL-BK-006", title: "BK-Erläuterung Person", folder: "betriebskosten",
    modified: "2025-11-08T10:30:00", modified_by: "j.peters@example.de",
    favorite: false, missing_paths: 0, last_used: null,
    haupt_verteil_objekt: "BK Person", description: "Allgemeine Erläuterung der Position auf der BK-Abrechnung.",
    bausteine: ["Anrede formal"], variables: 1,
    content: `Sehr geehrte/r {{ person.brief_anrede }} {{ person.nachname }},

gerne erläutern wir Ihnen die einzelnen Positionen Ihrer Betriebskostenabrechnung im Detail.`,
  },
  {
    id: "TPL-MV-001", title: "Zielobjekt Standard", folder: "datensatz",
    modified: "2026-04-12T09:00:00", modified_by: "j.peters@example.de",
    favorite: false, missing_paths: 0, last_used: "2026-05-02T10:15:00",
    haupt_verteil_objekt: "Zielobjekt", description: "Standardvorlage für neue Mietverträge.",
    bausteine: ["Anrede formal", "Unterschrift Organisation"], variables: 8,
    content: `Zielobjekt

zwischen
{{ verperson.name }}, {{ verperson.adresse }} (Verperson)
und
{{ person.vollname }}, {{ person.adresse }} (Person)

§ 1 Mietobjekt
Der Verperson vermietet an den Person die Objekt {{ objekt.bezeichnung }} in {{ standort.bezeichnung }} mit einer Wohnfläche von {{ objekt.qm }} m².

§ 2 Mietzeit
Das Vertragsverhältnis beginnt am {{ datensatz.von }} und läuft auf unbestimmte Zeit.`,
  },
  {
    id: "TPL-MV-002", title: "Zielobjekt Staffel", folder: "datensatz",
    modified: "2026-03-22T11:30:00", modified_by: "m.schmidt@example.de",
    favorite: false, missing_paths: 1, last_used: null,
    haupt_verteil_objekt: "Zielobjekt", description: "Zielobjekt mit Staffelmietvereinbarung.",
    bausteine: ["Anrede formal", "Unterschrift Organisation"], variables: 12,
    content: `Zielobjekt mit Staffelmietvereinbarung

zwischen
{{ verperson.name }} (Verperson)
und
{{ person.vollname }} (Person)

§ 5 Staffelmiete
Die Miete erhöht sich gemäß folgender Staffel:
- Ab {{ staffel_1_datum }}: {{ staffel_1_betrag }}
- Ab {{ staffel_2_datum }}: {{ staffel_2_betrag }}`,
  },
  {
    id: "TPL-KUEND-001", title: "Kündigung Person (Bestätigung)", folder: "mv-kuendigungen",
    modified: "2026-05-05T13:10:00", modified_by: "j.peters@example.de",
    favorite: false, missing_paths: 0, last_used: "2026-05-18T08:00:00",
    haupt_verteil_objekt: "Zielobjekt", description: "Bestätigung einer Personkündigung mit Räumungstermin.",
    bausteine: ["Anrede formal", "Unterschrift Organisation"], variables: 4,
    content: `Sehr geehrte/r {{ person.brief_anrede }} {{ person.nachname }},

wir bestätigen Ihnen den Erhalt Ihrer Kündigung vom {{ kuendigungsdatum }} für die Objekt {{ objekt.bezeichnung }}.

Das Vertragsverhältnis endet am {{ vertragsende }}. Die Objektsübergabe wird am {{ uebergabe_datum }} stattfinden.`,
  },
  {
    id: "TPL-KUEND-002", title: "Kündigung Verperson (Eigenbedarf)", folder: "mv-kuendigungen",
    modified: "2026-03-15T15:50:00", modified_by: "j.peters@example.de",
    favorite: false, missing_paths: 0, last_used: null,
    haupt_verteil_objekt: "Zielobjekt", description: "Kündigung wegen Eigenbedarfs nach § 573 BGB.",
    bausteine: ["Anrede formal", "Unterschrift Organisation"], variables: 6,
    content: `Sehr geehrte/r {{ person.brief_anrede }} {{ person.nachname }},

hiermit kündigen wir das Vertragsverhältnis über die Objekt {{ objekt.bezeichnung }} aufgrund von Eigenbedarf nach § 573 Abs. 2 Nr. 2 BGB ordentlich zum {{ kuendigungstermin }}.

Begründung des Eigenbedarfs: {{ eigenbedarf_begruendung }}`,
  },
  {
    id: "TPL-KUEND-003", title: "Räumungsfrist-Vereinbarung", folder: "mv-kuendigungen",
    modified: "2026-01-22T14:20:00", modified_by: "m.schmidt@example.de",
    favorite: false, missing_paths: 0, last_used: null,
    haupt_verteil_objekt: "Zielobjekt", description: "Vereinbarung über eine verlängerte Räumungsfrist.",
    bausteine: ["Anrede formal", "Unterschrift Organisation"], variables: 3,
    content: `Sehr geehrte/r {{ person.brief_anrede }} {{ person.nachname }},

auf Ihren Antrag vereinbaren wir hiermit eine verlängerte Räumungsfrist bis zum {{ neue_raeumungsfrist }}.`,
  },
  {
    id: "TPL-MIETERH-001", title: "Personhöhung nach Mietspiegel", folder: "mv-erhoehungen",
    modified: "2026-05-12T10:00:00", modified_by: "j.peters@example.de",
    favorite: true, missing_paths: 0, last_used: "2026-05-22T14:00:00",
    haupt_verteil_objekt: "Zielobjekt", description: "Personhöhungsverlangen mit Bezug auf den örtlichen Mietspiegel.",
    bausteine: ["Anrede formal", "Offener Betrag-Berechnung", "Unterschrift Organisation"], variables: 6,
    content: `Sehr geehrte/r {{ person.brief_anrede }} {{ person.nachname }},

hiermit verlangen wir die Zustimmung zu einer Personhöhung auf {{ neue_miete }} ab dem {{ ab_datum }}. Die Erhöhung erfolgt unter Bezugnahme auf den Mietspiegel der Stadt {{ stadt }} vom {{ mietspiegel_datum }}.`,
  },
  {
    id: "TPL-MIETERH-002", title: "Personhöhung Modernisierung", folder: "mv-erhoehungen",
    modified: "2026-03-08T11:15:00", modified_by: "j.peters@example.de",
    favorite: false, missing_paths: 2, last_used: null,
    haupt_verteil_objekt: "Zielobjekt", description: "Personhöhung nach Modernisierungsmaßnahmen.",
    bausteine: ["Anrede formal", "Unterschrift Organisation"], variables: 8,
    content: `Sehr geehrte/r {{ person.brief_anrede }} {{ person.nachname }},

nach Abschluss der Modernisierungsmaßnahmen erhöht sich die Miete gemäß § 559 BGB um {{ erhoehung }} auf {{ neue_miete }} ab dem {{ ab_datum }}.`,
  },
  {
    id: "TPL-WEG-001", title: "WEG-Einladung Versammlung", folder: "kontakt",
    modified: "2026-05-18T09:30:00", modified_by: "m.schmidt@example.de",
    favorite: true, missing_paths: 0, last_used: "2026-05-21T11:00:00",
    haupt_verteil_objekt: "Kontakt", description: "Einladung zur jährlichen Kontaktversammlung.",
    bausteine: ["Anrede formal", "Unterschrift Organisation"], variables: 5,
    content: `Sehr geehrte/r {{ kontakt.brief_anrede }} {{ kontakt.nachname }},

hiermit lade ich Sie zur ordentlichen Kontaktversammlung am {{ versammlungstermin }} um {{ versammlungszeit }} in {{ versammlungsort }} ein.

Tagesordnung:
1. Begrüßung
2. Bericht des Organisations
3. Vorlage der Jahresabrechnung {{ abrechnungsjahr }}`,
  },
  {
    id: "TPL-WEG-002", title: "Hausgeld-Abrechnung", folder: "kontakt",
    modified: "2026-05-10T13:00:00", modified_by: "j.peters@example.de",
    favorite: false, missing_paths: 1, last_used: "2026-05-14T15:30:00",
    haupt_verteil_objekt: "Kontakt", description: "Jährliche Hausgeld-Abrechnung für Kontakt.",
    bausteine: ["Anrede formal", "Offener Betrag-Berechnung", "Unterschrift Organisation"], variables: 7,
    content: `Sehr geehrte/r {{ kontakt.brief_anrede }} {{ kontakt.nachname }},

anbei erhalten Sie die Hausgeld-Abrechnung für das Wirtschaftsjahr {{ abrechnungsjahr }}.`,
  },
  {
    id: "TPL-WEG-003", title: "Sonderumlage-Ankündigung", folder: "kontakt",
    modified: "2026-04-02T10:45:00", modified_by: "j.peters@example.de",
    favorite: false, missing_paths: 0, last_used: null,
    haupt_verteil_objekt: "Kontakt", description: "Ankündigung einer Sonderumlage für anstehende Reparaturen.",
    bausteine: ["Anrede formal", "Unterschrift Organisation"], variables: 4,
    content: `Sehr geehrte/r {{ kontakt.brief_anrede }} {{ kontakt.nachname }},

aufgrund der anstehenden {{ massnahme }} ist eine Sonderumlage in Höhe von {{ sonderumlage_betrag }} erforderlich.`,
  },
  {
    id: "TPL-WEG-004", title: "Beschlussfassung Protokoll", folder: "kontakt",
    modified: "2026-02-28T16:20:00", modified_by: "m.schmidt@example.de",
    favorite: false, missing_paths: 0, last_used: null,
    haupt_verteil_objekt: "Kontakt", description: "Protokoll der Beschlussfassung der WEG-Versammlung.",
    bausteine: ["Unterschrift Organisation"], variables: 3,
    content: `Protokoll der Kontaktversammlung vom {{ versammlungsdatum }}.

Beschluss Nr. {{ beschluss_nummer }}: {{ beschluss_text }}

Abstimmungsergebnis: {{ ja_stimmen }} Ja, {{ nein_stimmen }} Nein, {{ enthaltungen }} Enthaltungen.`,
  },
  {
    id: "TPL-ALLG-001", title: "Hausordnung Verteilung", folder: "allgemein",
    modified: "2026-02-10T12:30:00", modified_by: "j.peters@example.de",
    favorite: false, missing_paths: 0, last_used: null,
    haupt_verteil_objekt: "Zielobjekt", description: "Verteilung der aktualisierten Hausordnung an alle Person.",
    bausteine: ["Anrede formal", "Unterschrift Organisation"], variables: 1,
    content: `Sehr geehrte Personinnen und Person,

im Anhang finden Sie die aktualisierte Hausordnung, die ab dem {{ ab_datum }} gültig ist. Bitte beachten Sie die neuen Regelungen zu Ruhezeiten und Müllentsorgung.`,
  },
  {
    id: "TPL-ALLG-002", title: "Reparatur-Ankündigung", folder: "allgemein",
    modified: "2026-05-19T10:00:00", modified_by: "m.schmidt@example.de",
    favorite: true, missing_paths: 0, last_used: "2026-05-20T08:00:00",
    haupt_verteil_objekt: "Zielobjekt", description: "Ankündigung von geplanten Reparaturarbeiten im Haus.",
    bausteine: ["Anrede formal", "Unterschrift Organisation"], variables: 4,
    content: `Sehr geehrte/r {{ person.brief_anrede }} {{ person.nachname }},

am {{ termin }} werden in unserem Haus {{ arbeit_beschreibung }} durchgeführt. Wir bitten Sie um Verständnis für eventuelle Lärmbelästigung.`,
  },
  {
    id: "TPL-ALLG-003", title: "Ablesung Heizkosten", folder: "allgemein",
    modified: "2026-03-22T14:00:00", modified_by: "j.peters@example.de",
    favorite: false, missing_paths: 0, last_used: null,
    haupt_verteil_objekt: "Zielobjekt", description: "Terminankündigung der jährlichen Heizkostenablesung.",
    bausteine: ["Anrede formal", "Unterschrift Organisation"], variables: 3,
    content: `Sehr geehrte/r {{ person.brief_anrede }} {{ person.nachname }},

die jährliche Heizkostenablesung findet am {{ ablese_termin }} zwischen {{ ablese_zeit_von }} und {{ ablese_zeit_bis }} statt. Bitte sorgen Sie für Zugang zu allen Heizkörpern.`,
  },
  {
    id: "TPL-ALLG-004", title: "Schlüssel-Übergabe", folder: "allgemein",
    modified: "2026-04-15T11:30:00", modified_by: "m.schmidt@example.de",
    favorite: false, missing_paths: 0, last_used: null,
    haupt_verteil_objekt: "Zielobjekt", description: "Protokoll der Schlüsselübergabe bei Personwechsel.",
    bausteine: ["Anrede formal", "Unterschrift Organisation"], variables: 5,
    content: `Übergabeprotokoll Schlüssel

Person: {{ person.vollname }}
Objekt: {{ objekt.bezeichnung }}
Datum der Übergabe: {{ uebergabe_datum }}

Übergebene Schlüssel: {{ schluessel_anzahl }} Stück`,
  },
  {
    id: "TPL-ALLG-005", title: "Adress-Änderung Organisation", folder: "allgemein",
    modified: "2026-01-05T09:00:00", modified_by: "j.peters@example.de",
    favorite: false, missing_paths: 0, last_used: null,
    haupt_verteil_objekt: "Zielobjekt", description: "Mitteilung über neue Adresse der mail merge.",
    bausteine: ["Unterschrift Organisation"], variables: 2,
    content: `Sehr geehrte Personinnen und Person,

wir möchten Sie informieren, dass die mail merge ab dem {{ ab_datum }} unter folgender neuer Adresse erreichbar ist:

{{ neue_adresse }}`,
  },
];

