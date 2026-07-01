// Sample data for Serienbrief Editor prototype
// Realistic mail merge context

export const SAMPLE_RECIPIENTS = [
  {
    id: "MV-2024-0142",
    label: "Müller, Andreas — Tristanstr. 4, WE 03",
    doctype: "Zielobjekt",
    values: {
      "person.anrede": "Herr",
      "person.brief_anrede": "Herr",
      "person.vorname": "Andreas",
      "person.nachname": "Müller",
      "person.vollname": "Andreas Müller",
      "person.strasse": "Tristanstr. 4",
      "person.plz_ort": "80637 München",
      "organisation.name": "Beispiel GmbH",
      "organisation.strasse": "Leopoldstr. 112",
      "organisation.plz_ort": "80802 München",
      "objekt.bezeichnung": "WE 03 (3-Zi., 78,5 m²)",
      "objekt.qm": "78,50",
      "standort.bezeichnung": "Tristanstr. 4, 80637 München",
      "offener_betrag": "–847,32 €",
      "betrag_offen": "847,32",
      "datensatz.von": "01.04.2022",
      "datensatz.bis": "unbefristet",
      "grundbetrag": "1.245,00 €",
      "zuschlag": "285,00 €",
      "gesamtbetrag": "1.530,00 €",
      "datum": "21. Mai 2026",
      "datum_iso": "2026-05-21",
      "stichtag": "31. Mai 2026",
      "frist_tage": "14",
      "statuscode": "1",
      "zahlungskonto.iban": "DE89 3704 0044 0532 0130 00",
      "zahlungskonto.bic": "COBADEFFXXX",
      "zahlungskonto.bank": "Commerzbank München",
    },
  },
  {
    id: "MV-2023-0098",
    label: "Schäfer, Marlene — Tristanstr. 4, WE 07",
    doctype: "Zielobjekt",
    values: {
      "person.anrede": "Frau",
      "person.brief_anrede": "Frau",
      "person.vorname": "Marlene",
      "person.nachname": "Schäfer",
      "person.vollname": "Marlene Schäfer",
      "person.strasse": "Tristanstr. 4",
      "person.plz_ort": "80637 München",
      "organisation.name": "Beispiel GmbH",
      "organisation.strasse": "Leopoldstr. 112",
      "organisation.plz_ort": "80802 München",
      "objekt.bezeichnung": "WE 07 (2-Zi., 54,2 m²)",
      "objekt.qm": "54,20",
      "standort.bezeichnung": "Tristanstr. 4, 80637 München",
      "offener_betrag": "0,00 €",
      "betrag_offen": "0,00",
      "datensatz.von": "15.08.2023",
      "datensatz.bis": "unbefristet",
      "grundbetrag": "920,00 €",
      "zuschlag": "210,00 €",
      "gesamtbetrag": "1.130,00 €",
      "datum": "21. Mai 2026",
      "datum_iso": "2026-05-21",
      "stichtag": "31. Mai 2026",
      "frist_tage": "14",
      "statuscode": "1",
      "zahlungskonto.iban": "DE89 3704 0044 0532 0130 00",
      "zahlungskonto.bic": "COBADEFFXXX",
      "zahlungskonto.bank": "Commerzbank München",
    },
  },
  {
    id: "MV-2021-0034",
    label: "Bauer, Reinhold — Leopoldstr. 88, WE 12",
    doctype: "Zielobjekt",
    values: {
      "person.anrede": "Herr",
      "person.brief_anrede": "Herr",
      "person.vorname": "Reinhold",
      "person.nachname": "Bauer",
      "person.vollname": "Reinhold Bauer",
      "person.strasse": "Leopoldstr. 88",
      "person.plz_ort": "80802 München",
      "organisation.name": "Beispiel GmbH",
      "organisation.strasse": "Leopoldstr. 112",
      "organisation.plz_ort": "80802 München",
      "objekt.bezeichnung": "WE 12 (4-Zi., 102,8 m²)",
      "objekt.qm": "102,80",
      "standort.bezeichnung": "Leopoldstr. 88, 80802 München",
      "offener_betrag": "–2.412,55 €",
      "betrag_offen": "2.412,55",
      "datensatz.von": "01.09.2021",
      "datensatz.bis": "unbefristet",
      "grundbetrag": "1.820,00 €",
      "zuschlag": "395,00 €",
      "gesamtbetrag": "2.215,00 €",
      "datum": "21. Mai 2026",
      "datum_iso": "2026-05-21",
      "stichtag": "31. Mai 2026",
      "frist_tage": "14",
      "statuscode": "2",
      "zahlungskonto.iban": "DE89 3704 0044 0532 0130 00",
      "zahlungskonto.bic": "COBADEFFXXX",
      "zahlungskonto.bank": "Commerzbank München",
    },
  },
];

