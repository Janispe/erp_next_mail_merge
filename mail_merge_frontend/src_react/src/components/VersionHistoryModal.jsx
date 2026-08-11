import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Icon } from "./Icon.jsx";
import {
  compareTemplateVersion,
  deleteTemplateVersion,
  loadTemplateVersions,
  renderTemplateVersionPreview,
  updateTemplateVersion,
} from "../api.js";
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
  const [pdf, setPdf] = useState("");
  const [previewLoading, setPreviewLoading] = useState(false);
  const [comparison, setComparison] = useState(null);
  const [compareLoading, setCompareLoading] = useState(false);
  const [label, setLabel] = useState("");
  const [savingMeta, setSavingMeta] = useState(false);
  const [restoring, setRestoring] = useState(false);
  const [deletingVersion, setDeletingVersion] = useState(false);
  const [query, setQuery] = useState("");
  const [navigationMode, setNavigationMode] = useState("graph");
  const [previewCacheRevision, setPreviewCacheRevision] = useState(0);
  const [prefetching, setPrefetching] = useState(false);
  const previewCacheRef = useRef(null);
  if (!previewCacheRef.current) previewCacheRef.current = createVersionPreviewCache(renderTemplateVersionPreview);
  const pdfUrl = usePdfUrl(pdf);

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
  }), [template.id, template.haupt_verteil_objekt, recipient?.id, druckSchwarzWeiss]);

  const previewKey = useCallback((version) => `${previewContext}|${version}`, [previewContext]);

  const loadVersionPdf = useCallback(async (version) => {
    const cache = previewCacheRef.current;
    const key = previewKey(version);
    const wasCached = cache.has(key);
    const nextPdf = await cache.load(key, previewParams(version));
    if (!wasCached && cache.has(key)) setPreviewCacheRevision((value) => value + 1);
    return nextPdf;
  }, [previewKey, previewParams]);

  const selected = items.find((item) => item.name === selectedName) || null;
  const filteredItems = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return items;
    return items.filter((item) => [
      `v${item.number}`, item.label, item.source, item.change_summary, item.created_by,
    ].some((value) => String(value || "").toLowerCase().includes(q)));
  }, [items, query]);
  const cachedPreviewCount = useMemo(() => items.reduce(
    (count, item) => count + (previewCacheRef.current.has(previewKey(item.name)) ? 1 : 0),
    0,
  ), [items, previewKey, previewCacheRevision]);

  const reload = async (keepSelection = true) => {
    if (!template?.id) return;
    const requestedTemplateId = template.id;
    setLoading(true);
    setError("");
    try {
      const result = await loadTemplateVersions(template.id);
      const next = result.items || [];
      setItems(next);
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
    setSelectedName("");
    setItemsTemplateId("");
    reload(false);
  }, [open, template?.id, refreshKey]);

  useEffect(() => {
    previewCacheRef.current.clear();
    setPreviewCacheRevision((value) => value + 1);
    setPdf("");
  }, [previewContext]);

  useEffect(() => {
    setLabel(selected?.label || "");
  }, [selectedName, selected?.label]);

  useEffect(() => {
    if (!open || !selected || view !== "preview" || itemsTemplateId !== template.id) return;
    const cache = previewCacheRef.current;
    const key = previewKey(selected.name);
    if (cache.has(key)) {
      setPdf(cache.get(key));
      setPreviewLoading(false);
      return undefined;
    }
    let alive = true;
    setPreviewLoading(true);
    setPdf("");
    loadVersionPdf(selected.name)
      .then((result) => { if (alive) setPdf(result); })
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
              <span className={`version-cache-status ${prefetching || previewLoading ? "loading" : ""}`} title="PDF-Vorschauen werden für diese Editor-Sitzung zwischengespeichert">
                {(prefetching || previewLoading) && <span className="spinner"/>} PDFs {cachedPreviewCount}/{items.length} bereit
              </span>
            )}
            <span>{items.length} {items.length === 1 ? "Version" : "Versionen"}</span>
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
            <div className="version-list">
              {loading && <div className="version-empty"><span className="spinner"/> Historie wird geladen …</div>}
              {!loading && navigationMode === "graph" && filteredItems.length > 0 && (
                <VersionHistoryGraph
                  items={filteredItems}
                  allItems={items}
                  selectedName={selectedName}
                  onSelect={setSelectedName}
                  formatDate={formatDate}
                  displayUser={displayUser}
                />
              )}
              {!loading && navigationMode === "list" && filteredItems.map((item) => (
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
                    <div className="version-detail-kicker">Version {selected.number} {selected.is_current && <span>Aktueller Stand</span>}</div>
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
                      title={selected.delete_block_reason || "Diese Version endgültig löschen"}
                    >
                      <Icon name="trash" size={13}/> {deletingVersion ? "Wird gelöscht …" : "Löschen"}
                    </button>
                    <button className="btn primary" onClick={restore} disabled={restoring || deletingVersion || selected.is_current} title={selected.is_current ? "Diese Version ist bereits aktuell" : "Als ungespeicherten Entwurf in den Editor laden"}>
                      <Icon name="repeat" size={13}/> {restoring ? "Wird geladen …" : "Wiederherstellen"}
                    </button>
                  </div>
                </div>

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
                  <button className={view === "compare" ? "active" : ""} onClick={() => setView("compare")}><Icon name="repeat" size={13}/> Mit aktuellem Stand vergleichen</button>
                </div>

                <div className="version-view-body">
                  {view === "preview" && (
                    <div className="version-pdf-wrap">
                      {previewLoading && <div className="version-loading"><span className="spinner"/> Version wird gerendert …</div>}
                      {!previewLoading && pdfUrl && (
                        <iframe title={`Vorschau Version ${selected.number}`} src={pdfUrl}/>
                      )}
                      {!previewLoading && !pdfUrl && !error && <div className="version-empty">Keine Vorschau verfügbar.</div>}
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
