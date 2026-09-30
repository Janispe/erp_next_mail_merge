import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import { VariableEditor, VariableValues } from "./VariableEditor.jsx";
import { searchRecords } from "./api.js";

vi.mock("./api.js", () => ({
  searchRecords: vi.fn(async () => ({ items: [{ id: "K-7", label: "Kanzlei Beispiel" }, { id: "K-8", label: "K-8" }] })),
}));
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
let host, root;
afterEach(async () => { await act(async () => root.unmount()); host.remove(); vi.clearAllMocks(); });

const mount = async (element) => {
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
  await act(async () => root.render(element));
};
const search = async (el, value) => {
  await act(async () => {
    el.dispatchEvent(new FocusEvent("focusin", { bubbles: true }));
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set.call(el, value);
    el.dispatchEvent(new Event("input", { bubbles: true }));
  });
  await act(async () => new Promise((resolve) => setTimeout(resolve, 250)));
};
const anwalt = { name: "anwalt", label: "Anwalt", type: "Doctype", reference_doctype: "Contact", path: "", value: "" };

it("wählt einen Datensatz über die Suche und kann ihn wieder entfernen", async () => {
  const onChange = vi.fn();
  await mount(<VariableEditor variables={[anwalt]} onChange={onChange} onReset={() => {}} />);
  await search(host.querySelector('[aria-label="Anwalt"]'), "Kanzlei");
  expect(searchRecords).toHaveBeenLastCalledWith("Contact", "Kanzlei");
  await act(async () => host.querySelector('[role="option"]').dispatchEvent(new MouseEvent("mousedown", { bubbles: true })));
  expect(onChange).toHaveBeenLastCalledWith("anwalt", "K-7");

  await act(async () => root.render(<VariableEditor variables={[{ ...anwalt, value: "K-7" }]} onChange={onChange} onReset={() => {}} />));
  expect(host.querySelector(".dl-record-chip").textContent).toContain("K-7");
  await act(async () => host.querySelector('[aria-label="K-7 entfernen"]').click());
  expect(onChange).toHaveBeenLastCalledWith("anwalt", "");
});

it("sammelt bei Doctype Liste mehrere Datensätze und zeigt sie als Liste an", async () => {
  const onChange = vi.fn();
  const liste = { ...anwalt, type: "Doctype Liste", value: ["K-7"] };
  await mount(<VariableEditor variables={[liste]} onChange={onChange} onReset={() => {}} />);
  await search(host.querySelector('[aria-label="Anwalt"]'), "");
  const options = [...host.querySelectorAll('[role="option"]')].map((el) => el.textContent);
  expect(options).toEqual(["K-8"]);
  await act(async () => host.querySelector('[role="option"]').dispatchEvent(new MouseEvent("mousedown", { bubbles: true })));
  expect(onChange).toHaveBeenLastCalledWith("anwalt", ["K-7", "K-8"]);

  await act(async () => root.render(<VariableValues variables={[{ ...liste, value: ["K-7", "K-8"] }]} />));
  expect(host.textContent).toContain("K-7, K-8");
});