export const PLACEHOLDER_GROUPS = [
  {
    key: "person",
    label: "Person",
    icon: "user",
    items: [
      { token: "{{ person.anrede }}", label: "Anrede", desc: "Herr / Frau / Divers" },
      { token: "{{ person.brief_anrede }}", label: "Brief-Anrede", desc: "Für Anschriftfeld" },
      { token: "{{ person.vorname }}", label: "Vorname" },
      { token: "{{ person.nachname }}", label: "Nachname" },
      { token: "{{ person.vollname }}", label: "Vollname", desc: "Vorname + Nachname" },
      { token: "{{ person.strasse }}", label: "Straße" },
      { token: "{{ person.plz_ort }}", label: "PLZ + Ort" },
    ],
  },
  {
    key: "organisation",
    label: "Organisation",
    icon: "building",
    items: [
      { token: "{{ organisation.name }}", label: "Organisation-Name" },
      { token: "{{ organisation.strasse }}", label: "Organisation-Straße" },
      { token: "{{ organisation.plz_ort }}", label: "Organisation PLZ + Ort" },
    ],
  },
  {
    key: "objekt",
    label: "Objekt",
    icon: "door",
    items: [
      { token: "{{ objekt.bezeichnung }}", label: "Objekts-Bezeichnung" },
      { token: "{{ objekt.qm }}", label: "Wohnfläche (m²)" },
      { token: "{{ standort.bezeichnung }}", label: "Standort" },
    ],
  },
  {
    key: "vertrag",
    label: "Vertrag & Beträge",
    icon: "euro",
    items: [
      { token: "{{ offener_betrag }}", label: "Offener Betrag (formatiert)", desc: "Aktueller Kontostand" },
      { token: "{{ betrag_offen }}", label: "Offener Betrag (Betrag)", desc: "Nur Zahl, ohne €" },
      { token: "{{ grundbetrag }}", label: "Grundbetrag" },
      { token: "{{ zuschlag }}", label: "Zuschlag" },
      { token: "{{ gesamtbetrag }}", label: "Gesamtbetrag" },
      { token: "{{ datensatz.von }}", label: "Einzug" },
      { token: "{{ datensatz.bis }}", label: "Auszug / Vertragsende" },
      { token: "{{ statuscode }}", label: "Statuscode" },
    ],
  },
  {
    key: "datum",
    label: "Datum & Fristen",
    icon: "calendar",
    items: [
      { token: "{{ datum }}", label: "Heute (formatiert)", desc: "21. Mai 2026" },
      { token: "{{ datum_iso }}", label: "Heute (ISO)", desc: "2026-05-21" },
      { token: "{{ stichtag }}", label: "Stichtag" },
      { token: "{{ frist_tage }}", label: "Frist (Tage)" },
    ],
  },
  {
    key: "bank",
    label: "Zahlungsdaten",
    icon: "credit-card",
    items: [
      { token: "{{ zahlungskonto.iban }}", label: "IBAN" },
      { token: "{{ zahlungskonto.bic }}", label: "BIC" },
      { token: "{{ zahlungskonto.bank }}", label: "Bank-Name" },
    ],
  },
];

export const SNIPPETS = [
  {
    key: "if",
    label: "Bedingung (if / endif)",
    desc: "{% if … %} … {% endif %}",
    value: `{% if BEDINGUNG %}\n\n{% endif %}`,
  },
  {
    key: "if-else",
    label: "Bedingung mit Else",
    desc: "{% if … %} … {% else %} … {% endif %}",
    value: `{% if BEDINGUNG %}\n\n{% else %}\n\n{% endif %}`,
  },
  {
    key: "if-eq",
    label: "Bedingung mit Vergleich",
    desc: "{% if x == \"Wert\" %} …",
    value: `{% if FELD == "WERT" %}\n\n{% endif %}`,
  },
  {
    key: "for",
    label: "Schleife (for / endfor)",
    desc: "{% for item in liste %} … {% endfor %}",
    value: `{% for item in liste %}\n\n{% endfor %}`,
  },
  {
    key: "set",
    label: "Variable setzen (set)",
    desc: "{% set name = wert %} — z. B. {% set stufe = serienbrief.werte.stufe | int %}",
    value: `{% set VARIABLE = WERT %}`,
  },
  // Freie Eingabe: kein fester ``value`` — der SlashMenu-UI rendert ein Inline-
  // Eingabefeld und konstruiert das Token aus ``custom.wrap`` + User-Input.
  {
    key: "custom-block",
    label: "Eigener {% Block %}",
    desc: "Beliebiger Jinja-Block — z. B. if loop.last, elif x > 0, endfor",
    custom: { wrap: "block", placeholder: "z. B. if loop.last" },
  },
  {
    key: "custom-expr",
    label: "Eigener {{ Ausdruck }}",
    desc: "Inline-Ausdruck — z. B. 'en' if _vm|length > 1 else ''",
    custom: { wrap: "expr", placeholder: "z. B. person.name | upper" },
  },
];

