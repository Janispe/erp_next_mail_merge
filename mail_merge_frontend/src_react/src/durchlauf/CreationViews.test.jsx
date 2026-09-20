import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import { CreationViews } from "./App.jsx";

vi.mock("./api.js", () => ({
  embedded: false,
  listVorlagen: vi.fn(async () => ({ items: [{ id: "demo-ablesetermin", title: "Ablesetermin ankündigen" }] })),
}));
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
let host, root;
afterEach(async () => { await act(async () => root.unmount()); host.remove(); });
const click = async element => { expect(element).toBeTruthy(); await act(async () => element.click()); };
const mount = async props => {
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
  await act(async () => root.render(<CreationViews {...props}/>));
};

it("öffnet standardmäßig die bisherige Ansicht und bewahrt beide Eingabestände", async () => {
  await mount({ preselect: "demo-ablesetermin" });
  const switches = host.querySelectorAll('.dl-view-switch button');
  expect(switches[0].getAttribute('aria-pressed')).toBe('true');
  expect(host.querySelector('.letter-composer')).toBeNull();
  const title = host.querySelector('input[placeholder="z. B. Serienlauf Mai 2026"]');
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(title, 'Mein Entwurf');
    title.dispatchEvent(new Event('input', { bubbles: true }));
  });
  await click(switches[1]);
  expect(host.querySelector('.dl-new').parentElement.hidden).toBe(true);
  expect(host.querySelector('.letter-composer').parentElement.hidden).toBe(false);
  expect(host.querySelector('.lc-template.selected').textContent).toContain('Ablesetermin');
  await click([...host.querySelectorAll('.letter-composer button')].find(b => b.textContent.includes('Empfänger auswählen')));
  expect(host.querySelector('.lc-section-heading h2').textContent).toBe('An wen geht der Brief?');
  await click(switches[0]);
  expect(title.value).toBe('Mein Entwurf');
  expect(host.querySelector('.letter-composer').parentElement.hidden).toBe(true);
  await click(switches[1]);
  expect(host.querySelector('.lc-section-heading h2').textContent).toBe('An wen geht der Brief?');
});

it("bietet auch beim direkten Prototyp-Einstieg den Rückweg zur bisherigen Ansicht", async () => {
  await mount({ initialPrototype: true });
  const switches = host.querySelectorAll('.dl-view-switch button');
  expect(switches[1].getAttribute('aria-pressed')).toBe('true');
  expect(host.querySelector('.dl-new')).toBeNull();
  await click(switches[0]);
  expect(host.querySelector('.dl-new').parentElement.hidden).toBe(false);
});
