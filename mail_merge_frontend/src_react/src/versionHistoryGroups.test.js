import { expect, it } from 'vitest';
import { visibleHistoryItems } from './versionHistoryGroups.js';
import { buildVersionGraph } from './components/VersionHistoryGraph.jsx';
const rows = [
 { name: 'V5', number: 5, based_on: 'V4', group_members: ['V4', 'V3'] },
 { name: 'V4', number: 4, based_on: 'V3', history_group: 'V5' },
 { name: 'V3', number: 3, based_on: 'V1', history_group: 'V5' },
 { name: 'V1', number: 1 },
];
it('collapses the presentation and connects the result to the original basis', () => {
 const visible = visibleHistoryItems(rows, {});
 expect(visible.map(v => v.name)).toEqual(['V5', 'V1']);
 expect(buildVersionGraph(visible, rows).restoreEdges[0]).toMatchObject({ source: 'V1', target: 'V5' });
 expect(rows[0].based_on).toBe('V4');
});
it('expands intermediate snapshots and searches hidden versions', () => {
 expect(visibleHistoryItems(rows, { expanded: { V5: true } })).toEqual(rows);
 expect(visibleHistoryItems(rows, { query: 'v3' })).toEqual([rows[2]]);
});
it('includes all rows during grouping selection', () => {
 expect(visibleHistoryItems(rows, { selecting: true })).toEqual(rows);
});
