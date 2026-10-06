export function visibleHistoryItems(items, { query = '', expanded = {}, selecting = false } = {}) {
  const q = query.trim().toLowerCase();
  if (q) return items.filter(item => [`v${item.number}`, item.label, item.source, item.change_summary, item.created_by].some(value => String(value || '').toLowerCase().includes(q)));
  if (selecting) return items;
  const byName = new Map(items.map(item => [item.name, item]));
  return items.filter(item => !item.history_group || expanded[item.history_group]).map(item => {
    if (!item.group_members?.length || expanded[item.name]) return item;
    const members = new Set(item.group_members);
    let origin = item.based_on;
    const seen = new Set();
    while (members.has(origin) && !seen.has(origin)) {
      seen.add(origin);
      origin = byName.get(origin)?.based_on;
    }
    return { ...item, display_based_on: origin };
  });
}
