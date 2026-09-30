import React, { useEffect, useState } from "react";
import { searchRecords } from "./api.js";

const isRecord = v => v.type === "Doctype" || v.type === "Doctype Liste";
const names = value => (Array.isArray(value) ? value : value ? [String(value)] : []).filter(Boolean);
const display = value => value === true ? "Ja" : value === false ? "Nein" : Array.isArray(value) ? (value.length ? value.join(", ") : "(leer)") : value === "" || value == null ? "(leer)" : String(value);

// Fester Datensatz (z. B. Kontakt der Kanzlei) für diesen Lauf bzw. Empfänger.
// Leer = Vorgabe der Vorlage bzw. Pfad ab dem Objekt.
export function RecordField({ variable, value, disabled, onChange }) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState([]);
  const [error, setError] = useState("");
  const list = variable.type === "Doctype Liste";
  const chosen = names(value);
  const doctype = variable.reference_doctype || "";
  useEffect(() => {
    if (!open || !doctype) return undefined;
    let alive = true;
    const timer = setTimeout(() => searchRecords(doctype, query)
      .then(r => { if (alive) { setItems(r?.items || []); setError(""); } })
      .catch(e => { if (alive) { setItems([]); setError(e?.message || "Suche fehlgeschlagen"); } }), 200);
    return () => { alive = false; clearTimeout(timer); };
  }, [open, doctype, query]);
  const choose = id => { onChange(list ? [...chosen.filter(n => n !== id), id] : id); setQuery(""); setOpen(false); };
  const drop = id => onChange(list ? chosen.filter(n => n !== id) : "");
  return <div className="dl-record">
    {chosen.length > 0 && <div className="dl-record-chips">{chosen.map(id => <span key={id} className="dl-record-chip">{id}<button type="button" disabled={disabled} aria-label={`${id} entfernen`} onClick={() => drop(id)}>×</button></span>)}</div>}
    {(list || !chosen.length) && <input className="dl-var-input" aria-label={variable.label || variable.name} disabled={disabled || !doctype} value={query}
      placeholder={variable.path ? `Aus Pfad: ${variable.path} – oder ${doctype} wählen` : `${doctype} suchen…`}
      onChange={e => setQuery(e.target.value)} onFocus={() => setOpen(true)} onBlur={() => setTimeout(() => setOpen(false), 150)}/>}
    {open && (items.length > 0 || error) && <div className="dl-record-results" role="listbox">
      {error && <div className="dl-var-desc">{error}</div>}
      {items.filter(item => !chosen.includes(item.id)).map(item => <button type="button" role="option" key={item.id} onMouseDown={e => { e.preventDefault(); choose(item.id); }}>
        {item.label}{item.label !== item.id && <small>{item.id}</small>}</button>)}
    </div>}
  </div>;
}
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
      {isRecord(v) ? <RecordField variable={v} value={value} disabled={disabled} onChange={next => onChange(v.name, next)}/>
        : v.type === "Bool" ? <select {...props} value={value === true || value === 1 || value === "1" || value === "true" ? "true" : value === false || value === 0 || value === "0" || value === "false" ? "false" : ""} onChange={e => onChange(v.name, e.target.value === "" ? "" : e.target.value === "true")}><option value="">Nicht gesetzt</option><option value="true">Ja</option><option value="false">Nein</option></select>
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