export const TEXT_BAUSTEINE = [
  { name: "Anrede formal", desc: "Sehr geehrte/r …,", preview: "Sehr geehrte/r {{ person.brief_anrede }} {{ person.nachname }}," },
  { name: "Unterschrift Organisation", desc: "Standard-Unterschriftsblock · Seitenumbruch davor", preview: "Mit freundlichen Grüßen\n\n{{ organisation.name }}\n\n_______________________________\n(i. A. Janis Peters)", pageBreakBefore: true },
  { name: "Fußzeile Zahlungsdaten", desc: "IBAN / BIC / Bank", preview: "Zahlungsdaten: {{ zahlungskonto.iban }} · BIC: {{ zahlungskonto.bic }} · {{ zahlungskonto.bank }}" },
  { name: "Hinweis Datenschutz", desc: "Standard DSGVO-Fußnote", preview: "Hinweis zum Datenschutz: Wir verarbeiten Ihre personenbezogenen Daten ausschließlich zur Durchführung des Vertragsverhältnisses und zur Erfüllung gesetzlicher Pflichten. Zielobjekt und Zwecke entnehmen Sie unserer Datenschutzerklärung. Sie haben das Recht auf Auskunft, Berichtigung, Löschung, Einschränkung sowie Widerspruch und Datenübertragbarkeit." },
  { name: "Bearbeitungsgebuehren-Klausel", desc: "§ 286 BGB-Hinweis", preview: "Hinweis nach § 286 BGB: Mit Ablauf der oben genannten Frist befinden Sie sich in Verzug. Wir behalten uns vor, Verzugszinsen in Höhe von 5 Prozentpunkten über dem Basiszinssatz sowie eine angemessene Bearbeitungspauschale geltend zu machen. Sollte auch nach Ablauf einer weiteren Frist keine Zahlung erfolgen, sind wir gezwungen, ein gerichtliches Verfahren einzuleiten und gegebenenfalls ein Inkasso-Unternehmen mit der Durchsetzung unserer Forderung zu beauftragen. Die dadurch entstehenden Kosten haben Sie zu tragen." },
];

export const TEMPLATE_VARIABLES = [
  { name: "frist_tage", type: "Zahl", default: "14", desc: "Zahlungsfrist in Tagen" },
  { name: "gebuehr", type: "Zahl", default: "5,00", desc: "Bearbeitungsgebuehr in Euro" },
  { name: "kontonummer", type: "String", default: "DE89 3704 0044 0532 0130 00", desc: "Zielobjekt-IBAN" },
];

