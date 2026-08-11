import { describe, expect, it } from "vitest";
import { buildVersionGraph } from "./VersionHistoryGraph.jsx";

const versions = [
  { name: "version-4", number: 4, restored_from: "version-1" },
  { name: "version-3", number: 3, restored_from: "" },
  { name: "version-2", number: 2, restored_from: "" },
  { name: "version-1", number: 1, restored_from: "" },
];

describe("buildVersionGraph", () => {
  it("connects a restored version to its historical origin", () => {
    const graph = buildVersionGraph(versions);

    expect(graph.restoreEdges).toHaveLength(1);
    expect(graph.restoreEdges[0]).toMatchObject({ source: "version-1", target: "version-4" });
    expect(graph.restoreEdges[0].sourceY).toBeGreaterThan(graph.restoreEdges[0].targetY);
    expect(graph.nodes[0].restoredFromNumber).toBe(1);
  });

  it("keeps origin metadata when a search hides the source node", () => {
    const graph = buildVersionGraph([versions[0]], versions);

    expect(graph.restoreEdges).toHaveLength(0);
    expect(graph.nodes[0].restoredFromNumber).toBe(1);
  });
});
