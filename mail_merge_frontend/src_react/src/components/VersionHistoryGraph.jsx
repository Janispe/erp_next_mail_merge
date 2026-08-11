import React from "react";
import { Icon } from "./Icon.jsx";

const ROW_HEIGHT = 96;
const NODE_Y_OFFSET = 42;

export function buildVersionGraph(items, allItems = items) {
  const visibleByName = new Map(items.map((item, index) => [item.name, index]));
  const allByName = new Map(allItems.map((item) => [item.name, item]));
  const nodes = items.map((item, index) => {
    const restoredFrom = item.restored_from ? allByName.get(item.restored_from) : null;
    return {
      item,
      y: NODE_Y_OFFSET + (index * ROW_HEIGHT),
      restoredFromNumber: restoredFrom?.number || null,
    };
  });
  const restoreEdges = nodes.flatMap((node) => {
    const sourceIndex = visibleByName.get(node.item.restored_from);
    if (sourceIndex === undefined) return [];
    return [{
      source: node.item.restored_from,
      target: node.item.name,
      sourceY: NODE_Y_OFFSET + (sourceIndex * ROW_HEIGHT),
      targetY: node.y,
    }];
  });
  return {
    nodes,
    restoreEdges,
    height: Math.max(84, items.length * ROW_HEIGHT),
  };
}

export const VersionHistoryGraph = ({
  items,
  allItems,
  selectedName,
  onSelect,
  formatDate,
  displayUser,
}) => {
  const graph = buildVersionGraph(items, allItems);
  const firstY = graph.nodes[0]?.y || NODE_Y_OFFSET;
  const lastY = graph.nodes.at(-1)?.y || firstY;

  return (
    <div className="version-graph" style={{ height: `${graph.height}px` }}>
      <svg
        className="version-graph-rails"
        width="58"
        height={graph.height}
        viewBox={`0 0 58 ${graph.height}`}
        aria-hidden="true"
      >
        <defs>
          <marker id="version-restore-arrow" viewBox="0 0 7 7" refX="6" refY="3.5" markerWidth="6" markerHeight="6" orient="auto">
            <path d="M0,0 L7,3.5 L0,7 Z" className="version-restore-arrow"/>
          </marker>
        </defs>
        {graph.nodes.length > 1 && (
          <path className="version-main-edge" d={`M34 ${firstY} L34 ${lastY}`}/>
        )}
        {graph.restoreEdges.map((edge) => (
          <path
            key={`${edge.source}-${edge.target}`}
            className="version-restore-edge"
            d={`M29 ${edge.sourceY} C7 ${edge.sourceY}, 7 ${edge.targetY}, 29 ${edge.targetY}`}
            markerEnd="url(#version-restore-arrow)"
          />
        ))}
      </svg>

      <div className="version-graph-rows">
        {graph.nodes.map(({ item, restoredFromNumber }) => (
          <button
            type="button"
            key={item.name}
            className={`version-graph-node ${selectedName === item.name ? "active" : ""}`}
            onClick={() => onSelect(item.name)}
            aria-label={`Version ${item.number}${item.is_current ? ", aktueller Stand" : ""}`}
          >
            <span className={`version-graph-dot ${item.is_current ? "current" : ""}`} />
            <span className="version-graph-card">
              <span className="version-graph-card-head">
                <span className="version-number">V{item.number}</span>
                <span className="version-graph-title">{item.label || item.source}</span>
                {item.protected && <Icon name="star" size={11} title="Geschützte Version"/>}
                {item.is_current && <span className="version-graph-current">Aktuell</span>}
              </span>
              {restoredFromNumber && (
                <span className="version-graph-origin"><Icon name="branch" size={11}/> Wiederhergestellt aus V{restoredFromNumber}</span>
              )}
              {!restoredFromNumber && <span className="version-list-summary">{item.change_summary || "Gespeicherter Stand"}</span>}
              <span className="version-list-meta">{formatDate(item.created)} · {displayUser(item.created_by)}</span>
            </span>
          </button>
        ))}
      </div>
    </div>
  );
};
