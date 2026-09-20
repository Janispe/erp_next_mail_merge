import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LetterComposer } from "./LetterComposer.jsx";
import { effectiveValue, missingFields } from "./composerApi.js";

vi.mock("./api.js", () => ({ embedded: false, gotoDurchlauf: vi.fn(), listVorlagen: vi.fn() }));
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
let host, root;
const click = async el => { expect(el).toBeTruthy(); await act(async () => el.click()); };
const button = text => [...host.querySelectorAll("button")].find(el => el.textContent.includes(text));
const input = async (el, value) => {
  expect(el).toBeTruthy();
  const proto = el.tagName === "TEXTAREA" ? HTMLTextAreaElement.prototype : el.tagName === "SELECT" ? HTMLSelectElement.prototype : HTMLInputElement.prototype;
  await act(async () => { Object.getOwnPropertyDescriptor(proto, "value").set.call(el, value); el.dispatchEvent(new Event(el.tagName === "SELECT" ? "change" : "input", { bubbles: true })); });
};
async function toFields() {
  await click(button("Ablesetermin ankündigen"));
  await click(button("Empfänger auswählen"));
  const boxes = host.querySelectorAll('.lc-recipient-options input');
  await click(boxes[0]); await click(boxes[1]);
  await click(button("Angaben ausfüllen"));
}
beforeEach(async () => { host = document.createElement("div"); document.body.append(host); root = createRoot(host); await act(async () => root.render(<LetterComposer/>)); });
afterEach(async () => { await act(async () => root.unmount()); host.remove(); });

describe("Brief erstellen", () => {
  it("steuert einen Vorlagenabsatz gemeinsam und schaltet ihn individuell aus", async () => {
    await toFields();
    expect(host.querySelector('.lc-addition-card')).toBeNull();
    await input(host.querySelector('[aria-label="Ablesetermin"]'), "2026-10-12");
    await input(host.querySelector('[aria-label="Hinweis anzeigen"]'), "true");
    await input(host.querySelector('[aria-label="Hinweistext"]'), "Bitte die Kellerräume öffnen.");
    await input(host.querySelector('.lc-scope select'), "DEMO-MV-002");
    const toggle = host.querySelector('[aria-label="Hinweis anzeigen"]');
    await click(toggle.closest('.lc-field').querySelector('input[type="checkbox"]'));
    await input(toggle, "false");
    await click(button("Vorschau prüfen"));
    expect(host.querySelectorAll('.lc-check .success')).toHaveLength(2);
    expect(host.querySelector('iframe').getAttribute('srcdoc')).toContain("Bitte die Kellerräume öffnen.");
    await click(host.querySelectorAll('.lc-check')[1]);
    expect(host.querySelector('iframe').getAttribute('srcdoc')).not.toContain("Bitte die Kellerräume öffnen.");
    expect(host.querySelector('.lc-changes').textContent).toContain("Nein");
    expect(host.querySelector('.lc-changes').textContent).toContain("Individuell eingesetzt");
    await click(button("Weiter zum Speichern"));
    await click(button("Als Entwurf speichern"));
    expect(host.textContent).toContain("Demo abgeschlossen");
  });
  it("zeigt fehlende Angaben je Empfänger und verhindert das Speichern", async () => {
    await toFields();
    await click(button("Vorschau prüfen"));
    expect(host.querySelectorAll('.lc-check .warning')).toHaveLength(2);
    expect(host.textContent).toContain("Ablesetermin fehlt.");
    expect(button("Weiter zum Speichern").disabled).toBe(true);
    await click(button("Angaben korrigieren"));
    expect(host.querySelector('.lc-scope select').value).toBe("DEMO-MV-001");
    expect(host.querySelector('[aria-label="Ablesetermin"]').disabled).toBe(true);
    await click(host.querySelector('[aria-label="Ablesetermin"]').closest('.lc-field').querySelector('.lc-inline-check input'));
    await input(host.querySelector('[aria-label="Ablesetermin"]'), "2026-10-15");
    await click(button("Vorschau prüfen"));
    expect(host.querySelectorAll('.lc-check .success')).toHaveLength(1);
    expect(host.querySelectorAll('.lc-check .warning')).toHaveLength(1);
    expect(button("Weiter zum Speichern").disabled).toBe(true);
  });
  it("kennzeichnet eine alte Vorschau nach einer Eingabeänderung", async () => {
    await toFields();
    await input(host.querySelector('[aria-label="Ablesetermin"]'), "2026-10-12");
    await click(button("Vorschau prüfen"));
    await click(button("Angaben"));
    await input(host.querySelector('[aria-label="Ablesetermin"]'), "2026-10-20");
    expect(host.querySelector('.lc-warning').textContent).toContain("enthält diese Änderung noch nicht");
    await click(button("Vorschau prüfen"));
    expect(host.querySelector('.lc-warning')).toBeNull();
    expect(host.querySelector('iframe').getAttribute('srcdoc')).toContain("2026-10-20");
  });
  it("behält false und null als ausdrückliche individuelle Angaben bei", () => {
    const f = { name: "x", label: "Zustimmung", required: true, default: true };
    expect(effectiveValue(f, { x: true }, { x: false })).toBe(false);
    expect(missingFields([f], { x: true }, { x: false })).toEqual({});
    expect(missingFields([f], { x: true }, { x: "" })).toEqual({ x: "Zustimmung fehlt." });
  });
});
