import { describe, expect, it } from "vitest";
import {
  applyAssignmentEntry,
  assignmentEntry,
  recordVariableRoots,
  switchVariableSource,
  variableSource,
  withRecord,
  withoutRecord,
} from "./recordVariables.js";

const anwalt = { variable: "anwalt", type: "Doctype", reference_doctype: "Contact", value: "", path: "" };

describe("Doctype-Variablen mit festem Datensatz", () => {
  it("leitet die Quelle aus Wert bzw. Umschalter ab", () => {
    expect(variableSource(anwalt)).toBe("path");
    expect(variableSource({ ...anwalt, value: "K1" })).toBe("record");
    expect(variableSource({ ...anwalt, source: "record" })).toBe("record");
  });

  it("hält nie Pfad und Datensatz gleichzeitig", () => {
    const withPath = { ...anwalt, path: "objekt.kunde" };
    expect(switchVariableSource(withPath, "record")).toMatchObject({ source: "record", path: "" });
    expect(switchVariableSource({ ...anwalt, value: "K1" }, "path")).toMatchObject({ source: "path", value: "" });
  });

  it("setzt einen Namen bzw. sammelt Namen für Listen", () => {
    expect(withRecord(anwalt, "K1").value).toBe("K1");
    const liste = { ...anwalt, type: "Doctype Liste", value: [] };
    const zwei = withRecord(withRecord(liste, "K1"), "K2");
    expect(zwei.value).toEqual(["K1", "K2"]);
    expect(withRecord(zwei, "K1").value).toEqual(["K1", "K2"]);
    expect(withoutRecord(zwei, "K1").value).toEqual(["K2"]);
    expect(withoutRecord({ ...anwalt, value: "K1" }, "K1").value).toBe("");
  });

  it("speichert Belegungen als value (Datensatz) oder path und stellt sie wieder her", () => {
    expect(assignmentEntry({ ...anwalt, value: "K1" })).toEqual({ value: "K1" });
    expect(assignmentEntry({ ...anwalt, path: "objekt.kunde" })).toEqual({ path: "objekt.kunde" });
    expect(applyAssignmentEntry(anwalt, { value: "K2" })).toMatchObject({ source: "record", value: "K2", path: "" });
    expect(applyAssignmentEntry({ ...anwalt, value: "K1" }, { path: "objekt.kunde" })).toMatchObject({ source: "path", value: "", path: "objekt.kunde" });
  });

  it("bietet Doctype-Variablen als Anfang von Baustein-Pfaden an", () => {
    const roots = recordVariableRoots([
      anwalt,
      { variable: "anwalt_adresse", type: "Doctype", reference_doctype: "Address" },
      { variable: "betreff", type: "Text" },
      { variable: "ohne_doctype", type: "Doctype", reference_doctype: "" },
    ]);
    expect(roots.map((root) => [root.path, root.type])).toEqual([
      ["anwalt", "Contact"],
      ["anwalt_adresse", "Address"],
    ]);
  });
});
