import React, { useEffect, useMemo, useRef, useState } from "react";
import { embedded, gotoDurchlauf } from "./api.js";
import { describeTemplate, effectiveValue, findRecipients, findTemplates, missingFields, previewLetters, saveLetters } from "./composerApi.js";
import "./composer.css";

const steps = ["Vorlage", "Empfänger", "Angaben", "Vorschau", "Speichern"];
const originLabels = { template: "Vorlagenwert", common: "Für alle eingesetzt", individual: "Individuell eingesetzt" };
const previewDocument = (html) => `<!doctype html><html lang="de"><head><meta charset="utf-8"><style>body{margin:0;padding:42px;background:white;color:#242d36;font:15px/1.65 Arial,sans-serif}h2{font-size:20px;margin-top:42px}.sender{font-size:10px;letter-spacing:.06em;color:#56616c}p{margin:0 0 18px}img{max-width:100%}</style></head><body>${html || ""}</body></html>`;

function FieldInput({ field, value, onChange, disabled, error }) {
  const props = { id: `lc-field-${field.name}`, "aria-label": field.label, "aria-invalid": !!error, disabled };
  if (field.type === "Bool") return <select {...props} value={value == null || value === "" ? "" : String(value)} onChange={e => onChange(e.target.value === "" ? "" : e.target.value === "true")}><option value="">Bitte wählen</option><option value="true">Ja</option><option value="false">Nein</option></select>;
  if (field.type === "Text") return <textarea {...props} rows={2} maxLength={4000} value={value ?? ""} onChange={e => onChange(e.target.value)}/>;
  return <input {...props} type={field.type === "Datum" ? "date" : field.type === "Zahl" ? "number" : "text"} step="any" value={value ?? ""} onChange={e => onChange(field.type === "Zahl" && e.target.value !== "" ? Number(e.target.value) : e.target.value)}/>;
}

