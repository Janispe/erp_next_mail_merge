import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import { VariableEditor, VariableValues } from "./VariableEditor.jsx";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
let host, root;
afterEach(async () => { await act(async () => root.unmount()); host.remove(); });
const mount = async element => {
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
  await act(async () => root.render(element));
};
const change = async (el, value) => {
  const proto = el.tagName === "SELECT" ? HTMLSelectElement.prototype : HTMLInputElement.prototype;
  await act(async () => {
    Object.getOwnPropertyDescriptor(proto, "value").set.call(el, value);
    el.dispatchEvent(new Event(el.tagName === "SELECT" ? "change" : "input", { bubbles: true }));
  });
};
const rent = {name:"objekt.bruttomiete",label:"Bruttomiete",type:"Zahl",path:"objekt.bruttomiete"};
it("wechselt vom Vorlagenpfad zu einem anderen Pfad, Festwert und zurück", async () => {
  const onChange = vi.fn();
  const render = value => <VariableEditor variables={[{...rent,value}]} onChange={onChange}/>;
  await mount(render(undefined));
  await change(host.querySelector('[aria-label="Quelle für Bruttomiete"]'), "path");
  expect(onChange).toHaveBeenLastCalledWith(rent.name, {path:rent.path});
  await act(async () => root.render(render({path:rent.path})));
  await change(host.querySelector('[aria-label="Feldpfad für Bruttomiete"]'), "objekt.aktuelle_nettokaltmiete");
  expect(onChange).toHaveBeenLastCalledWith(rent.name, {path:"objekt.aktuelle_nettokaltmiete"});
  await change(host.querySelector('[aria-label="Quelle für Bruttomiete"]'), "value");
  expect(onChange).toHaveBeenLastCalledWith(rent.name, "");
  await act(async () => root.render(render("")));
  await change(host.querySelector('[aria-label="Bruttomiete"]'), "750");
  expect(onChange).toHaveBeenLastCalledWith(rent.name, "750");
  await change(host.querySelector('[aria-label="Quelle für Bruttomiete"]'), "default");
  expect(onChange).toHaveBeenLastCalledWith(rent.name, undefined);
});
it("zeigt und entfernt einen individuellen Pfad, ohne die gemeinsame Vorgabe zu ändern", async () => {
  const onReset = vi.fn();
  await mount(<VariableEditor variables={[{...rent,value:900}]} individual overrides={{[rent.name]:{path:"objekt.alternative"}}} onChange={vi.fn()} onReset={onReset}/>);
  expect(host.querySelector('[aria-label="Feldpfad für Bruttomiete"]').value).toBe("objekt.alternative");
  expect(host.textContent).toContain("Für alle: 900");
  await change(host.querySelector('[aria-label="Quelle für Bruttomiete"]'), "default");
  expect(onReset).toHaveBeenCalledWith(rent.name);
  await act(async () => root.render(<VariableValues variables={[rent]} overrides={{[rent.name]:{path:"objekt.alternative"}}}/>));
  expect(host.textContent).toContain("Aus Pfad: objekt.alternative");
  expect(host.textContent).not.toContain("[object Object]");
});
