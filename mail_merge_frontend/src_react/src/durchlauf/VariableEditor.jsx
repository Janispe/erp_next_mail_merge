import React from "react";

const display = value => value === true ? "Ja" : value === false ? "Nein" : value === "" || value == null ? "(leer)" : String(value);
export function VariableEditor({ variables, resolvedValues = {}, overrides = {}, individual = false, disabled, onChange, onReset }) {
  return <div className="dl-vars">{variables.map(v => {
    const own = individual && Object.hasOwn(overrides, v.name);
    const inherited = v.value ?? (individual ? resolvedValues[v.name] : undefined);
    const value = own ? overrides[v.name] : inherited;
    const props = { className: "dl-var-input", "aria-label": v.label || v.name, disabled, placeholder: v.path ? `Aus Pfad: ${v.path}` : "", value: value ?? "" };
    return <div className={`dl-var ${own ? "dl-var-overridden" : ""}`} key={v.name}>
      <div className="dl-var-head"><span className="dl-var-name">{v.label || v.name}</span><span className="dl-var-type">{v.type}</span></div>
      {v.desc && <div className="dl-var-desc">{v.desc}</div>}
      {individual && <div className="dl-variable-origin">{own ? "Individueller Wert" : "Gemeinsamer Wert"}</div>}
      {v.type === "Bool" ? <select {...props} value={value === true || value === 1 || value === "1" || value === "true" ? "true" : value === false || value === 0 || value === "0" || value === "false" ? "false" : ""} onChange={e => onChange(v.name, e.target.value === "" ? "" : e.target.value === "true")}><option value="">Nicht gesetzt</option><option value="true">Ja</option><option value="false">Nein</option></select>
        : v.type === "Text" ? <textarea {...props} rows={4} onChange={e => onChange(v.name, e.target.value)}/>
        : <input {...props} type={v.type === "Datum" ? "date" : "text"} inputMode={v.type === "Zahl" ? "decimal" : undefined} onChange={e => onChange(v.name, e.target.value)}/>}
      {own && <div className="dl-variable-reset"><span>Für alle: {display(inherited)}</span><button type="button" disabled={disabled} onClick={() => onReset(v.name)}>Gemeinsamen Wert verwenden</button></div>}
    </div>;
  })}{!variables.length && <p>Keine ausfüllbaren Vorlagenvariablen vorhanden.</p>}</div>;
}

export function VariableValues({ variables, resolvedValues = {}, overrides = {} }) {
  return <div className="dl-vars">{variables.map(v => {
    const own = Object.hasOwn(overrides, v.name);
    const inherited = v.value ?? resolvedValues[v.name];
    const value = own ? overrides[v.name] : inherited;
    const origin = own ? "Individueller Wert" : v.value != null ? "Gemeinsamer Wert / Vorgabe" : "Aus Datenpfad";
    const shown = v.type === "Datum" && /^\d{4}-\d{2}-\d{2}$/.test(value || "") ? value.split("-").reverse().join(".") : display(value);
    return <div className={`dl-var ${own ? "dl-var-overridden" : ""}`} key={v.name}>
      <div className="dl-var-head"><span className="dl-var-name">{v.label || v.name}</span><span className="dl-var-type">{v.type}</span></div>
      <div className="dl-variable-origin">{origin}</div>
      <div className="dl-var-readonly" style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{shown}</div>
      {v.path && <div className="dl-var-desc">Pfad: {v.path}</div>}
    </div>;
  })}{!variables.length && <p>Keine Variablen vorhanden.</p>}</div>;
}