export function LetterComposer({ preselect = "", onClose, onBusyChange }) {
  const [step, setStep] = useState(0);
  const [query, setQuery] = useState("");
  const [templates, setTemplates] = useState([]);
  const [template, setTemplate] = useState(null);
  const [templateBusy, setTemplateBusy] = useState(false);
  const [recipientQuery, setRecipientQuery] = useState("");
  const [options, setOptions] = useState([]);
  const [offset, setOffset] = useState(0);
  const [more, setMore] = useState(false);
  const [selected, setSelected] = useState([]);
  const [values, setValues] = useState({});
  const [individual, setIndividual] = useState({});
  const [scope, setScope] = useState("all");
  const [current, setCurrent] = useState("");
  const [result, setResult] = useState(null);
  const [previewKey, setPreviewKey] = useState("");
  const [saved, setSaved] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [attempted, setAttempted] = useState(false);
  const selectionRequest = useRef(0);
  const fields = template?.fields || [];
  const payload = useMemo(() => ({ template: template?.name, revision: template?.revision, recipients: selected.map(r => r.id), values, individual }), [template, selected, values, individual]);
  const inputKey = JSON.stringify(payload);
  const stale = !!result && previewKey !== inputKey;
  const issues = Object.fromEntries(selected.map(r => [r.id, missingFields(fields, values, individual[r.id]?.values)]));
  const missingCount = selected.filter(r => Object.keys(issues[r.id]).length).length;
  const check = result?.checks.find(c => c.recipient === current) || result?.checks[0];
  const disabled = busy || !!saved;
  useEffect(() => { onBusyChange?.(busy || templateBusy); }, [busy, templateBusy, onBusyChange]);

  useEffect(() => { let active = true; findTemplates(query).then(items => { if (active) setTemplates(items || []); }).catch(e => { if (active) setError(e.message); }); return () => { active = false; }; }, [query]);
  const chooseTemplate = async id => {
    const request = ++selectionRequest.current;
    setTemplateBusy(true); setError("");
    try {
      const next = await describeTemplate(id);
      if (request !== selectionRequest.current) return;
      setTemplate(next); setSelected([]); setValues({}); setIndividual({}); setScope("all"); setResult(null); setSaved(null); setAttempted(false); setOffset(0); setRecipientQuery("");
    } catch (e) { setError(e.message); }
    finally { if (request === selectionRequest.current) setTemplateBusy(false); }
  };
  useEffect(() => { if (preselect) chooseTemplate(preselect); }, [preselect]);
  useEffect(() => {
    if (!template) return;
    let active = true;
    findRecipients(template.name, recipientQuery, offset).then(res => { if (active) { setOptions(res.items); setMore(res.has_more); } }).catch(e => { if (active) setError(e.message); });
    return () => { active = false; };
  }, [template, recipientQuery, offset]);
  useEffect(() => {
    const warn = e => { if (!saved && selected.length) { e.preventDefault(); e.returnValue = ""; } };
    window.addEventListener("beforeunload", warn); return () => window.removeEventListener("beforeunload", warn);
  }, [saved, selected.length]);

  const changeIndividual = (id, key, value) => setIndividual(prev => ({ ...prev, [id]: { ...prev[id], [key]: value } }));
  const setField = (field, value) => {
    if (scope === "all") setValues(prev => ({ ...prev, [field.name]: value }));
    else changeIndividual(scope, "values", { ...individual[scope]?.values, [field.name]: value });
  };
  const toggleOverride = (field, on) => {
    const next = { ...individual[scope]?.values };
    if (on) next[field.name] = effectiveValue(field, values, {}) ?? "";
    else delete next[field.name];
    changeIndividual(scope, "values", next);
  };
  const preview = async () => {
    setBusy(true); setError(""); setAttempted(true);
    const key = inputKey;
    try { const next = await previewLetters(payload); setResult(next); setPreviewKey(key); setCurrent(selected[0]?.id || ""); setStep(3); }
    catch (e) { setError(e.message || "Die Vorschau konnte nicht erstellt werden."); }
    finally { setBusy(false); }
  };
  const save = async () => {
    if (!result?.ready || stale || saved || busy) return;
    setBusy(true); setError("");
    try { setSaved(await saveLetters(result.token)); }
    catch (e) { setError(e.message || "Speichern fehlgeschlagen. Ihre Angaben bleiben erhalten."); }
    finally { setBusy(false); }
  };
  const editRecipient = id => { setScope(id); setStep(2); setAttempted(true); };

  return <div className="letter-composer">
    <header className="lc-header"><div><div className="lc-eyebrow">SERIENBRIEFE <span>Prototyp</span></div><h1>Brief erstellen</h1><p>Von der Vorlage zum persönlichen Brief.</p></div><div className="lc-header-links">{onClose && <button className="lc-link" disabled={busy} onClick={onClose}>Zurück zum Durchlauf</button>}<a href="/app/serienbrief_browser" target="_top">Vorlagen bearbeiten ↗</a></div></header>
    {!embedded && <div className="lc-demo">Interaktive Demo mit Beispieldaten · Hier werden keine echten Briefe gespeichert.</div>}
    <nav className="lc-steps" aria-label="Schritte zur Brieferstellung">{steps.map((label, i) => <button key={label} disabled={busy || !!saved || i > step} aria-current={i === step ? "step" : undefined} onClick={() => setStep(i)}><span>{i < step ? "✓" : i + 1}</span>{label}</button>)}</nav>
    <main className="lc-main">
      {error && <div role="alert" className="lc-alert lc-error">{error}</div>}
      {stale && !saved && <div role="status" className="lc-alert lc-warning">Ihre Angaben wurden geändert. Die bisherige Vorschau enthält diese Änderung noch nicht. Bitte vor dem Speichern erneut prüfen.</div>}
      {step === 0 && <section><div className="lc-section-heading"><h2>Welchen Brief möchten Sie erstellen?</h2><p>Wählen Sie eine Vorlage. Sie bestimmt die ausfüllbaren Angaben und optionalen Inhalte.</p></div><label className="lc-search">Vorlage suchen<input value={query} onChange={e => setQuery(e.target.value)} placeholder="Zum Beispiel Ablesetermin oder Information …"/></label><div className="lc-template-grid">{templates.map(t => <button className={`lc-template ${template?.name === t.id ? "selected" : ""}`} key={t.id} disabled={templateBusy} onClick={() => chooseTemplate(t.id)}><span className="lc-category">{t.kategorie || "Vorlage"}</span><strong>{t.title || t.id}</strong><span>{t.description || t.iteration_doctype || "Vorlage auswählen und Angaben prüfen"}</span>{template?.name === t.id && <b>✓ Ausgewählt</b>}</button>)}</div>{templateBusy && <p role="status">Vorlage wird geladen …</p>}{template && <div className="lc-template-summary"><strong>{template.title}</strong><p>{template.description || `${fields.length} ausfüllbare Angaben · Empfängertyp: ${template.recipient_doctype}`}</p></div>}{!templates.length && <p>Keine Vorlage gefunden. Bitte einen anderen Suchbegriff verwenden.</p>}</section>}
      {step === 1 && <section><div className="lc-section-heading"><h2>An wen geht der Brief?</h2><p>{template.title} · Bis zu {template.max_recipients} Empfänger pro Vorschau im Prototyp.</p></div><div className="lc-two-col"><div><label className="lc-search">Empfänger suchen<input value={recipientQuery} onChange={e => { setRecipientQuery(e.target.value); setOffset(0); }} placeholder="Name oder Datensatz-ID …"/></label><div className="lc-recipient-options">{options.map(r => <label key={r.id}><input type="checkbox" checked={selected.some(s => s.id === r.id)} disabled={!selected.some(s => s.id === r.id) && selected.length >= template.max_recipients} onChange={e => { if (e.target.checked) setSelected(prev => [...prev, r]); else { setSelected(prev => prev.filter(s => s.id !== r.id)); setIndividual(prev => { const next = { ...prev }; delete next[r.id]; return next; }); } }}/><span><strong>{r.label}</strong><small>{r.id}</small></span></label>)}</div>{!options.length && <p>Keine passenden Empfänger gefunden.</p>}<div className="lc-pagination"><button disabled={!offset} onClick={() => setOffset(Math.max(0, offset - 20))}>Vorherige</button><button disabled={!more} onClick={() => setOffset(offset + 20)}>Weitere Empfänger</button></div></div><aside className="lc-card"><h3>Ihre Auswahl <span className="lc-count">{selected.length}</span></h3>{selected.length ? selected.map(r => <p key={r.id}>✓ {r.label}</p>) : <p>Noch keine Empfänger ausgewählt.</p>}</aside></div></section>}
      {step === 2 && <section><div className="lc-section-heading"><h2>Angaben aus der Vorlage</h2><p>Gemeinsame Angaben gelten für alle. Individuelle Angaben ersetzen sie nur beim ausgewählten Empfänger.</p></div><div className="lc-scope"><label>Bearbeiten für<select value={scope} disabled={disabled} onChange={e => { setScope(e.target.value); }}><option value="all">Alle Empfänger gemeinsam</option>{selected.map(r => <option key={r.id} value={r.id}>{r.label}</option>)}</select></label><span className={missingCount ? "lc-chip warning" : "lc-chip success"}>{missingCount ? `${missingCount} Empfänger: Angaben fehlen` : `${selected.length} Empfänger: Angaben vollständig`}</span></div><div className="lc-two-col"><div className="lc-card"><h3>{scope === "all" ? "Gemeinsame Angaben" : "Individuelle Angaben"}</h3>{fields.map(field => { const own = Object.hasOwn(individual[scope]?.values || {}, field.name); const value = effectiveValue(field, values, scope === "all" ? {} : individual[scope]?.values); const fieldError = attempted ? (scope === "all" ? selected.some(r => issues[r.id][field.name]) ? `${field.label} fehlt für mindestens einen Empfänger.` : null : issues[scope]?.[field.name]) : null; return <div className="lc-field" key={field.name}><label htmlFor={`lc-field-${field.name}`}>{field.label} {field.required ? <span className="lc-required">Pflichtangabe</span> : <small>optional</small>}</label>{scope !== "all" && <label className="lc-inline-check"><input type="checkbox" checked={own} disabled={disabled} onChange={e => toggleOverride(field, e.target.checked)}/> Eigener Wert für diesen Empfänger</label>}<FieldInput field={field} value={value} disabled={disabled || (scope !== "all" && !own)} onChange={v => setField(field, v)} error={fieldError}/>{field.description && <small>{field.description}</small>}{fieldError && <span className="lc-field-error" role="alert">{fieldError}</span>}</div>; })}{!fields.length && <p>Diese Vorlage bezieht ihre Angaben direkt aus den Empfängerdaten.</p>}</div><aside className="lc-card"><h3>Inhalte pro Empfänger steuern</h3><p>Die Vorlage legt fest, welche Texte und Schalter verfügbar sind. Ja/Nein-Variablen können beispielsweise einzelne Absätze ein- oder ausblenden.</p><p>Wählen Sie oben einen Empfänger und aktivieren Sie beim gewünschten Feld „Eigener Wert“. So können Sie einen Inhalt nur für diesen Empfänger ausschalten oder einen anderen Text einsetzen.</p></aside></div></section>}
      {step === 3 && <section><div className="lc-section-heading"><h2>Briefe prüfen</h2><p>Prüfen Sie jeden Empfänger. Die Leseansicht zeigt die ausgefüllte Vorlage; das PDF zeigt das endgültige Layout.</p></div><div className="lc-review-layout"><aside className="lc-card"><h3>Empfängerprüfung</h3>{result?.checks.map(c => <button key={c.recipient} className={`lc-check ${check?.recipient === c.recipient ? "active" : ""}`} onClick={() => setCurrent(c.recipient)}><strong>{selected.find(r => r.id === c.recipient)?.label || c.recipient}</strong><span className={`lc-chip ${c.status === "ready" ? "success" : "warning"}`}>{c.status === "ready" ? "Vollständig" : c.status === "missing" ? "Angaben fehlen" : "Renderfehler"}</span></button>)}<button className="lc-secondary" disabled={busy} onClick={preview}>{busy ? "Vorschau wird erstellt …" : "Vorschau aktualisieren"}</button></aside><div>{check?.status === "ready" ? <><div className="lc-preview-toolbar"><span>Ausgefüllte Vorlage</span>{check.pdf_url && <a href={check.pdf_url} target="_blank" rel="noreferrer">PDF-Vorschau öffnen ↗</a>}</div><iframe className="lc-paper" title="Briefvorschau" sandbox="" srcDoc={previewDocument(check.html)}/></> : <div className="lc-card lc-error-detail"><h3>{check?.status === "missing" ? "Hier fehlen noch Angaben" : "Dieser Brief konnte nicht erstellt werden"}</h3>{Object.entries(check?.fields || {}).map(([key, text]) => <p key={key}>{text}</p>)}{check?.message && <p>{check.message}</p>}<button onClick={() => editRecipient(check.recipient)}>Angaben korrigieren</button></div>}</div><aside className="lc-card lc-changes"><h3>Was wurde eingesetzt?</h3><p>Die Vorlage bestimmt Text und Position. Schalter steuern die darin vorgesehenen optionalen Inhalte.</p>{check?.changes.map((c, i) => <div className="lc-change" key={i}><small>{c.label}</small><strong>{c.value === false ? "Nein" : c.value === true ? "Ja" : String(c.value ?? "—")}</strong><span>{originLabels[c.origin]}</span></div>)}</aside></div></section>}
      {step === 4 && <section className="lc-save"><div className="lc-save-icon">{saved ? "✓" : "↓"}</div><h2>{saved ? embedded ? "Ihre Briefentwürfe sind gespeichert" : "Demo abgeschlossen" : "Geprüfte Briefe als Entwurf speichern"}</h2><p>{saved ? embedded ? "Die gespeicherten PDFs entsprechen genau Ihrer Vorschau." : "In der Demo wurden keine Datensätze oder PDFs gespeichert." : `${selected.length} ${selected.length === 1 ? "Brief" : "Briefe"} · ${template.title}`}</p><div className="lc-card"><p>✓ Eingaben geprüft</p><p>✓ Gemeinsame und individuelle Variablenwerte berücksichtigt</p><p>✓ Standardvorlage unverändert</p><p>Speichern legt Entwürfe an. Es erfolgt kein Versand und kein Einreichen.</p></div>{saved ? embedded && <button className="lc-primary" onClick={() => gotoDurchlauf(saved.docname)}>Gespeicherten Durchlauf öffnen</button> : <button className="lc-primary" onClick={save} disabled={disabled || stale || !result?.ready}>{busy ? "Wird gespeichert …" : "Als Entwurf speichern"}</button>}</section>}
    </main>
    <footer className="lc-footer"><span>{template?.title || "Noch keine Vorlage ausgewählt"}{selected.length > 0 && ` · ${selected.length} Empfänger`}</span><div>{step > 0 && !saved && <button className="lc-secondary" disabled={busy} onClick={() => setStep(step - 1)}>Zurück</button>}{step < 2 && <button className="lc-primary" disabled={busy || templateBusy || !template || (step === 1 && !selected.length)} onClick={() => { setError(""); setStep(step + 1); }}>{step === 0 ? "Empfänger auswählen" : "Angaben ausfüllen"} →</button>}{step === 2 && <button className="lc-primary" disabled={busy} onClick={preview}>{busy ? "Briefe werden geprüft …" : "Vorschau prüfen"} →</button>}{step === 3 && <button className="lc-primary" disabled={busy || stale || !result?.ready} onClick={() => setStep(4)}>Weiter zum Speichern →</button>}</div></footer>
  </div>;
}
