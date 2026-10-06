import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Icon } from "./Icon.jsx";
import {
  compareTemplateVersion,
  groupTemplateVersions,
  ungroupTemplateVersions,
  deleteTemplateVersion,
  loadTemplateVersions,
  renderTemplateVersionPreview,
  updateTemplateVersion,
} from "../api.js";
import { PreviewFeedback, PreviewValueInput } from "./PreviewFeedback.jsx";
import { VersionUsagePanel } from "./VersionUsagePanel.jsx";
import { visibleHistoryItems } from "../versionHistoryGroups.js";
import { VersionHistoryGraph } from "./VersionHistoryGraph.jsx";
import { createVersionPreviewCache, versionPreviewContextKey } from "../versionPreviewCache.js";

function usePdfUrl(base64) {
  const [url, setUrl] = useState("");
  useEffect(() => {
    if (!base64) { setUrl(""); return undefined; }
    try {
      const bin = atob(base64);
      const bytes = new Uint8Array(bin.length);
      for (let i = 0; i < bin.length; i += 1) bytes[i] = bin.charCodeAt(i);
      const next = URL.createObjectURL(new Blob([bytes], { type: "application/pdf" }));
      setUrl(next);
      return () => URL.revokeObjectURL(next);
    } catch (_) {
      setUrl("");
      return undefined;
    }
  }, [base64]);
  return url;
}

function formatDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("de-DE", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function displayUser(value) {
  const text = String(value || "");
  return text === "Administrator" ? text : (text.split("@")[0] || text);
}

export const VersionHistoryModal = ({
  open,
  template,
  recipient,
  druckSchwarzWeiss,
  refreshKey,
  hasUnsavedChanges,
  onClose,
  onRestore,
}) => {
  const [items, setItems] = useState([]);
  const [itemsTemplateId, setItemsTemplateId] = useState("");
  const [selectedName, setSelectedName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [view, setView] = useState("preview");
  const [preview, setPreview] = useState(null);
  const [placeholderMode, setPlaceholderMode] = useState(false);
  const [draftValues, setDraftValues] = useState({});
  const [appliedValues, setAppliedValues] = useState({});
  const [previewLoading, setPreviewLoading] = useState(false);
  const [comparison, setComparison] = useState(null);
  const [compareLoading, setCompareLoading] = useState(false);
  const [label, setLabel] = useState("");
  const [savingMeta, setSavingMeta] = useState(false);
  const [restoring, setRestoring] = useState(false);
  const [deletingVersion, setDeletingVersion] = useState(false);
  const [query, setQuery] = useState("");
  const [canManageHistory, setCanManageHistory] = useState(false);
  const [groupSelection, setGroupSelection] = useState(null);
  const [groupBusy, setGroupBusy] = useState(false);
  const [expandedGroups, setExpandedGroups] = useState({});
  const [navigationMode, setNavigationMode] = useState("graph");
  const [previewCacheRevision, setPreviewCacheRevision] = useState(0);
  const [prefetching, setPrefetching] = useState(false);
  const previewCacheRef = useRef(null);
  if (!previewCacheRef.current) previewCacheRef.current = createVersionPreviewCache(renderTemplateVersionPreview);
  const pdfUrl = usePdfUrl(preview?.ready === false ? "" : preview?.pdf_base64);

  const previewContext = useMemo(() => versionPreviewContextKey({
    templateId: template?.id,
    iterationDoctype: template?.haupt_verteil_objekt,
    recipientId: recipient?.id,
    druckSchwarzWeiss,
  }), [template?.id, template?.haupt_verteil_objekt, recipient?.id, druckSchwarzWeiss]);

  const previewParams = useCallback((version) => ({
    template: template.id,
    version,
    iterationDoctype: template.haupt_verteil_objekt,
    recipientId: recipient?.id,
    druckSchwarzWeiss,
    previewValues: appliedValues[version] || {},
    placeholderMode,
  }), [template.id, template.haupt_verteil_objekt, recipient?.id, druckSchwarzWeiss, appliedValues, placeholderMode]);

  const previewKey = useCallback((version) => `${previewContext}|${placeholderMode ? "names" : "values"}|${version}|${JSON.stringify(appliedValues[version] || {})}`, [previewContext, appliedValues, placeholderMode]);

  const loadVersionPdf = useCallback(async (version) => {
    const cache = previewCacheRef.current;
    const key = previewKey(version);
    const wasCached = cache.has(key);
    const nextPdf = await cache.load(key, previewParams(version));
    if (!wasCached && cache.has(key)) setPreviewCacheRevision((value) => value + 1);
    return nextPdf;
  }, [previewKey, previewParams]);

  const selected = items.find((item) => item.name === selectedName) || null;
  const filteredItems = useMemo(() => visibleHistoryItems(items, { query, expanded: expandedGroups, selecting: !!groupSelection }), [items, query, expandedGroups, groupSelection]);
  const toggleGroup = (name) => {
    if (expandedGroups[name] && selected?.history_group === name) setSelectedName(name);
    setExpandedGroups(current => ({ ...current, [name]: !current[name] }));
  };
  const previewCounts = useMemo(() => items.reduce((counts, item) => {
    const report = previewCacheRef.current.get(previewKey(item.name));
    if (report?.pdf_base64 && report.ready !== false && report.placeholder_mode) counts.layout += 1;
    else if (report?.pdf_base64 && report.ready !== false) counts.ready += 1;
    else if (report?.errors?.some((e) => ["provide_inputs", "correct_inputs"].includes(e.action))) counts.inputs += 1;
    else if (report?.ready === false) counts.failed += 1;
    return counts;
  }, { ready: 0, inputs: 0, failed: 0, layout: 0 }), [items, previewKey, previewCacheRevision]);

  const reload = async (keepSelection = true) => {
    if (!template?.id) return;
    const requestedTemplateId = template.id;
    setLoading(true);
    setError("");
    try {
      const result = await loadTemplateVersions(template.id);
      const next = result.items || [];
      setItems(next);
      setCanManageHistory(!!result.can_manage_history);
      setItemsTemplateId(requestedTemplateId);
      setSelectedName((current) => (
        keepSelection && next.some((item) => item.name === current)
          ? current
          : (next[0]?.name || "")
      ));
    } catch (e) {
      setError((e && e.message) || String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!open) return;
    setView("preview");
    setQuery("");
    setNavigationMode("graph");
    setItems([]);
    setGroupSelection(null);
    setExpandedGroups({});
    setPlaceholderMode(false);
    setDraftValues({});
    setAppliedValues({});
    setPreview(null);
    previewCacheRef.current.clear();
    setSelectedName("");
    setItemsTemplateId("");
    reload(false);
  }, [open, template?.id, refreshKey]);

  useEffect(() => {
    previewCacheRef.current.clear();
    setPreviewCacheRevision((value) => value + 1);
    setPreview(null);
  }, [previewContext]);

  useEffect(() => {
    setLabel(selected?.label || "");
  }, [selectedName, selected?.label]);

  useEffect(() => {
    if (!open || !selected || view !== "preview" || itemsTemplateId !== template.id) return;
    const cache = previewCacheRef.current;
    const key = previewKey(selected.name);
    if (cache.has(key)) {
      setPreview(cache.get(key));
      setPreviewLoading(false);
      return undefined;
    }
    let alive = true;
    setPreviewLoading(true);
    setPreview(null);
    setError("");
    loadVersionPdf(selected.name)
      .then((result) => { if (alive) setPreview(result); })
      .catch((e) => { if (alive) setError((e && e.message) || String(e)); })
      .finally(() => { if (alive) setPreviewLoading(false); });
    return () => { alive = false; };
  }, [open, selectedName, view, previewKey, loadVersionPdf, itemsTemplateId, template.id]);

  useEffect(() => {
    if (!open || !items.length || itemsTemplateId !== template.id) {
      setPrefetching(false);
      return undefined;
    }
    let cancelled = false;
    let timer = null;
    const queue = items.filter((item) => item.name !== selectedName);
    setPrefetching(queue.some((item) => !previewCacheRef.current.has(previewKey(item.name))));

    timer = window.setTimeout(async () => {
      for (const item of queue) {
        if (cancelled) break;
        if (previewCacheRef.current.has(previewKey(item.name))) continue;
        try {
          await loadVersionPdf(item.name);
        } catch (_) {
          // Hintergrundfehler blockieren weder Modal noch die ausgewählte Vorschau.
        }
      }
      if (!cancelled) setPrefetching(false);
    }, 300);

    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    };
  }, [open, items, selectedName, previewKey, loadVersionPdf, itemsTemplateId, template.id]);

  useEffect(() => {
    if (!open || !selected || view !== "compare" || itemsTemplateId !== template.id) return;
    let alive = true;
    setCompareLoading(true);
    setComparison(null);
    compareTemplateVersion(template.id, selected.name)
      .then((result) => { if (alive) setComparison(result); })
      .catch((e) => { if (alive) setError((e && e.message) || String(e)); })
      .finally(() => { if (alive) setCompareLoading(false); });
    return () => { alive = false; };
  }, [open, selectedName, view, template?.id, itemsTemplateId]);

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (event) => { if (event.key === "Escape" && !restoring && !deletingVersion) onClose?.(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, restoring, deletingVersion, onClose]);

  if (!open) return null;

  const changeGroup = async (ungroup = false) => {
    if (groupBusy) return;
    setGroupBusy(true); setError("");
    try {
      const result = ungroup
        ? await ungroupTemplateVersions(template.id, selected.name)
        : await groupTemplateVersions(template.id, groupSelection);
      setGroupSelection(null);
      await reload(false);
      setSelectedName(result.head);
    } catch (e) { setError(e.message || String(e)); }
    finally { setGroupBusy(false); }
  };

  const saveMetadata = async (patch) => {
    if (!selected || savingMeta) return;
    setSavingMeta(true);
    setError("");
    try {
      const result = await updateTemplateVersion(template.id, selected.name, {
        label: patch.label ?? label,
        protected: patch.protected ?? selected.protected,
      });
      setItems((current) => current.map((item) => item.name === result.name ? { ...item, ...result } : item));
      setLabel(result.label || "");
    } catch (e) {
      setError((e && e.message) || String(e));
    } finally {
      setSavingMeta(false);
    }
  };

  const restore = async () => {
    if (!selected || restoring) return;
    const ok = window.confirm(
      `Version ${selected.number}${selected.label ? ` „${selected.label}“` : ""} als Entwurf laden?\n\n` +
      (hasUnsavedChanges ? "Die derzeit ungespeicherten Änderungen im Editor werden dadurch ersetzt.\n\n" : "") +
      "Die Historie bleibt zunächst unverändert. Erst mit „Speichern“ wird daraus eine neue Version."
    );
    if (!ok) return;
    setRestoring(true);
    setError("");
    try {
      const result = await onRestore?.(selected.name);
      if (result !== false) onClose?.();
    } catch (e) {
      setError((e && e.message) || String(e));
    } finally {
      setRestoring(false);
    }
  };

  const removeSelected = async () => {
    if (!selected?.can_delete || deletingVersion) return;
    const ok = window.confirm(
      `Version ${selected.number}${selected.label ? ` „${selected.label}“` : ""} endgültig löschen?\n\n` +
      "Die Versionsnummer wird nicht neu vergeben. Dieser Vorgang kann nicht rückgängig gemacht werden."
    );
    if (!ok) return;
    setDeletingVersion(true);
    setError("");
    try {
      await deleteTemplateVersion(template.id, selected.name);
      setSelectedName("");
      await reload(false);
    } catch (e) {
      setError((e && e.message) || String(e));
    } finally {
      setDeletingVersion(false);
    }
  };

  return (
    <div className="version-modal-backdrop" onMouseDown={(e) => { if (e.target === e.currentTarget && !restoring && !deletingVersion) onClose?.(); }}>
      <section className="version-modal" role="dialog" aria-modal="true" aria-label="Versionshistorie">
        <header className="version-modal-head">
          <div className="version-modal-title">
            <span className="version-modal-icon"><Icon name="clock" size={18}/></span>
            <div>
              <strong>Versionshistorie</strong>
              <span>{template.title || template.id}</span>
            </div>
          </div>
          <div className="version-modal-head-actions">
            {!!items.length && (
              <span className={`version-cache-status ${previewCounts.inputs || previewCounts.failed || previewCounts.layout ? "attention" : ""} ${prefetching || previewLoading ? "loading" : ""}`} title="PDF-Vorschauen werden für diese Editor-Sitzung zwischengespeichert">
                {(prefetching || previewLoading) && <span className="spinner"/>} PDFs {previewCounts.ready}/{items.length} bereit
                {previewCounts.inputs > 0 && ` · ${previewCounts.inputs} mit offenen Eingaben`}
                {previewCounts.layout > 0 && ` · ${previewCounts.layout} mit Platzhaltern`}
                {previewCounts.failed > 0 && ` · ${previewCounts.failed} mit Fehler`}
              </span>
            )}
            <span>{items.length} {items.length === 1 ? "Version" : "Versionen"}{items.some(item => item.group_members?.length) && ` · ${items.filter(item => item.group_members?.length).length} zusammengefasst`}</span>
            <button className="btn ghost icon" onClick={onClose} disabled={restoring || deletingVersion} aria-label="Schließen"><Icon name="x" size={16}/></button>
          </div>
        </header>

        <div className="version-modal-layout">
          <aside className="version-list-pane">
            <div className="version-search">
              <Icon name="search" size={13}/>
              <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Versionen durchsuchen…"/>
            </div>
            <div className="version-navigation-switch" role="group" aria-label="Darstellung der Versionshistorie">
              <button type="button" className={navigationMode === "graph" ? "active" : ""} onClick={() => setNavigationMode("graph")}>
                <Icon name="branch" size={12}/> Verlauf
              </button>
              <button type="button" className={navigationMode === "list" ? "active" : ""} onClick={() => setNavigationMode("list")}>
                <Icon name="list" size={12}/> Liste
              </button>
            </div>
            {canManageHistory && <div className="version-group-tools">
              {!groupSelection ? <button className="btn sm" disabled={items.filter(item => item.can_group).length < 2} onClick={() => { setGroupSelection(selected?.can_group ? [selected.name] : []); setNavigationMode("list"); setQuery(""); }}>Vorschläge zusammenfassen</button> : <>
                <p>Eine zusammenhängende Vorschlagskette auswählen. Der neueste Stand bleibt als Ergebnis sichtbar.</p>
                <button className="btn sm primary" disabled={groupBusy || groupSelection.length < 2} onClick={() => changeGroup()}>Auswahl zusammenfassen ({groupSelection.length})</button>
                <button className="btn sm ghost" disabled={groupBusy} onClick={() => setGroupSelection(null)}>Abbrechen</button>
              </>}
            </div>}
            <div className="version-list">
              {loading && <div className="version-empty"><span className="spinner"/> Historie wird geladen …</div>}
              {!loading && !groupSelection && navigationMode === "graph" && filteredItems.length > 0 && (
                <VersionHistoryGraph
                  items={filteredItems}
                  allItems={items}
                  selectedName={selectedName}
                  onSelect={setSelectedName}
                  formatDate={formatDate}
                  displayUser={displayUser}
                  expandedGroups={expandedGroups}
                  onToggleGroup={toggleGroup}
                />
              )}
              {!loading && (groupSelection || navigationMode === "list") && filteredItems.map((item) => (
                <div key={item.name} className="version-select-row">
                  {groupSelection && <input type="checkbox" aria-label={`Version ${item.number} auswählen`} disabled={!item.can_group || groupBusy} checked={groupSelection.includes(item.name)} onChange={(event) => setGroupSelection(current => event.target.checked ? [...current, item.name] : current.filter(name => name !== item.name))}/>}
                <button
                  type="button"
                  key={item.name}
                  className={`version-list-item ${selectedName === item.name ? "active" : ""}`}
                  onClick={() => setSelectedName(item.name)}
                >
                  <span className="version-number">V{item.number}</span>
                  <span className="version-list-copy">
                    <span className="version-list-title">
                      {item.label || item.source}
                      {item.protected && <Icon name="star" size={11} title="Geschützte Version"/>}
                    </span>
                    <span className="version-list-summary">{item.change_summary || "Gespeicherter Stand"}</span>
                    <span className="version-list-meta">{formatDate(item.created)} · {displayUser(item.created_by)}</span>
                  </span>
                  {item.is_current && <span className="version-current-dot" title="Aktueller Stand"/>}
                </button>
                {!!item.group_members?.length && <button className="btn sm ghost" onClick={() => toggleGroup(item.name)} aria-expanded={!!expandedGroups[item.name]}>{expandedGroups[item.name] ? "Zwischenstände ausblenden" : `${item.group_members.length} Zwischenstände einblenden`}</button>}
                </div>
              ))}
              {!loading && !filteredItems.length && (
                <div className="version-empty">{items.length ? "Keine passende Version." : "Noch keine Version vorhanden."}</div>
              )}
            </div>
          </aside>

          <main className="version-detail-pane">
            {error && <div className="version-error">{error}</div>}
            {selected ? (
              <>
                <div className="version-detail-head">
                  <div>
                    <div className="version-detail-kicker">Version {selected.number} {selected.assistant_created && <span>KI</span>} {selected.is_proposal && <span>Vorschlag · nicht aktiv</span>} {selected.is_current && <span>Aktueller Stand</span>}</div>
                    <div className="version-detail-date">{formatDate(selected.created)} von {displayUser(selected.created_by)}</div>
                  </div>
                  <div className="version-detail-actions">
                    <button
                      className={`btn ghost ${selected.protected ? "version-protected" : ""}`}
                      onClick={() => saveMetadata({ protected: !selected.protected })}
                      disabled={savingMeta || deletingVersion}
                      title={selected.protected ? "Schutz aufheben" : "Als wichtige Version schützen"}
                    >
                      <Icon name="star" size={13}/> {selected.protected ? "Geschützt" : "Schützen"}
                    </button>
                    <button
                      className="btn ghost version-delete"
                      onClick={removeSelected}
                      disabled={deletingVersion || !selected.can_delete}
                      title={selected.delete_block_reasons?.join("\n") || selected.delete_block_reason || "Diese Version endgültig löschen"}
                    >
                      <Icon name="trash" size={13}/> {deletingVersion ? "Wird gelöscht …" : "Löschen"}
                    </button>
                    <button className="btn primary" onClick={restore} disabled={restoring || deletingVersion || selected.is_current} title={selected.is_current ? "Diese Version ist bereits aktuell" : "Als ungespeicherten Entwurf in den Editor laden"}>
                      <Icon name="repeat" size={13}/> {restoring ? "Wird geladen …" : "Wiederherstellen"}
                    </button>
                  </div>
                </div>

                {!!selected.group_members?.length && <div className="version-group-summary">
                  <strong>Zusammenfassung: {selected.group_members.length + 1} Versionen · Ergebnis V{selected.number}</strong>
                  <button className="btn sm ghost" onClick={() => toggleGroup(selected.name)}>{expandedGroups[selected.name] ? "Zwischenstände ausblenden" : "Zwischenstände einblenden"}</button>
                  {canManageHistory && <button className="btn sm ghost" disabled={groupBusy} onClick={() => changeGroup(true)}>Zusammenfassung auflösen</button>}
                </div>}
                {selected.history_group && <div className="version-group-summary">Zwischenstand einer Zusammenfassung. <button className="btn sm ghost" onClick={() => setSelectedName(selected.history_group)}>Ergebnisversion öffnen</button></div>}
                {!selected.can_delete && <details className="version-delete-reasons"><summary>Warum ist Löschen gesperrt?</summary><ul>{(selected.delete_block_reasons || [selected.delete_block_reason]).filter(Boolean).map(reason => <li key={reason}>{reason}</li>)}</ul><button className="btn sm ghost" onClick={() => setView("usage")}>Verknüpfte Briefe und Durchläufe ansehen</button></details>}

                <div className="version-label-editor">
                  <label htmlFor="version-label">Bezeichnung</label>
                  <input id="version-label" value={label} onChange={(e) => setLabel(e.target.value)} placeholder="z. B. Freigabe Rechtsabteilung" maxLength={140}/>
                  <button className="btn sm" onClick={() => saveMetadata({ label })} disabled={savingMeta || deletingVersion || label === (selected.label || "")}>Übernehmen</button>
                </div>

                <div className="version-change-chips">
                  {(selected.change_summary || "Gespeicherter Stand").split(",").map((part) => <span key={part}>{part.trim()}</span>)}
                  {selected.restored_from && <span>Wiederherstellung</span>}
                </div>

                <div className="version-view-tabs">
                  <button className={view === "preview" ? "active" : ""} onClick={() => setView("preview")}><Icon name="file" size={13}/> PDF-Vorschau</button>
                  <button className={view === "usage" ? "active" : ""} onClick={() => setView("usage")}><Icon name="file" size={13}/> Verknüpfte Briefe</button>
                  <button className={view === "compare" ? "active" : ""} onClick={() => setView("compare")}><Icon name="repeat" size={13}/> Mit aktuellem Stand vergleichen</button>
                </div>

                {view === "preview" && <label className="preview-placeholder-option">
                  <input type="checkbox" checked={placeholderMode} onChange={(event) => setPlaceholderMode(event.target.checked)}/>
                  Fehlende Eingaben als Variablennamen anzeigen
                </label>}
                <div className="version-view-body">
                  {view === "usage" && <VersionUsagePanel key={`${template.id}|${selected.name}`} template={template.id} version={selected.name} grouped={!!selected.group_members?.length}/>}

                  {view === "preview" && (
                    <div className="version-preview-content">
                      {!previewLoading && <PreviewFeedback report={preview}/>}
                      {!!preview?.inputs?.some((field) => field.fillable) && (
                        <details className="version-preview-values" open={preview.ready === false}>
                          <summary>Werte für die Vorschau eingeben</summary>
                          <form onSubmit={(event) => {
                            event.preventDefault();
                            setAppliedValues((current) => ({ ...current, [selected.name]: { ...draftValues[selected.name] } }));
                            previewCacheRef.current.clear();
                            setPreviewCacheRevision((value) => value + 1);
                          }}>
                            <p>Diese Werte gelten nur für die Vorschau. Vorlage und Version bleiben unverändert.</p>
                            <div className="version-preview-fields">{preview.inputs.filter((field) => field.fillable).map((field) => (
                              <label key={field.field}>
                                <span>{field.label}{field.required ? " *" : ""}</span>
                                <PreviewValueInput field={field} value={draftValues[selected.name]?.[field.field]} onChange={(value) => setDraftValues((current) => ({ ...current, [selected.name]: { ...current[selected.name], [field.field]: value } }))}/>
                              </label>
                            ))}</div>
                            <button className="btn primary" type="submit" disabled={previewLoading}>Mit diesen Werten rendern</button>
                          </form>
                        </details>
                      )}
                      {previewLoading && <div className="version-loading"><span className="spinner"/> Version wird gerendert …</div>}
                      {!previewLoading && pdfUrl && <div className="version-pdf-wrap"><iframe title={`Vorschau Version ${selected.number}`} src={pdfUrl}/></div>}
                      {!previewLoading && !pdfUrl && !error && !preview?.errors?.length && <div className="version-empty">Keine Vorschau verfügbar.</div>}
                    </div>
                  )}
                  {view === "compare" && (
                    <div className="version-compare">
                      {compareLoading && <div className="version-loading"><span className="spinner"/> Änderungen werden verglichen …</div>}
                      {!compareLoading && comparison && (
                        <>
                          <div className="version-compare-summary">
                            <strong>Version {selected.number}</strong><span>→</span><strong>Aktueller Stand</strong>
                            <span className="version-compare-stat">Variablen {comparison.stats?.variables_before ?? 0} → {comparison.stats?.variables_after ?? 0}</span>
                            <span className="version-compare-stat">Bausteine {comparison.stats?.blocks_before ?? 0} → {comparison.stats?.blocks_after ?? 0}</span>
                          </div>
                          <div className="version-diff-legend"><span className="removed">Entfernt</span><span className="added">Hinzugefügt</span></div>
                          {(comparison.diff || []).some((part) => part.type !== "same") ? (
                            <div className="version-rich-diff">
                              {(comparison.diff || []).map((part, index) => <span key={index} className={part.type}>{part.text}</span>)}
                            </div>
                          ) : (
                            <div className="version-no-diff">
                              <Icon name="check" size={17}/>
                              <strong>Keine inhaltlichen Änderungen</strong>
                              <span>Diese Version entspricht dem aktuellen Stand.</span>
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  )}
                </div>
              </>
            ) : !loading && <div className="version-empty version-empty-large">Version auswählen.</div>}
          </main>
        </div>
      </section>
    </div>
  );
};