export const TEMPLATE_TREE = [
  {
    key: "erinnerungen",
    label: "Erinnerungen",
    count: 8,
    pinned: true,
    templates: [
      { id: "t-001", title: "1. Erinnerung", modified: "Vor 2 Tagen", current: true },
      { id: "t-002", title: "2. Erinnerung", modified: "Vor 2 Tagen" },
      { id: "t-003", title: "3. Erinnerung (letzte Erinnerung)", modified: "Vor 1 Woche" },
      { id: "t-004", title: "Zahlungserinnerung freundlich", modified: "Vor 3 Wochen" },
      { id: "t-005", title: "Erinnerung Heizkosten-Vorauszahlung", modified: "Vor 1 Monat" },
      { id: "t-006", title: "Außergerichtliche Erinnerung", modified: "Vor 2 Monaten" },
      { id: "t-007", title: "Inkasso-Ankündigung", modified: "Vor 4 Monaten" },
      { id: "t-008", title: "Erinnerung mit Ratenangebot", modified: "Vor 5 Monaten" },
    ],
  },
  {
    key: "betriebskosten",
    label: "Betriebskostenabrechnung",
    count: 6,
    templates: [
      { id: "t-101", title: "BK-Abrechnung Anschreiben", modified: "Vor 1 Woche" },
      { id: "t-102", title: "BK-Nachzahlungs-Anforderung", modified: "Vor 2 Wochen" },
      { id: "t-103", title: "BK-Guthaben-Erstattung", modified: "Vor 2 Wochen" },
      { id: "t-104", title: "Vorauszahlungs-Anpassung", modified: "Vor 1 Monat" },
      { id: "t-105", title: "Widerspruch-Antwort BK", modified: "Vor 3 Monaten" },
      { id: "t-106", title: "BK-Erläuterung Person", modified: "Vor 6 Monaten" },
    ],
  },
  {
    key: "datensatz",
    label: "Zielobjekt",
    count: 11,
    templates: [
      { id: "t-201", title: "Zielobjekt Standard", modified: "Vor 1 Monat" },
      { id: "t-202", title: "Zielobjekt Staffel", modified: "Vor 2 Monaten" },
      { id: "t-203", title: "Kündigung Person (Bestätigung)", modified: "Vor 3 Wochen" },
      { id: "t-204", title: "Kündigung Verperson (Eigenbedarf)", modified: "Vor 2 Monaten" },
      { id: "t-205", title: "Personhöhung nach Mietspiegel", modified: "Vor 1 Woche" },
      { id: "t-206", title: "Personhöhung Modernisierung", modified: "Vor 2 Monaten" },
      { id: "t-207", title: "Objekts-Übergabeprotokoll", modified: "Vor 3 Wochen" },
    ],
  },
  {
    key: "kontakt",
    label: "Kontakt / WEG",
    count: 4,
    templates: [
      { id: "t-301", title: "WEG-Einladung Versammlung", modified: "Vor 1 Woche" },
      { id: "t-302", title: "Hausgeld-Abrechnung", modified: "Vor 2 Wochen" },
      { id: "t-303", title: "Sonderumlage-Ankündigung", modified: "Vor 1 Monat" },
      { id: "t-304", title: "Beschlussfassung Protokoll", modified: "Vor 2 Monaten" },
    ],
  },
  {
    key: "allgemein",
    label: "Allgemein",
    count: 5,
    templates: [
      { id: "t-401", title: "Hausordnung Verteilung", modified: "Vor 3 Monaten" },
      { id: "t-402", title: "Reparatur-Ankündigung", modified: "Vor 1 Woche" },
      { id: "t-403", title: "Ablesung Heizkosten", modified: "Vor 2 Monaten" },
      { id: "t-404", title: "Schlüssel-Übergabe", modified: "Vor 1 Monat" },
      { id: "t-405", title: "Adress-Änderung Organisation", modified: "Vor 4 Monaten" },
    ],
  },
  {
    key: "import",
    label: "Dokumentvorlagen Import",
    count: 412,
    templates: [
      { id: "t-901", title: "Altbestand: Anschreiben Person", modified: "Importiert" },
      { id: "t-902", title: "Altbestand: BK 2022 Vorlage", modified: "Importiert" },
    ],
  },
];

// Demo-Vorlage "1. Erinnerung" im DB-Format (rohe Jinja-Tokens) – nur für Standalone-Dev
// (npm run dev). Dogfoodt: Ausrichtung, Marks, Baustein, Platzhalter, Tabellen-Loop, if-Block.
export const CURRENT_TEMPLATE = {
  id: "t-001",
  title: "1. Erinnerung",
  kategorie: "Erinnerungen",
  haupt_verteil_objekt: "Zielobjekt",
  content_type: "Textbaustein (Rich Text)",
  content_position: "Nach Bausteinen",
  modified: "21.05.2026 14:32",
  modified_by: "j.peters@example.de",
  canWrite: true,
  htmlContent: `<p style="text-align: right">M\u00fcnchen, {{ datum }}</p>
<p>{{ person.anrede }} {{ person.vorname }} {{ person.nachname }}</p>
<p>{{ person.strasse }}</p>
<p>{{ person.plz_ort }}</p>
<h2>Zahlungserinnerung \u2014 Zielobjekt {{ objekt.bezeichnung }}</h2>
<div>{{ baustein("Anrede formal") }}</div>
<p>auf dem Konto Ihrer Objekt {{ objekt.bezeichnung }} in der {{ standort.bezeichnung }} ist aktuell ein offener Offener Betrag in H\u00f6he von <strong>{{ offener_betrag }}</strong> ausgewiesen.</p>
<p>Die offenen Posten im Einzelnen:</p>
<table><thead><tr><th>Rechnung</th><th>F\u00e4llig</th><th style="text-align: right">Offen</th></tr></thead><tbody>
{% for row in payments %}
<tr><td>{{ row.sales_invoice }}</td><td>{{ row.due_date }}</td><td style="text-align: right">{{ row.outstanding }}</td></tr>
{% endfor %}
</tbody></table>
<p>Wir bitten Sie h\u00f6flich, den f\u00e4lligen Betrag bis sp\u00e4testens {{ stichtag }} (Frist: {{ frist_tage }} Tage) zu \u00fcberweisen.</p>
{% if statuscode == "2" %}
<p>Da es sich um die zweite Erinnerung handelt, erheben wir eine Bearbeitungsgebuehr in H\u00f6he von 5,00 \u20ac.</p>
{% endif %}
<p>Sollten Sie den Betrag bereits \u00fcberwiesen haben, betrachten Sie dieses Schreiben bitte als gegenstandslos.</p>
<div>{{ baustein("Unterschrift Organisation") }}</div>`,
};
