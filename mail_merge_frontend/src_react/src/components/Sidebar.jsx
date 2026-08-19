import React, { useState, useMemo, useEffect, useRef } from "react";
import { Icon } from "./Icon.jsx";
import { loadPref, savePref } from "../persist.js";

// base64-PDF → Blob-URL (vermeidet riesige data:-URIs / CSP-Probleme)
function usePdfUrl(base64) {
  const [url, setUrl] = useState(null);
  useEffect(() => {
    if (!base64) { setUrl(null); return; }
    try {
      const bin = atob(base64);
      const bytes = new Uint8Array(bin.length);
      for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
      const blob = new Blob([bytes], { type: "application/pdf" });
      const u = URL.createObjectURL(blob);
      setUrl(u);
      return () => URL.revokeObjectURL(u);
    } catch (e) {
      setUrl(null);
    }
  }, [base64]);
  return url;
}

// =========================
// Preview pane — echtes PDF
// =========================
const PreviewPane = ({ template, recipient, recipients, onChangeRecipient, onSearchRecipients,
                       previewPdf, previewLoading, previewError, previewMode, onRefresh, onMaximize,
                       druckSchwarzWeiss, onDruckSchwarzWeissChange,
                       variablesForPreview, previewVars, onPreviewVarChange }) => {
  const [pickerOpen, setPickerOpen] = useState(false);
  const [pvOpen, setPvOpen] = useState(true);
  const [q, setQ] = useState("");
  const pdfUrl = usePdfUrl(previewPdf);

  // Text-Variablen (keine Doctype-Pfad-Variablen) -> hier kann man für die Vorschau
  // testweise Werte setzen, ohne den gespeicherten Default zu verändern.
  const textVars = (variablesForPreview || []).filter(
    (v) => v.variable && v.type !== "Doctype" && v.type !== "Doctype Liste"
  );

  return (
    <div className="preview-pane">
      <div className="preview-control">
        <div className="recipient-picker" onClick={() => setPickerOpen(o => !o)}>
          <Icon name="user" size={13}/>
          <div style={{ display: "flex", flexDirection: "column", lineHeight: 1.2, flex: 1, minWidth: 0 }}>
            <span className="pp-label">Zielobjekt ({template.haupt_verteil_objekt || "—"})</span>
            <span className="pp-value" style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
              {recipient?.label || "Beispielwerte"}
            </span>
          </div>
          <Icon name="chevron-down" size={12}/>
        </div>
        <button className="btn sm icon" title="Vorschau aktualisieren" onClick={onRefresh} disabled={previewLoading}>
          <Icon name="refresh" size={13}/>
        </button>
        <label className="preview-print-option" title="Drucksparende Schwarz-Weiß-Variante für unterstützte Briefköpfe">
          <input
            type="checkbox"
            checked={!!druckSchwarzWeiss}
            onChange={(e) => onDruckSchwarzWeissChange && onDruckSchwarzWeissChange(e.target.checked)}
            disabled={previewLoading}
          />
          <span>S/W</span>
        </label>
        <button className="btn sm icon" title="PDF groß ansehen" onClick={onMaximize}>
          <Icon name="maximize" size={13}/>
        </button>
      </div>

      {pickerOpen && (
        <div style={{ borderBottom: "1px solid var(--border)", background: "var(--surface)", padding: 8, maxHeight: 320, overflow: "auto" }}>
          <div className="ph-search-wrap" style={{ marginBottom: 6 }}>
            <span className="icon-left"><Icon name="search" size={13}/></span>
            <input
              className="ph-search-input"
              placeholder="Zielobjekt suchen…"
              value={q}
              onChange={e => { setQ(e.target.value); onSearchRecipients && onSearchRecipients(e.target.value); }}
            />
          </div>
          <div
            onClick={() => { onChangeRecipient(null); setPickerOpen(false); }}
            className="recipient-row"
            style={{ borderRadius: 4, cursor: "pointer", padding: "6px 10px", fontSize: 12.5,
                     background: !recipient?.id ? "var(--primary-50)" : "transparent" }}
          >
            <div style={{ fontWeight: 500 }}>Beispielwerte</div>
            <div style={{ fontSize: 10.5, color: "var(--text-faint)" }}>Vorschau mit Musterdaten</div>
          </div>
          {(recipients || []).map(r => (
            <div
              key={r.id}
              onClick={() => { onChangeRecipient(r); setPickerOpen(false); }}
              style={{ padding: "6px 10px", borderRadius: 4, cursor: "pointer", fontSize: 12.5,
                       background: r.id === recipient?.id ? "var(--primary-50)" : "transparent" }}
            >
              <div style={{ fontWeight: 500 }}>{r.label}</div>
              <div style={{ fontSize: 10.5, color: "var(--text-faint)", fontFamily: "var(--font-mono)" }}>{r.id}</div>
            </div>
          ))}
          {(recipients || []).length === 0 && (
            <div className="empty-hint" style={{ padding: 8 }}>Keine Zielobjekt gefunden.</div>
          )}
        </div>
      )}

      {textVars.length > 0 && (
        <div className="pv-section">
          <div className="pv-head" onClick={() => setPvOpen((o) => !o)}>
            <Icon name="chevron-right" size={11} style={{ transform: pvOpen ? "rotate(90deg)" : "none" }}/>
            <span>Vorschau-Werte</span>
            <span className="pv-count">{textVars.length}</span>
          </div>
          {pvOpen && (
            <div className="pv-body">
              <div className="pv-hint">Werte nur für die Vorschau — wird <strong>nicht</strong> gespeichert.</div>
              {textVars.map((v) => (
                <label key={v.variable} className="pv-row">
                  <span className="pv-label" title={v.variable}>{v.label || v.variable}</span>
                  <input
                    className="pv-input"
                    value={(previewVars && previewVars[v.variable]) || ""}
                    placeholder={v.value ? `Standard: ${v.value}` : "Wert für Vorschau"}
                    onChange={(e) => onPreviewVarChange && onPreviewVarChange(v.variable, e.target.value)}
                    spellCheck={false}
                  />
                </label>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="preview-doc" style={{ position: "relative" }}>
        {previewLoading && <div className="editor-loading">PDF wird gerendert …</div>}
        {!previewLoading && previewError && (
          <div className="editor-loading" style={{ color: "var(--danger)", padding: 16, textAlign: "center" }}>
            {previewError}
          </div>
        )}
        {!previewLoading && !previewError && pdfUrl && (
          <iframe title="PDF-Vorschau" src={pdfUrl} style={{ width: "100%", height: "100%", border: "none", minHeight: 420 }}/>
        )}
        {!previewLoading && !previewError && !pdfUrl && (
          <div className="editor-loading">Noch keine Vorschau · „▶" zum Rendern.</div>
        )}
      </div>
      <div className="preview-footer">
        <span>
          <span className="render-dot"/>{" "}
          {previewMode === "durchlauf" ? "Echter Zielobjekt" :
           previewMode === "split_preview" ? "Beispielwerte" : "PDF-Vorschau"}
          {" · gespeicherter Stand"}
        </span>
        {pdfUrl && (
          <a className="btn sm ghost" href={pdfUrl} download={`vorlage-${template.id || "preview"}.pdf`} title="PDF herunterladen">
            <Icon name="download" size={12}/> PDF
          </a>
        )}
      </div>
    </div>
  );
};

// =========================
// Placeholder pane — rekursiver Baum (Parität zum alten Formular-Picker)
// =========================
const nodeMatches = (n, q) =>
  (n.label || "").toLowerCase().includes(q) || (n.token || "").toLowerCase().includes(q);

function filterNodes(nodes, q) {
  if (!q) return nodes || [];
  const out = [];
  for (const n of nodes || []) {
    const kids = filterNodes(n.children, q);
    if (nodeMatches(n, q) || kids.length) out.push({ ...n, children: kids });
  }
  return out;
}

export function countTokens(nodes) {
  let c = 0;
  for (const n of nodes || []) {
    if (n.token) c++;
    c += countTokens(n.children);
  }
  return c;
}

const TreeNode = ({ node, depth, onInsert, expandAll, tokenTransform }) => {
  const [open, setOpen] = useState(false);
  const [idx, setIdx] = useState(1); // 1-basiert; welches Child-Element
  const hasChildren = (node.children || []).length > 0;
  const isOpen = expandAll || open;
  const isTable = node.type === "Tabelle";
  const xform = tokenTransform || ((t) => t);

  // Für Kinder einer Tabelle: [0] -> [idx-1] (gewähltes Element).
  const childTransform = isTable ? (t) => xform(t).replace("[0]", `[${idx - 1}]`) : xform;
  const effToken = node.token ? xform(node.token) : "";

  // Listen-Pfad der Tabelle aus dem ersten Kind-Token ableiten (z. B. objekt.person).
  const childTok = (node.children || []).map((c) => c.token).find(Boolean) || "";
  const listPath = (/\{\{\$\s*(.+?)\[0\]\./.exec(childTok) || [])[1] || "";
  // Schleife nur für DIREKTE Child-Tabellen des Iterations-Objekts (objekt.<feld>).
  // Tabellen unter einem Link-Feld (objekt.objekt.<tabelle>) brechen beim Rendern, weil
  // der Link im Kontext ein unaufgelöster String ist — Loop-Button dort ausblenden.
  const canLoop = isTable && /^objekt\.[^.]+$/.test(listPath);

  // "Schleife über alle": Loop-Gerüst aus den Kindern ableiten.
  const insertLoop = () => {
    if (!listPath) return;
    const firstField =
      (node.children || [])
        .map((c) => (/\[0\]\.(\w+)/.exec(c.token || "") || [])[1])
        .find((f) => f && f !== "name") || "name";
    onInsert(`{% for eintrag in ${listPath} %}\n{{ eintrag.${firstField} }}\n{% endfor %}`);
  };

  return (
    <div className="ph-tree-node">
      <div className="ph-tree-row" style={{ paddingLeft: 6 + depth * 14 }}>
        {hasChildren ? (
          <span className="ph-tree-chev" onClick={() => setOpen(o => !o)}>
            <Icon name="chevron-right" size={11} style={{ transform: isOpen ? "rotate(90deg)" : "none" }}/>
          </span>
        ) : (
          <span className="ph-tree-chev spacer"/>
        )}
        <span
          className="ph-tree-label"
          draggable={!!effToken}
          onDragStart={effToken ? (e) => {
            e.dataTransfer.setData("application/json", JSON.stringify({ kind: "placeholder", token: effToken }));
            e.dataTransfer.effectAllowed = "copy";
          } : undefined}
          onClick={() => (effToken ? onInsert(effToken) : hasChildren && setOpen(o => !o))}
          title={effToken ? `Einfügen: ${effToken}` : node.label}
        >
          {node.label}
          {node.type && <span className="ph-tree-token ph-tree-type">{node.type}</span>}
        </span>
        {isTable && (
          <span className="ph-table-tools" onClick={(e) => e.stopPropagation()}>
            <input
              className="ph-idx-input"
              type="number"
              min={1}
              value={idx}
              title="Welches Element (1 = erstes)"
              onChange={(e) => setIdx(Math.max(1, parseInt(e.target.value, 10) || 1))}
            />
            {canLoop && (
              <button className="ph-loop-btn" onClick={insertLoop} title="Schleife über alle Zeilen einfügen">
                ↻ alle
              </button>
            )}
          </span>
        )}
        {effToken && (
          <button className="ph-tree-insert" onClick={() => onInsert(effToken)} title="Einfügen">+</button>
        )}
      </div>
      {hasChildren && isOpen && (node.children || []).map((c, i) => (
        <TreeNode key={i} node={c} depth={depth + 1} onInsert={onInsert} expandAll={expandAll} tokenTransform={childTransform}/>
      ))}
    </div>
  );
};

const PlaceholderPane = ({
  groups, advancedGroups, meta, advancedLoading, onLoadAdvanced, onOpenProfile, onInsert,
}) => {
  const [q, setQ] = useState("");
  const [collection, setCollection] = useState("standard");
  const query = q.trim().toLowerCase();
  const sourceGroups = collection === "advanced" ? advancedGroups : groups;
  const filtered = useMemo(
    () => (sourceGroups || []).map(g => ({ ...g, tree: filterNodes(g.tree, query) })).filter(g => (g.tree || []).length),
    [sourceGroups, query]
  );

  useEffect(() => {
    if (collection === "advanced" && !(advancedGroups || []).length && (meta?.advanced_count || 0) > 0) {
      onLoadAdvanced?.().catch(() => {});
    }
  }, [collection, advancedGroups, meta?.advanced_count, onLoadAdvanced]);

  const standardCount = meta?.standard_count ?? countTokens((groups || []).flatMap(g => g.tree || []));
  const advancedCount = meta?.advanced_count || 0;

  return (
    <div className="ph-pane">
      <div className="ph-search">
        <div className="ph-search-wrap">
          <span className="icon-left"><Icon name="search" size={13}/></span>
          <input className="ph-search-input" placeholder="Platzhalter suchen…" value={q} onChange={e => setQ(e.target.value)}/>
        </div>
        <div className="ph-collections" role="group" aria-label="Platzhalter-Sichtbarkeit">
          <button
            className={`ph-collection-btn ${collection === "standard" ? "active" : ""}`}
            onClick={() => setCollection("standard")}
          >
            <Icon name="star" size={11}/> Häufig verwendet <span>{standardCount}</span>
          </button>
          <button
            className={`ph-collection-btn ${collection === "advanced" ? "active" : ""}`}
            onClick={() => setCollection("advanced")}
          >
            <Icon name="folder-open" size={11}/> Erweitert <span>{advancedCount}</span>
          </button>
        </div>
        <div className="ph-hint-row">
          <div className="ph-hint">
            {collection === "standard"
              ? "Übliche Felder, Variablen und konfigurierte Pfade"
              : "Alle verfügbaren Pfade – deaktivierte bleiben ausgeblendet"}
          </div>
          {!!onOpenProfile && (
            <button className="ph-profile-btn" onClick={onOpenProfile} title="Platzhalterprofil konfigurieren">
              <Icon name="edit" size={12}/> Verwalten
            </button>
          )}
        </div>
      </div>

      {collection === "advanced" && advancedLoading && (
        <div className="ph-loading"><span className="spinner"/> Erweiterte Pfade werden geladen…</div>
      )}

      {filtered.map(g => (
        <div className="ph-group" key={g.key}>
          <div className="ph-group-title">
            <Icon name={g.icon || "tag"} size={12}/>
            <span>{g.label}</span>
            <span className="ph-group-count">{countTokens(g.tree)}</span>
          </div>
          {(g.tree || []).map((n, i) => (
            <TreeNode key={i} node={n} depth={0} onInsert={onInsert} expandAll={!!query}/>
          ))}
        </div>
      ))}

      {filtered.length === 0 && (
        <div className="empty-hint" style={{ marginTop: 24 }}>
          {collection === "advanced" && advancedLoading
            ? ""
            : `Keine Platzhalter${query ? ` für „${q}"` : ""}.`}
        </div>
      )}
    </div>
  );
};

// =========================
// Bausteine pane (echt)
// =========================
const BAUSTEIN_VALUE_TYPES = new Set(["Text", "Bool"]);
const BAUSTEIN_AUTO_TAGS = [
  { tag: "Briefgestaltung", match: /briefkopf|footer|fußzeile|fusszeile|unterschrift/i },
  { tag: "Betriebskosten", match: /betriebskosten|bk[- ]?abrechnung|nebenkosten|heizkosten/i },
  { tag: "Zahlung & Mahnung", match: /bank|zahlung|mietkonto|rückstand|rueckstand|mahnung/i },
  { tag: "Anrede & Personen", match: /anrede|mieter.*name|eigentümer|eigentuemer|empfänger|empfaenger/i },
  { tag: "Mietvertrag", match: /mietvertrag|miethistorie|mietverhältnis|mietverhaeltnis/i },
  { tag: "Hinweise", match: /hinweis|lüft|lueft|rauchwarn|information/i },
];

function tagsForBaustein(baustein) {
  const explicit = Array.isArray(baustein?.tags)
    ? baustein.tags
    : String(baustein?.tags || "").split(",");
  const clean = explicit.map((tag) => String(tag || "").trim()).filter(Boolean);
  if (clean.length) return [...new Set(clean)];
  const haystack = `${baustein?.title || ""} ${baustein?.description || ""}`;
  const automatic = BAUSTEIN_AUTO_TAGS.filter((rule) => rule.match.test(haystack)).map((rule) => rule.tag);
  return automatic.length ? automatic : ["Sonstige"];
}

const BausteinePane = ({
  items,
  onInsert,
  onLoadPreview,
  recipient,
  hauptVerteilObjekt,
  editable,
}) => {
  const [q, setQ] = useState("");
  const [selectedName, setSelectedName] = useState("");
  const [collection, setCollection] = useState("all");
  const [activeTag, setActiveTag] = useState("");
  const [favorites, setFavorites] = useState(() => new Set(loadPref("bausteinFavorites", [])));
  const [recent, setRecent] = useState(() => loadPref("bausteinRecent", []));
  const [collapsedGroups, setCollapsedGroups] = useState(
    () => new Set(loadPref("bausteinCollapsedGroups", []))
  );
  const [previewHtml, setPreviewHtml] = useState("");
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState("");
  const decorated = useMemo(
    () => items.map((item) => ({ ...item, catalogTags: tagsForBaustein(item) })),
    [items]
  );
  const allTags = useMemo(
    () => [...new Set(decorated.flatMap((item) => item.catalogTags))].sort((a, b) => a.localeCompare(b, "de")),
    [decorated]
  );
  const filtered = useMemo(() => {
    const query = q.trim().toLowerCase();
    let result = decorated;
    if (collection === "favorites") result = result.filter((b) => favorites.has(b.name));
    if (collection === "recent") {
      const order = new Map(recent.map((name, index) => [name, index]));
      result = result.filter((b) => order.has(b.name)).sort((a, b) => order.get(a.name) - order.get(b.name));
    }
    if (activeTag) result = result.filter((b) => b.catalogTags.includes(activeTag));
    if (query) {
      result = result.filter((b) =>
        (b.title || "").toLowerCase().includes(query) ||
        (b.description || "").toLowerCase().includes(query) ||
        (b.preview || "").toLowerCase().includes(query) ||
        b.catalogTags.some((tag) => tag.toLowerCase().includes(query))
      );
    }
    return result;
  }, [q, decorated, collection, activeTag, favorites, recent]);
  const grouped = useMemo(() => {
    if (collection === "recent") return [["Zuletzt verwendet", filtered]];
    const groups = new Map();
    filtered.forEach((item) => {
      const group = activeTag || item.catalogTags[0] || "Sonstige";
      if (!groups.has(group)) groups.set(group, []);
      groups.get(group).push(item);
    });
    return [...groups.entries()].sort(([a], [b]) => a.localeCompare(b, "de"));
  }, [filtered, collection, activeTag]);
  const selected = useMemo(
    () => decorated.find((b) => b.name === selectedName) || null,
    [decorated, selectedName]
  );

  useEffect(() => savePref("bausteinFavorites", [...favorites]), [favorites]);
  useEffect(() => savePref("bausteinRecent", recent), [recent]);
  useEffect(() => savePref("bausteinCollapsedGroups", [...collapsedGroups]), [collapsedGroups]);

  const toggleFavorite = (name) => {
    setFavorites((current) => {
      const next = new Set(current);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  };
  const markRecent = (name) => {
    setRecent((current) => [name, ...current.filter((entry) => entry !== name)].slice(0, 6));
  };
  const selectBaustein = (name) => {
    markRecent(name);
    setSelectedName(name);
  };
  const insertBaustein = (name) => {
    markRecent(name);
    onInsert(name);
  };
  const toggleGroup = (group) => {
    setCollapsedGroups((current) => {
      const next = new Set(current);
      if (next.has(group)) next.delete(group);
      else next.add(group);
      return next;
    });
  };

  useEffect(() => {
    if (!selected || typeof onLoadPreview !== "function") {
      setPreviewHtml("");
      setPreviewLoading(false);
      setPreviewError("");
      return;
    }
    let alive = true;
    setPreviewLoading(true);
    setPreviewError("");
    Promise.resolve(onLoadPreview(selected.name))
      .then((html) => {
        if (alive) setPreviewHtml(html || "");
      })
      .catch((e) => {
        if (!alive) return;
        setPreviewHtml("");
        setPreviewError((e && e.message) || String(e));
      })
      .finally(() => {
        if (alive) setPreviewLoading(false);
      });
    return () => { alive = false; };
  }, [selected, onLoadPreview]);

  const onDragStart = (e, name) => {
    e.dataTransfer.setData("application/json", JSON.stringify({ kind: "baustein", name }));
    e.dataTransfer.effectAllowed = "copy";
  };

  if (selected) {
    const inputs = selected.inputs || [];
    const values = inputs.filter((inp) => BAUSTEIN_VALUE_TYPES.has((inp.type || "").trim()));
    const objectInputs = inputs.filter((inp) => !BAUSTEIN_VALUE_TYPES.has((inp.type || "").trim()));
    const outputs = selected.outputs || [];
    const standards = selected.standardpfade || [];
    const activeStandard = standards.find((s) => s.startobjekt === hauptVerteilObjekt);
    const standardMappings = activeStandard?.mappings || {};
    const previewContext = recipient?.label || "Beispielwerte";
    const purpose = selected.description ||
      `Fügt den zentral gepflegten Inhalt „${selected.title || selected.name}“ an der aktuellen Cursorposition in den Brief ein.`;

    return (
      <div className="bs-pane bs-detail-pane">
        <button className="bs-detail-back" onClick={() => setSelectedName("")}>
          <Icon name="back" size={13}/> Alle Bausteine
        </button>

        <section className="bs-detail-card">
          <div className="bs-detail-title-row">
            <span className="bs-detail-icon"><Icon name="block" size={15}/></span>
            <div className="bs-detail-title-main">
              <h3>{selected.title || selected.name}</h3>
              <code>{`{{ baustein("${selected.name}") }}`}</code>
              <div className="bs-detail-tags">
                {selected.catalogTags.map((tag) => <span key={tag}>{tag}</span>)}
              </div>
            </div>
            <button
              type="button"
              className={`bs-favorite-btn ${favorites.has(selected.name) ? "active" : ""}`}
              aria-label={favorites.has(selected.name) ? "Aus Favoriten entfernen" : "Zu Favoriten hinzufügen"}
              title={favorites.has(selected.name) ? "Aus Favoriten entfernen" : "Zu Favoriten hinzufügen"}
              onClick={() => toggleFavorite(selected.name)}
            >
              <Icon name="star" size={15}/>
            </button>
          </div>

          <div className="bs-detail-section">
            <div className="bs-detail-label">Was macht dieser Baustein?</div>
            <p className="bs-detail-purpose">{purpose}</p>
          </div>

          <div className="bs-detail-section">
            <div className="bs-detail-label-row">
              <span className="bs-detail-label">Gerenderte Vorschau</span>
              <span className="bs-context-badge" title={previewContext}>{previewContext}</span>
            </div>
            {previewLoading ? (
              <div className="bs-detail-loading"><span className="spinner"/> Vorschau wird gerendert…</div>
            ) : previewError ? (
              <div className="bs-detail-error">Vorschau konnte nicht geladen werden: {previewError}</div>
            ) : previewHtml ? (
              <div
                className="bs-detail-rendered baustein-preview-body"
                dangerouslySetInnerHTML={{ __html: previewHtml }}
              />
            ) : selected.preview ? (
              <div className="bs-detail-rendered bs-detail-plain-preview">{selected.preview}</div>
            ) : (
              <div className="bs-detail-empty">Dieser Baustein erzeugt keinen direkt sichtbaren Inhalt.</div>
            )}
          </div>

          {(objectInputs.length > 0 || values.length > 0) && (
            <div className="bs-detail-section">
              <div className="bs-detail-label">Benötigt</div>
              <div className="bs-info-list">
                {objectInputs.map((inp) => (
                  <div className="bs-info-row" key={`input-${inp.name}`}>
                    <span className="bs-info-dot bs-info-dot-in"/>
                    <div className="bs-info-main">
                      <strong>{inp.label || inp.name}</strong>
                      {inp.desc && <span>{inp.desc}</span>}
                      {standardMappings[inp.name] && <code>{standardMappings[inp.name]}</code>}
                    </div>
                    <span className="bs-info-type">{inp.reference_doctype || inp.type}</span>
                  </div>
                ))}
                {values.map((inp) => (
                  <div className="bs-info-row" key={`value-${inp.name}`}>
                    <span className="bs-info-dot bs-info-dot-value"/>
                    <div className="bs-info-main">
                      <strong>{inp.label || inp.name}</strong>
                      <span>{inp.desc || "Wird beim Baustein im Brief konfiguriert."}</span>
                    </div>
                    <span className="bs-info-type">{inp.type}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {outputs.length > 0 && (
            <div className="bs-detail-section">
              <div className="bs-detail-label">Stellt bereit</div>
              <div className="bs-info-list">
                {outputs.map((out) => (
                  <div className="bs-info-row" key={`output-${out.name}`}>
                    <span className="bs-info-dot bs-info-dot-out"/>
                    <div className="bs-info-main">
                      <strong>{out.label || out.name}</strong>
                      {out.desc && <span>{out.desc}</span>}
                    </div>
                    <span className="bs-info-type">{out.reference_doctype || out.type}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="bs-detail-section bs-detail-meta">
            <span>
              <strong>{objectInputs.length + values.length}</strong> Eingaben
            </span>
            <span><strong>{outputs.length}</strong> Ausgaben</span>
            <span title={standards.map((s) => s.startobjekt).join(", ")}>
              <strong>{standards.length}</strong> Standard-Zuordnungen
            </span>
          </div>

          <button
            className="btn primary bs-detail-insert"
            disabled={!editable}
            onClick={() => insertBaustein(selected.name)}
          >
            <Icon name="plus" size={13}/> An Cursor einfügen
          </button>
        </section>
      </div>
    );
  }

  return (
    <div className="bs-pane">
      <div className="ph-search" style={{ paddingBottom: 8 }}>
        <div className="ph-search-wrap">
          <span className="icon-left"><Icon name="search" size={13}/></span>
          <input className="ph-search-input" placeholder="Baustein suchen…" value={q} onChange={e => setQ(e.target.value)}/>
        </div>
        <div className="ph-hint"><strong>{items.length}</strong> Textbausteine · Nach Tags gruppiert · Ziehen fügt ein</div>
      </div>

      <div className="bs-collection-tabs" role="group" aria-label="Baustein-Sammlung">
        <button className={collection === "all" ? "active" : ""} onClick={() => setCollection("all")}>
          <Icon name="grid" size={12}/> Alle <span>{items.length}</span>
        </button>
        <button className={collection === "favorites" ? "active" : ""} onClick={() => setCollection("favorites")}>
          <Icon name="star" size={12}/> Favoriten <span>{favorites.size}</span>
        </button>
        <button className={collection === "recent" ? "active" : ""} onClick={() => setCollection("recent")}>
          <Icon name="clock" size={12}/> Zuletzt
        </button>
      </div>

      <div className="bs-tag-filter" aria-label="Nach Tag filtern">
        <button className={!activeTag ? "active" : ""} onClick={() => setActiveTag("")}>Alle Tags</button>
        {allTags.map((tag) => (
          <button key={tag} className={activeTag === tag ? "active" : ""} onClick={() => setActiveTag(activeTag === tag ? "" : tag)}>
            {tag}
          </button>
        ))}
      </div>

      {grouped.map(([group, groupItems]) => {
        if (!groupItems.length) return null;
        const collapsed = collapsedGroups.has(group);
        return (
          <section className="bs-catalog-group" key={group}>
            <button className="bs-catalog-group-head" onClick={() => toggleGroup(group)} aria-expanded={!collapsed}>
              <Icon name="chevron-down" size={12} className={collapsed ? "collapsed" : ""}/>
              <span>{group}</span>
              <span className="bs-catalog-group-count">{groupItems.length}</span>
            </button>
            {!collapsed && groupItems.map((b) => (
              <div
                key={b.name}
                className="bs-card"
                draggable={!!editable}
                onDragStart={e => onDragStart(e, b.name)}
              >
                <button
                  type="button"
                  className="bs-card-select"
                  aria-label={`${b.title || b.name} – Details anzeigen`}
                  onClick={() => selectBaustein(b.name)}
                >
                  <div className="bs-head">
                    <Icon name="block" size={13} style={{ color: "var(--accent)" }}/>
                    <div style={{ flex: 1 }}>
                      <div className="bs-title">{b.title}</div>
                      {b.description && <div className="bs-desc">{b.description}</div>}
                    </div>
                    <Icon name="chevron-right" size={13} className="bs-open-icon"/>
                  </div>
                  {b.preview && <div className="bs-preview">{b.preview}</div>}
                  <div className="bs-card-tags">
                    {b.catalogTags.map((tag) => <span key={tag}>{tag}</span>)}
                  </div>
                  <div className="bs-card-meta">
                    <span>{(b.inputs || []).length} Eingaben</span>
                    <span>{(b.outputs || []).length} Ausgaben</span>
                  </div>
                </button>
                <div className="bs-actions">
                  <button
                    type="button"
                    className={`bs-favorite-btn ${favorites.has(b.name) ? "active" : ""}`}
                    aria-label={favorites.has(b.name) ? `${b.title} aus Favoriten entfernen` : `${b.title} zu Favoriten hinzufügen`}
                    title={favorites.has(b.name) ? "Aus Favoriten entfernen" : "Zu Favoriten hinzufügen"}
                    onClick={() => toggleFavorite(b.name)}
                  >
                    <Icon name="star" size={13}/>
                  </button>
                  <button
                    className="btn sm"
                    disabled={!editable}
                    onClick={() => insertBaustein(b.name)}
                  >
                    <Icon name="plus" size={12}/> An Cursor einfügen
                  </button>
                </div>
              </div>
            ))}
          </section>
        );
      })}

      {filtered.length === 0 && (
        <div className="bs-empty-state">
          {collection === "favorites" ? (
            <><Icon name="star" size={20}/><strong>Noch keine Favoriten</strong><span>Markiere häufig verwendete Bausteine mit dem Stern.</span></>
          ) : collection === "recent" ? (
            <><Icon name="clock" size={20}/><strong>Noch nichts verwendet</strong><span>Geöffnete und eingefügte Bausteine erscheinen hier.</span></>
          ) : (
            <><Icon name="search" size={20}/><strong>Keine Bausteine gefunden</strong><span>{q ? `Keine Treffer für „${q}“.` : "Für diesen Tag gibt es keine Treffer."}</span></>
          )}
        </div>
      )}
    </div>
  );
};

// =========================
// Variables pane (editierbar: anlegen/löschen, Typ + Wert/Pfad)
// =========================
const VAR_TYPES = ["Text", "String", "Zahl", "Bool", "Datum", "Doctype", "Doctype Liste"];
const isDoctypeType = (t) => t === "Doctype" || t === "Doctype Liste";

// Muss exakt frappe.scrub() entsprechen: " " und "-" -> "_", lowercase. Sonst stimmt der
// im Brief eingefügte {{ name }} nicht mit dem Backend-Schlüssel (frappe.scrub) überein.
const scrubName = (s) => String(s || "").replace(/[ -]/g, "_").toLowerCase();

const captureVariableAssignment = (vars) => {
  const values = {};
  for (const v of vars || []) {
    const key = scrubName(v.variable);
    if (!key) continue;
    if (isDoctypeType(v.type)) values[key] = { path: v.path || "" };
    else values[key] = { value: v.value ?? "" };
  }
  return values;
};

const applyVariableAssignment = (vars, profile) => {
  const values = profile?.values || {};
  return (vars || []).map((v) => {
    const entry = values[scrubName(v.variable)] || {};
    return isDoctypeType(v.type)
      ? { ...v, path: entry.path ?? "" }
      : { ...v, value: entry.value ?? "" };
  });
};

const VariablesPane = ({
  variables, onChange, onInsert, placeholderPaths,
  variableAssignments, onVariableAssignmentsChange, templateId, editable = true,
}) => {
  const vars = variables || [];
  const profiles = variableAssignments || [];
  const [selectedProfile, setSelectedProfile] = useState("");
  useEffect(() => setSelectedProfile(""), [templateId]);
  const update = (i, patch) =>
    onChange && onChange(vars.map((v, idx) => (idx === i ? { ...v, ...patch } : v)));
  const remove = (i) => onChange && onChange(vars.filter((_, idx) => idx !== i));
  const add = () =>
    onChange &&
    onChange([
      ...vars,
      { variable: "", type: "Text", label: "", reference_doctype: "", value: "", path: "" },
    ]);
  const selectProfile = (label) => {
    setSelectedProfile(label);
    if (!label) return;
    const profile = profiles.find((item) => item.label === label);
    if (profile && onChange) onChange(applyVariableAssignment(vars, profile));
  };
  const saveAsProfile = () => {
    if (!editable || !onVariableAssignmentsChange) return;
    const requested = window.prompt("Bezeichnung der Variablenbelegung:", selectedProfile || "");
    const label = String(requested || "").trim();
    if (!label) return;
    const existingIndex = profiles.findIndex((item) => item.label.toLocaleLowerCase() === label.toLocaleLowerCase());
    const nextProfile = {
      label: existingIndex >= 0 ? profiles[existingIndex].label : label,
      is_default: existingIndex >= 0 ? !!profiles[existingIndex].is_default : profiles.length === 0,
      values: captureVariableAssignment(vars),
    };
    if (existingIndex >= 0) {
      if (!window.confirm(`Variablenbelegung „${profiles[existingIndex].label}“ überschreiben?`)) return;
      onVariableAssignmentsChange(profiles.map((item, index) => index === existingIndex ? nextProfile : item));
    } else {
      onVariableAssignmentsChange([...profiles, nextProfile]);
    }
    setSelectedProfile(nextProfile.label);
  };
  const deleteProfile = () => {
    if (!selectedProfile || !window.confirm(`Variablenbelegung „${selectedProfile}“ löschen?`)) return;
    onVariableAssignmentsChange && onVariableAssignmentsChange(
      profiles.filter((item) => item.label !== selectedProfile),
    );
    setSelectedProfile("");
  };
  const toggleDefaultProfile = () => {
    if (!selectedProfile || !onVariableAssignmentsChange) return;
    const selected = profiles.find((item) => item.label === selectedProfile);
    const makeDefault = !selected?.is_default;
    onVariableAssignmentsChange(profiles.map((item) => ({
      ...item,
      is_default: makeDefault ? item.label === selectedProfile : false,
    })));
  };
  const activeProfile = profiles.find((item) => item.label === selectedProfile);

  return (
    <div className="var-pane">
      <div style={{ marginBottom: 10, fontSize: 12, color: "var(--text-muted)", lineHeight: 1.5 }}>
        Vorlagen-Variablen: anlegen, Typ + Wert (Text) bzw. Pfad (Doctype) setzen. Im Brief via{" "}
        <code>{"{{ name }}"}</code> nutzbar. Speichern oben rechts.
      </div>
      <div className="var-profile-box">
        <div className="var-profile-title">Gespeicherte Belegungen</div>
        <div className="var-profile-row">
          <select
            className="var-profile-select"
            value={selectedProfile}
            onChange={(event) => selectProfile(event.target.value)}
            disabled={!editable || profiles.length === 0}
            title="Eine gespeicherte Belegung sofort übernehmen"
          >
            <option value="">Belegung wählen…</option>
            {profiles.map((profile) => (
              <option key={profile.label} value={profile.label}>
                {profile.is_default ? "★ " : ""}{profile.label}
              </option>
            ))}
          </select>
          <button className="var-profile-save" onClick={saveAsProfile} disabled={!editable || vars.length === 0}>
            <Icon name="save" size={11}/> Aktuelle speichern
          </button>
        </div>
        {activeProfile && (
          <div className="var-profile-actions">
            <button onClick={saveAsProfile} disabled={!editable}>Überschreiben</button>
            <button onClick={toggleDefaultProfile} disabled={!editable}>
              {activeProfile.is_default ? "Standard entfernen" : "Als Standard"}
            </button>
            <button className="is-danger" onClick={deleteProfile} disabled={!editable}>Löschen</button>
          </div>
        )}
        <div className="var-profile-hint">
          Die Auswahl ersetzt die aktuellen Werte und Pfade. Gespeichert wird die Änderung zusammen mit der Vorlage.
        </div>
      </div>
      <datalist id="hv-var-path-suggestions">
        {(placeholderPaths || []).map((p, i) => (
          <option key={i} value={p.path}>{p.type ? `${p.path} · ${p.type}` : p.path}</option>
        ))}
      </datalist>

      {vars.map((v, i) => {
        const dt = isDoctypeType(v.type);
        const key = scrubName(v.variable);
        return (
          <div key={i} className="var-edit-row">
            <div className="var-edit-head">
              <input
                className="var-edit-name"
                placeholder="variablen_name"
                value={v.variable || ""}
                onChange={(e) => update(i, { variable: scrubName(e.target.value) })}
                spellCheck={false}
                disabled={!editable}
              />
              <select
                className="var-edit-type"
                value={v.type || "Text"}
                onChange={(e) => update(i, { type: e.target.value })}
                disabled={!editable}
              >
                {VAR_TYPES.map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
              <button className="var-edit-del" title="Variable löschen" onClick={() => remove(i)} disabled={!editable}>
                <Icon name="x" size={12} />
              </button>
            </div>

            {dt ? (
              <>
                <input
                  className="var-edit-sub"
                  placeholder="Referenz-Doctype (z. B. Standort)"
                  value={v.reference_doctype || ""}
                  onChange={(e) => update(i, { reference_doctype: e.target.value })}
                  spellCheck={false}
                  disabled={!editable}
                />
                <input
                  className="var-edit-sub var-edit-path"
                  list="hv-var-path-suggestions"
                  placeholder="Pfad, z. B. objekt.objekt.standort"
                  value={v.path || ""}
                  onChange={(e) => update(i, { path: e.target.value })}
                  spellCheck={false}
                  disabled={!editable}
                />
              </>
            ) : (
              <input
                className="var-edit-sub"
                placeholder="Wert"
                value={v.value || ""}
                onChange={(e) => update(i, { value: e.target.value })}
                disabled={!editable}
              />
            )}

            <div className="var-edit-actions">
              <label className="var-edit-optional" title="Wenn aktiv: leerer Wert ist erlaubt — kein Fehler beim Rendern">
                <input
                  type="checkbox"
                  checked={!!v.optional}
                  onChange={(e) => update(i, { optional: e.target.checked ? 1 : 0 })}
                  disabled={!editable}
                />
                optional
              </label>
              <button
                className="var-insert-btn"
                disabled={!key || !editable}
                onClick={() => onInsert && onInsert(`{{ ${key} }}`)}
                title="In den Brief einfügen"
              >
                <Icon name="tag" size={11} /> einfügen
              </button>
            </div>
          </div>
        );
      })}

      {vars.length === 0 && <div className="empty-hint">Noch keine Variablen.</div>}
      <button className="var-add-btn" onClick={add} disabled={!editable}>
        <Icon name="plus" size={12} /> Variable hinzufügen
      </button>
    </div>
  );
};

// =========================
// Sidebar shell
// =========================
export const Sidebar = ({
  tab, onTab, template, recipient, recipients,
  placeholders, advancedPlaceholders, placeholderMeta, advancedPlaceholdersLoading,
  onLoadAdvancedPlaceholders, onOpenPlaceholderProfile, bausteine,
  onChangeRecipient, onSearchRecipients,
  previewPdf, previewLoading, previewError, previewMode, onRefreshPreview,
  onInsertPlaceholder, onInsertBaustein, onLoadBausteinPreview, onMaximizePreview, onResizeStart,
  variables, variableAssignments, placeholderPaths, onVariablesChange,
  onVariableAssignmentsChange, editable = true,
  druckSchwarzWeiss, onDruckSchwarzWeissChange,
  variablesForPreview, previewVars, onPreviewVarChange,
}) => {
  // „Erweitert“ enthält jetzt bewusst auch die Standardfelder. Deshalb ist sein
  // Zähler bereits die Gesamtzahl und darf nicht mit Standard addiert werden.
  const phCount = placeholderMeta?.advanced_count || placeholderMeta?.standard_count || 0;
  const bsCount = (bausteine || []).length;
  const varCount = (variables || []).length;

  return (
    <aside className="sidebar">
      <div className="sidebar-resize-handle" onMouseDown={onResizeStart} title="Ziehen zum Verbreitern"/>
      <div className="sb-tabs">
        <button className={`sb-tab ${tab === "preview" ? "active" : ""}`} onClick={() => onTab("preview")}>Vorschau</button>
        <button className={`sb-tab ${tab === "placeholders" ? "active" : ""}`} onClick={() => onTab("placeholders")}>
          Platzhalter <span className="sb-tab-badge">{phCount}</span>
        </button>
        <button className={`sb-tab ${tab === "bausteine" ? "active" : ""}`} onClick={() => onTab("bausteine")}>
          Bausteine <span className="sb-tab-badge">{bsCount}</span>
        </button>
        <button className={`sb-tab ${tab === "variables" ? "active" : ""}`} onClick={() => onTab("variables")}>
          Variablen <span className="sb-tab-badge">{varCount}</span>
        </button>
      </div>
      <div className="sb-body">
        {tab === "preview" && (
          <PreviewPane
            template={template} recipient={recipient} recipients={recipients}
            onChangeRecipient={onChangeRecipient} onSearchRecipients={onSearchRecipients}
            previewPdf={previewPdf} previewLoading={previewLoading} previewError={previewError}
            previewMode={previewMode} onRefresh={onRefreshPreview} onMaximize={onMaximizePreview}
            druckSchwarzWeiss={druckSchwarzWeiss}
            onDruckSchwarzWeissChange={onDruckSchwarzWeissChange}
            variablesForPreview={variablesForPreview} previewVars={previewVars}
            onPreviewVarChange={onPreviewVarChange}
          />
        )}
        {tab === "placeholders" && (
          <PlaceholderPane
            groups={placeholders || []}
            advancedGroups={advancedPlaceholders || []}
            meta={placeholderMeta || {}}
            advancedLoading={advancedPlaceholdersLoading}
            onLoadAdvanced={onLoadAdvancedPlaceholders}
            onOpenProfile={template.haupt_verteil_objekt ? onOpenPlaceholderProfile : null}
            onInsert={onInsertPlaceholder}
          />
        )}
        {tab === "bausteine" && (
          <BausteinePane
            items={bausteine || []}
            onInsert={onInsertBaustein}
            onLoadPreview={onLoadBausteinPreview}
            recipient={recipient}
            hauptVerteilObjekt={template.haupt_verteil_objekt}
            editable={editable}
          />
        )}
        {tab === "variables" && (
          <VariablesPane
            variables={variables}
            variableAssignments={variableAssignments}
            onVariableAssignmentsChange={onVariableAssignmentsChange}
            templateId={template.id}
            onChange={onVariablesChange}
            onInsert={onInsertPlaceholder}
            placeholderPaths={placeholderPaths}
            editable={editable}
          />
        )}
      </div>
    </aside>
  );
};
