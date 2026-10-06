import React from "react";

export function PreviewFeedback({ report }) {
  const errors = typeof report === "string" ? [{ message: report }] : (report?.errors || []);
  if (!errors.length) return report?.placeholder_mode ? (
    <section className="preview-feedback inputs" role="status"><strong>Layoutvorschau mit Variablennamen</strong>
      <p>Offene Werte erscheinen als [variablenname]. Bedingungen verwenden Beispielwerte. Prüfe den Brief anschließend mit echten Eingaben.</p>
    </section>
  ) : null;
  const inputsOnly = errors.every((error) => ["provide_inputs", "correct_inputs"].includes(error.action));
  return (
    <section className={`preview-feedback ${inputsOnly ? "inputs" : "failure"}`} role="status">
      <strong>{inputsOnly ? "Angaben für die Vorschau fehlen oder sind ungültig" : "Vorschau konnte nicht erstellt werden"}</strong>
      {inputsOnly && <p>Das sind offene Eingaben, kein Fehler im Vorlagentext. Trage die Vorschauwerte ein und rendere erneut. Die Werte werden nicht gespeichert.</p>}
      {errors.map((error, index) => (
        <div key={index} className="preview-feedback-item">
          {!inputsOnly && <p>{error.message}</p>}
          {!!error.issues?.length && <ul>{error.issues.map((issue, i) => (
            <li key={`${issue.field || "location"}-${i}`}>
              <strong>{issue.label || issue.field || "Vorlage"}</strong>
              {issue.type && <span> · {issue.type === "Datum" ? "Datum (JJJJ-MM-TT)" : issue.type}</span>}
              {issue.path && <span> · Datenpfad: <code>{issue.path}</code></span>}
            </li>
          ))}</ul>}
          {error.action === "check_recipient_data" && <p>Prüfe die Daten des Zielobjekts und die zugeordneten Feldpfade.</p>}
          {error.action === "review_template" && <p>Prüfe den Vorlagentext beziehungsweise den betroffenen Textbaustein.</p>}
          {error.action === "check_pdf_renderer" && <p>Die PDF-Verarbeitung ist fehlgeschlagen. Bitte erneut versuchen; bei wiederholtem Fehler die PDF-Erzeugung prüfen.</p>}
          {error.diagnostic && <details>
            <summary>Technische Hinweise</summary>
            <p>{error.diagnostic.exception_type}: {error.diagnostic.message}</p>
            {error.diagnostic.baustein && <p>Textbaustein: {error.diagnostic.baustein}</p>}
            {error.diagnostic.line && <p>Jinja-Zeile {error.diagnostic.line} im verarbeiteten Quelltext; sie kann von der Editor-Zeile abweichen.</p>}
          </details>}
        </div>
      ))}
    </section>
  );
}

export function PreviewValueInput({ field, value, onChange }) {
  const shown = value ?? "";
  if (field.type === "Bool") return <select aria-label={field.label || field.field} value={String(shown)} onChange={(e) => onChange(e.target.value === "" ? "" : e.target.value === "true")}>
    <option value="">Keine Angabe</option><option value="true">Ja</option><option value="false">Nein</option>
  </select>;
  if (field.type === "Doctype Liste") return <textarea aria-label={field.label || field.field} value={Array.isArray(shown) ? shown.join("\n") : shown} placeholder="Exakte Datensatznamen, einer pro Zeile" onChange={(e) => onChange(e.target.value.split("\n").filter(Boolean))}/>;
  if (["Text", "String"].includes(field.type)) return <textarea aria-label={field.label || field.field} value={shown} rows={2} onChange={(e) => onChange(e.target.value)} placeholder="Wert nur für diese Vorschau"/>;
  return <input aria-label={field.label || field.field} type={field.type === "Datum" ? "date" : field.type === "Zahl" ? "number" : "text"} step={field.type === "Zahl" ? "any" : undefined} value={shown} onChange={(e) => onChange(field.type === "Zahl" && e.target.value !== "" ? Number(e.target.value) : e.target.value)} placeholder={field.type === "Doctype" ? "Exakter Name eines vorhandenen Datensatzes" : "Vorschauwert"}/>;
}
