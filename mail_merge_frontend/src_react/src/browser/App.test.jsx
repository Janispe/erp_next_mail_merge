import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "./App.jsx";
import { deleteTemplate, loadBrowserData } from "./api.js";

vi.mock("./api.js", () => ({
  loadBrowserData: vi.fn(), deleteTemplate: vi.fn(),
  setFavorite: vi.fn(), moveTemplates: vi.fn(), copyTemplate: vi.fn(),
  createTemplate: vi.fn(), createFolder: vi.fn(), openDurchlauf: vi.fn(),
  openEditor: vi.fn(), loadRecipients: vi.fn(), renderPreview: vi.fn(), embedded: true,
}));

let container, root, records;
const click = async element => act(async () => element.click());
const deleteButton = () => [...container.querySelectorAll(".bw-bulk-actions button")]
  .find(button => /Lösch/.test(button.textContent));
const rows = () => [...container.querySelectorAll(".tpl-row")];

beforeEach(async () => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  vi.clearAllMocks();
  vi.spyOn(window, "confirm").mockReturnValue(true);
  vi.spyOn(window, "alert").mockImplementation(() => {});
  records = ["Vorlage A", "Vorlage B"].map(id => ({
    id, title: id, folder: "ordner", modified: "2026-09-09", modified_by: "Administrator",
    description: "", bausteine: [], variables: [],
  }));
  loadBrowserData.mockImplementation(async () => ({
    folders: [{ id: "ordner", title: "Ordner", count: records.length }], templates: [...records],
  }));
  deleteTemplate.mockImplementation(async id => {
    records = records.filter(record => record.id !== id);
    return { name: id };
  });
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
  await act(async () => root.render(<App />));
});

afterEach(async () => {
  await act(async () => root.unmount());
  container.remove();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("Löschen aus der Auswahlleiste", () => {
  it("löscht eine ausgewählte Vorlage erst nach Bestätigung", async () => {
    await click(rows()[0].querySelector('input[type="checkbox"]'));
    await click(deleteButton());
    expect(window.confirm).toHaveBeenCalledWith('Vorlage „Vorlage A" wirklich löschen?');
    expect(deleteTemplate).toHaveBeenCalledTimes(1);
    expect(deleteTemplate).toHaveBeenCalledWith("Vorlage A");
    expect(rows()).toHaveLength(1);
    expect(rows()[0].textContent).toContain("Vorlage B");
    expect(container.querySelector(".bw-bulk-bar")).toBeNull();
  });

  it("behält die Auswahl bei, wenn die Bestätigung abgebrochen wird", async () => {
    window.confirm.mockReturnValue(false);
    await click(rows()[0].querySelector('input[type="checkbox"]'));
    await click(deleteButton());
    expect(deleteTemplate).not.toHaveBeenCalled();
    expect(rows()).toHaveLength(2);
    expect(rows()[0].querySelector("input").checked).toBe(true);
  });

  it("zeigt einen Teilfehler und lässt nur die nicht gelöschte Vorlage ausgewählt", async () => {
    deleteTemplate.mockImplementation(async id => {
      if (id === "Vorlage B") throw new Error("Die Vorlage wird noch verwendet.");
      records = records.filter(record => record.id !== id);
      return { name: id };
    });
    for (const row of rows()) await click(row.querySelector("input"));
    await click(deleteButton());
    expect(deleteTemplate).toHaveBeenCalledTimes(2);
    expect(window.alert).toHaveBeenCalledWith(expect.stringContaining('„Vorlage B": Die Vorlage wird noch verwendet.'));
    expect(rows()).toHaveLength(1);
    expect(rows()[0].textContent).toContain("Vorlage B");
    expect(rows()[0].querySelector("input").checked).toBe(true);
  });

  it("sperrt den Knopf während der Anfrage gegen doppelte Löschaufrufe", async () => {
    let resolveDelete;
    deleteTemplate.mockImplementation(() => new Promise(resolve => { resolveDelete = resolve; }));
    await click(rows()[0].querySelector("input"));
    await click(deleteButton());
    expect(deleteButton().disabled).toBe(true);
    await click(deleteButton());
    expect(deleteTemplate).toHaveBeenCalledTimes(1);
    await act(async () => resolveDelete({ name: "Vorlage A" }));
  });
});
