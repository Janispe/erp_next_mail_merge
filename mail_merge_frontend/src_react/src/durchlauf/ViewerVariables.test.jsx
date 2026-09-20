import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import { App } from "./App.jsx";
import { saveVariables } from "./api.js";
vi.mock("./api.js", async original => {
  const actual = await original();
  const { DURCHLAUF, RECIPIENTS } = await import('./data.js');
  return { ...actual, saveVariables: vi.fn(async () => ({})), loadDurchlauf: vi.fn(async () => ({ durchlauf: { ...DURCHLAUF, can_write: true, variables: [
    {name:'termin',label:'Termin',type:'Datum',value:'2026-10-01'},
    {name:'text',label:'Hinweistext',type:'Text',value:'Gemeinsam'},
    {name:'zeigen',label:'Hinweis anzeigen',type:'Bool',value:true},
  ] }, recipients: RECIPIENTS.slice(0,2), overrides: {} })) };
});
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
let host,root;
afterEach(async () => { await act(async () => root.unmount()); host.remove(); vi.clearAllMocks(); });
const input = async (el,value) => { expect(el).toBeTruthy(); const proto=el.tagName==='SELECT'?HTMLSelectElement.prototype:el.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;
  await act(async () => { Object.getOwnPropertyDescriptor(proto,'value').set.call(el,value);el.dispatchEvent(new Event(el.tagName==='SELECT'?'change':'input',{bubbles:true})); }); };
it('speichert individuelle Datumswerte, leere Texte und Nein unabhängig von gemeinsamen Werten', async () => {
  host=document.createElement('div');document.body.append(host);root=createRoot(host);
  await act(async () => root.render(<App/>));
  const left=host.querySelector('.dl-config');
  await input(left.querySelector('.dl-variable-scope select'),'recipient');
  expect(left.textContent).toContain('Müller, Andreas');
  await input(left.querySelector('[aria-label="Termin"]'),'2026-11-12');
  await input(left.querySelector('[aria-label="Hinweistext"]'),'');
  await input(left.querySelector('[aria-label="Hinweis anzeigen"]'),'false');
  await act(async () => new Promise(resolve=>setTimeout(resolve,650)));
  const [common,individual]=saveVariables.mock.lastCall;
  expect(individual['MV-2024-0142']).toEqual({termin:'2026-11-12',text:'',zeigen:false});
  expect(common.find(v=>v.name==='zeigen').value).toBe(true);
  await act(async () => left.querySelectorAll('.dl-variable-reset button')[1].click());
  await act(async () => new Promise(resolve=>setTimeout(resolve,650)));
  expect(saveVariables.mock.lastCall[1]['MV-2024-0142']).not.toHaveProperty('text');
  expect(left.querySelector('[aria-label="Hinweistext"]').value).toBe('Gemeinsam');
  const splitter=host.querySelector('[role="separator"]');
  await act(async () => splitter.dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowRight',bubbles:true})));
  expect(splitter.getAttribute('aria-valuenow')).toBe('400');
  expect(host.querySelector('.dl-main').style.getPropertyValue('--dl-config-width')).toBe('400px');
});
