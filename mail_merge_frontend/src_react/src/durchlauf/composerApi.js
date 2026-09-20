import { rpc } from "../bridge.js";
import { embedded, listVorlagen } from "./api.js";

const templates = [
  { id: "demo-ablesetermin", title: "Ablesetermin ankündigen", kategorie: "Termine", description: "Ein Terminbrief mit gemeinsamen Angaben und optionalem Zugangshinweis." },
  { id: "demo-information", title: "Information an die Hausgemeinschaft", kategorie: "Information", description: "Eine kurze Mitteilung mit einer frei ausfüllbaren Nachricht." },
];
const recipients = [
  { id: "DEMO-MV-001", label: "Anna Beispiel · Gartenstraße 12, 1. OG links" },
  { id: "DEMO-MV-002", label: "Ben Muster · Gartenstraße 12, 2. OG rechts" },
  { id: "DEMO-MV-003", label: "Clara Beispiel · Gartenstraße 12, EG" },
];
export const escape = value => String(value ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
export const effectiveValue = (field, values, individual) => Object.hasOwn(individual || {}, field.name) ? individual[field.name] : Object.hasOwn(values || {}, field.name) ? values[field.name] : field.default;
export function missingFields(fields, values, individual) {
  return Object.fromEntries(fields.filter(f => {
    const value = effectiveValue(f, values, individual);
    return f.required && (value == null || (typeof value === "string" && !value.trim()));
  }).map(f => [f.name, `${f.label} fehlt.`]));
}
export async function findTemplates(query) {
  if (embedded) return (await listVorlagen(query)).items;
  return templates.filter(t => t.title.toLowerCase().includes(query.toLowerCase()));
}
export async function describeTemplate(template) {
  if (embedded) return rpc("composer_template", { template });
  const item = templates.find(t => t.id === template) || templates[0];
  return { ...item, name: item.id, recipient_doctype: "Beispieldatensatz", revision: "demo-v1", max_recipients: 10,
    fields: item.id === "demo-ablesetermin" ? [
      { name: "datum", label: "Datum", type: "Datum", required: false, default: new Date().toISOString().slice(0,10) },
      { name: "termin", label: "Ablesetermin", type: "Datum", required: true, default: null, description: "An diesem Tag findet die Ablesung statt." },
      { name: "zeitfenster", label: "Zeitfenster", type: "Text", required: true, default: "09:00 bis 12:00 Uhr" },
      { name: "hinweis_anzeigen", label: "Hinweis anzeigen", type: "Bool", required: false, default: false },
      { name: "hinweistext", label: "Hinweistext", type: "Text", required: false, default: "" },
      { name: "ansprechpartner", label: "Ansprechpartner", type: "Text", required: false, default: "Organisation" },
    ] : [{ name: "nachricht", label: "Nachricht", type: "Text", required: true, default: null }],
  };
}
export async function findRecipients(template, query, offset = 0) {
  if (embedded) return rpc("composer_recipients", { template, query, offset });
  return { items: recipients.filter(r => `${r.id} ${r.label}`.toLowerCase().includes(query.toLowerCase())), has_more: false };
}
export async function previewLetters(payload) {
  if (embedded) return rpc("composer_preview", { payload: JSON.stringify(payload) });
  const template = await describeTemplate(payload.template);
  const checks = payload.recipients.map(id => {
    const custom = payload.individual[id] || {};
    const errors = missingFields(template.fields, payload.values, custom.values);
    const changes = template.fields.map(f => ({ label: f.label, value: effectiveValue(f, payload.values, custom.values), origin: Object.hasOwn(custom.values || {}, f.name) ? "individual" : Object.hasOwn(payload.values, f.name) ? "common" : "template" }));
    const fieldValue = name => effectiveValue(template.fields.find(f => f.name === name), payload.values, custom.values);
    const extra = template.name === "demo-ablesetermin" && fieldValue("hinweis_anzeigen") && fieldValue("hinweistext") ? `<p>${escape(fieldValue("hinweistext")).replace(/\n/g, "<br>")}</p>` : "";
    const closing = "<p>Mit freundlichen Grüßen<br>Ihre Organisation</p>";
    const body = template.name === "demo-ablesetermin" ? `<p>wir kündigen die Ablesung für den <strong>${escape(fieldValue("termin"))}</strong> im Zeitfenster ${escape(fieldValue("zeitfenster"))} an.</p><p>Bitte ermöglichen Sie den Zugang zu den Zählern. Bei Fragen wenden Sie sich an ${escape(fieldValue("ansprechpartner") || "uns")}.</p>` : `<p>${escape(changes[0].value)}</p>`;
    return { recipient: id, status: Object.keys(errors).length ? "missing" : "ready", fields: errors, changes,
      html: `<p class="sender">ORGANISATION · Gartenstraße 12</p><p>${escape(recipients.find(r => r.id === id)?.label)}</p><p>${escape(template.fields.some(f => f.name === "datum") ? fieldValue("datum") : "")}</p><h2>${escape(template.title)}</h2><p>Guten Tag,</p>${body}${extra}${closing}` };
  });
  return { ready: checks.every(c => c.status === "ready"), checks, token: "demo-preview", expires_in_seconds: 1800 };
}
export async function saveLetters(token) {
  if (embedded) return rpc("composer_save", { token });
  return { docname: "DEMO-ENTWURF", demo: true };
}
