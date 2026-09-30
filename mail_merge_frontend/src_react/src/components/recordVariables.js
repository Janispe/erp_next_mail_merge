// Doctype-Variablen der Vorlage: entweder Pfad ab dem Objekt oder fest gewählter
// Datensatz (Wert = Name, bei "Doctype Liste" = Liste von Namen). Das Backend
// lädt den Datensatz beim Rendern in den Kontext; Baustein-Pfade können dann
// bei der Variable beginnen (z. B. Briefkopf address -> anwalt_adresse).

export const isRecordType = (type) => type === "Doctype" || type === "Doctype Liste";

const hasRecord = (value) =>
  Array.isArray(value) ? value.length > 0 : value != null && String(value).trim() !== "";

// "record" | "path". `source` hält die Auswahl, solange noch nichts eingetragen ist.
export const variableSource = (v) => {
  if (v?.source === "record" || v?.source === "path") return v.source;
  return hasRecord(v?.value) ? "record" : "path";
};

// Beim Umschalten die jeweils andere Angabe leeren: nie Pfad und Datensatz zugleich.
export const switchVariableSource = (v, source) =>
  source === "record"
    ? { ...v, source, path: "" }
    : { ...v, source, value: "" };

export const recordNames = (value) => {
  if (Array.isArray(value)) return value.filter((name) => String(name || "").trim() !== "");
  return hasRecord(value) ? [String(value)] : [];
};

// Wert einer Doctype-Variable nach Auswahl: einzelner Name oder Namensliste.
export const withRecord = (v, name) => {
  if (v.type === "Doctype Liste") {
    const names = recordNames(v.value);
    return names.includes(name) ? v : { ...v, source: "record", value: [...names, name] };
  }
  return { ...v, source: "record", value: name };
};

export const withoutRecord = (v, name) =>
  v.type === "Doctype Liste"
    ? { ...v, value: recordNames(v.value).filter((item) => item !== name) }
    : { ...v, value: "" };

// Belegungsprofil: gewählter Datensatz als value, sonst der Pfad.
export const assignmentEntry = (v) =>
  variableSource(v) === "record" ? { value: v.value ?? "" } : { path: v.path || "" };

export const applyAssignmentEntry = (v, entry = {}) =>
  hasRecord(entry.value)
    ? { ...v, source: "record", value: entry.value, path: "" }
    : { ...v, source: "path", value: "", path: entry.path ?? "" };

// Vorlagen-Variablen mit Referenz-Doctype als zusätzliche Anfangspunkte im Pfad-Picker.
export const recordVariableRoots = (variables) =>
  (variables || [])
    .filter((v) => isRecordType(v.type) && String(v.variable || "").trim() && v.reference_doctype)
    .map((v) => ({
      path: String(v.variable).trim(),
      type: v.reference_doctype,
      label: `Vorlagen-Variable ${String(v.variable).trim()}`,
    }));
