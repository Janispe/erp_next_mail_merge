import React, { useEffect, useState } from 'react';
import { loadTemplateVersionUsage } from '../api.js';

export function VersionUsagePanel({ template, version, grouped = false }) {
  const [scope, setScope] = useState('version');
  const [kind, setKind] = useState('documents');
  const [offset, setOffset] = useState(0);
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => { setOffset(0); }, [scope, kind, version]);
  useEffect(() => {
    let alive = true;
    setLoading(true); setError(''); setReport(null);
    loadTemplateVersionUsage({ template, version: scope === 'version' ? version : '', kind, offset })
      .then(result => { if (alive) setReport(result); })
      .catch(e => { if (alive) setError(e.message || String(e)); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [template, version, scope, kind, offset]);
  return <div className="version-usage">
    <div className="version-usage-controls">
      <label>Verknüpfungen für <select value={scope} onChange={e => setScope(e.target.value)}><option value="version">{grouped ? 'Diese Zusammenfassung' : 'Diese Version'}</option><option value="template">Gesamte Vorlage</option></select></label>
      <div role="group" aria-label="Verknüpfte Datensätze">
        <button className={`btn sm ${kind === 'documents' ? 'primary' : ''}`} onClick={() => setKind('documents')}>Briefe{report && ` (${report.counts?.documents ?? 0})`}</button>
        <button className={`btn sm ${kind === 'runs' ? 'primary' : ''}`} onClick={() => setKind('runs')}>Durchläufe{report && ` (${report.counts?.runs ?? 0})`}</button>
      </div>
    </div>
    {grouped && scope === 'version' && <p>Enthält auch Briefe und Durchläufe der zusammengefassten Zwischenstände.</p>}
    {scope === 'template' && <p>Ältere Briefe ohne festgelegte Vorlagenversion sind ebenfalls enthalten.</p>}
    {loading && <div className="version-loading"><span className="spinner"/> Verknüpfungen werden geladen …</div>}
    {error && <div className="version-error">{error}</div>}
    {!loading && report && <>
      {report.items.length ? <div className="version-usage-table"><table>
        <thead><tr><th>{kind === 'documents' ? 'Brief' : 'Durchlauf'}</th><th>Version</th><th>Datum</th><th>Status</th>{kind === 'documents' && <><th>Zielobjekt</th><th>PDF</th></>}</tr></thead>
        <tbody>{report.items.map(item => <tr key={item.name}>
          <td><a href={item.url} target="_blank" rel="noreferrer">{item.title || item.name}</a><small>{item.name}</small>{item.durchlauf && <a className="version-usage-run" href={`/desk/serienbrief-durchlauf/${encodeURIComponent(item.durchlauf)}`} target="_blank" rel="noreferrer">Durchlauf {item.durchlauf}</a>}</td>
          <td>{item.version_number ? `V${item.version_number}` : 'Nicht festgelegt'}</td>
          <td>{item.date || '—'}</td><td>{item.docstatus === 2 ? 'Storniert' : item.status || '—'}</td>
          {kind === 'documents' && <><td>{item.objekt || '—'}</td><td>{item.pdf_url ? <a href={item.pdf_url} target="_blank" rel="noreferrer">PDF öffnen</a> : '—'}</td></>}
        </tr>)}</tbody>
      </table></div> : <div className="version-empty">Keine sichtbaren {kind === 'documents' ? 'Briefe' : 'Durchläufe'} für diesen Stand.</div>}
      <div className="version-usage-pagination"><span>{report.total} {kind === 'documents' ? 'Briefe' : 'Durchläufe'}</span><button className="btn sm" disabled={!offset} onClick={() => setOffset(value => Math.max(0, value - 20))}>Zurück</button><button className="btn sm" disabled={!report.has_more} onClick={() => setOffset(value => value + 20)}>Weiter</button></div>
    </>}
  </div>;
}
