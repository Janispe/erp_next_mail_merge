import React, { useState, useRef, useEffect, useCallback, useLayoutEffect } from "react";
import { useEditor, EditorContent, BubbleMenu } from "@tiptap/react";
import { Extension } from "@tiptap/core";
import { Plugin, PluginKey } from "@tiptap/pm/state";
import { Decoration, DecorationSet } from "@tiptap/pm/view";
import { Icon } from "./Icon.jsx";
import { SNIPPETS } from "../data.js";
import { buildExtensions } from "../tiptap/extensions.js";
import { decorateForTiptap, serializeToTokens, groupForToken } from "../tiptap/tokens.js";
import { diffTokens } from "../tiptap/validateJinja.js";
import { loadPref, savePref } from "../persist.js";

const pageSimPluginKey = new PluginKey("hvPageSimulation");

const PageSimulationExtension = Extension.create({
	name: "hvPageSimulation",
	addProseMirrorPlugins() {
		return [
			new Plugin({
				key: pageSimPluginKey,
				state: {
					init: () => DecorationSet.empty,
					apply(tr, old) {
						const next = tr.getMeta(pageSimPluginKey);
						if (next) return next;
						return old.map(tr.mapping, tr.doc);
					},
				},
				props: {
					decorations(state) {
						return this.getState(state);
					},
				},
			}),
		];
	},
});

// Einzel-Token (Platzhalter/Baustein/inline-Jinja) als atomarer Node einfügen (robuster als
// HTML-Parsing). Mehr-Token-Snippets mit Leerzeilen -> decorate + insertContent(HTML).
function insertRawToken(editor, raw) {
	if (!editor || !raw) return;
	const t = raw.trim();
	const isSingle =
		(/^\{\{[\s\S]*\}\}$/.test(t) && t.indexOf("}}") === t.length - 2) ||
		(/^\{%[\s\S]*%\}$/.test(t) && t.indexOf("%}") === t.length - 2);
	let node = null;
	if (isSingle) {
		if (/^\{\{\s*baustein\(/.test(t)) node = { type: "hvBaustein", attrs: { token: t } };
		else if (t.startsWith("{{")) {
			const inner = (/\{\{\s*([\s\S]+?)\s*\}\}/.exec(t) || [])[1] || "";
			// In einer Bedingung: bare Feld-Chip (person.anrede) statt {{ }}.
			node = editor.isActive("hvIf")
				? { type: "hvField", attrs: { name: inner, group: groupForToken(inner) } }
				: { type: "hvPlaceholder", attrs: { token: t, group: groupForToken(inner) } };
		} else node = { type: "hvJinjaInline", attrs: { token: t } };
	}
	if (node) editor.chain().focus().insertContent(node).run();
	else editor.chain().focus().insertContent(decorateForTiptap(t)).run();
}

const DEFAULT_PAGE_SIM = {
	pageMm: 297,
	pageGapMm: 14,
	pageWidthMm: 210,
	marginTopMm: 20,
	marginRightMm: 20,
	marginBottomMm: 16,
	marginLeftMm: 25,
};

function currentPageSimulation() {
	const configured = (typeof window !== "undefined" && window.__hvEditorPageLayout) || {};
	const numberOr = (value, fallback) => {
		const parsed = Number(value);
		return Number.isFinite(parsed) && parsed >= 0 ? parsed : fallback;
	};
	return {
		pageMm: numberOr(configured.pageHeightMm, DEFAULT_PAGE_SIM.pageMm),
		pageGapMm: DEFAULT_PAGE_SIM.pageGapMm,
		pageWidthMm: numberOr(configured.pageWidthMm, DEFAULT_PAGE_SIM.pageWidthMm),
		marginTopMm: numberOr(configured.marginTopMm, DEFAULT_PAGE_SIM.marginTopMm),
		marginRightMm: numberOr(configured.marginRightMm, DEFAULT_PAGE_SIM.marginRightMm),
		marginBottomMm: numberOr(configured.marginBottomMm, DEFAULT_PAGE_SIM.marginBottomMm),
		marginLeftMm: numberOr(configured.marginLeftMm, DEFAULT_PAGE_SIM.marginLeftMm),
	};
}

function clearPageSimulation(dom) {
	if (!dom) return;
	dom.querySelectorAll(".hv-page-sim-next").forEach((el) => {
		el.classList.remove("hv-page-sim-next");
		el.style.removeProperty("--hv-page-sim-gap");
	});
}

function clearPageSimulationLayout(canvas) {
	if (!canvas) return;
	updateFooterSourcePlacement(canvas.querySelector(".tiptap-surface"), false);
	canvas.querySelectorAll(":scope > .hv-page-sim-sheet").forEach((el) => el.remove());
	canvas.style.removeProperty("--hv-editor-layout-min-height");
	delete canvas.__hvPageSimulationPages;
}

function updateFooterSourcePlacement(pm, enabled = true) {
	if (!pm) return null;
	pm.querySelectorAll(".hv-footer-source").forEach((el) => el.classList.remove("hv-footer-source"));
	pm.querySelectorAll(".hv-footer-source-row").forEach((el) => el.classList.remove("hv-footer-source-row"));
	if (!enabled) return null;

	const sources = Array.from(pm.querySelectorAll('[data-hv-baustein-name*="Footer" i]'));
	for (const source of sources) {
		source.classList.add("hv-footer-source");
		let block = source;
		while (block.parentElement && block.parentElement !== pm) block = block.parentElement;
		if (block.parentElement !== pm) continue;

		const remaining = block.cloneNode(true);
		remaining.querySelectorAll('[data-hv-baustein-name*="Footer" i]').forEach((el) => el.remove());
		remaining.querySelectorAll("br, .ProseMirror-separator").forEach((el) => el.remove());
		const hasText = !!remaining.textContent?.trim();
		const hasContent = !!remaining.querySelector(
			'img, table, hr, [data-hv-kind="baustein"], [data-hv-kind="placeholder"], [data-hv-kind="jinja-inline"]'
		);
		if (!hasText && !hasContent) block.classList.add("hv-footer-source-row");
	}
	return sources[0] || null;
}

// Fuer eine neue Pagination brauchen wir die natuerlichen Elementpositionen
// ohne bereits gesetzte Simulationsabstaende. Die Decorations bleiben dabei
// im ProseMirror-State erhalten; wir neutralisieren sie nur synchron fuer die
// Messung und stellen den DOM danach wieder her. So koennen veraltete Umbrueche
// (z.B. nach Empfaenger- oder Platzhalterwechsel) auch wieder verschwinden.
function measureWithoutPageSimulation(dom, measure) {
	if (!dom) return measure();
	const saved = Array.from(dom.querySelectorAll(".hv-page-sim-next")).map((el) => ({
		el,
		gap: el.style.getPropertyValue("--hv-page-sim-gap"),
	}));
	saved.forEach(({ el }) => {
		el.classList.remove("hv-page-sim-next");
		el.style.removeProperty("--hv-page-sim-gap");
	});
	try {
		return measure();
	} finally {
		saved.forEach(({ el, gap }) => {
			if (!el.isConnected) return;
			el.classList.add("hv-page-sim-next");
			if (gap) el.style.setProperty("--hv-page-sim-gap", gap);
		});
	}
}

function clearPageSimulationDecorations(editor) {
	if (!editor?.view) return;
	editor.storage.hvPageSimulationKey = null;
	editor.view.dispatch(editor.view.state.tr.setMeta(pageSimPluginKey, DecorationSet.empty));
}

// Chromium darf Listen zwischen <li>-Elementen und Tabellen zwischen Zeilen
// umbrechen. Die alte Simulation sah nur direkte pm.children und behandelte
// damit ein komplettes <ol> als unteilbaren Block. Diese Kandidaten spiegeln
// die tatsächlich umbrechbaren ProseMirror-Knoten samt Dokumentposition.
function collectPageBreakCandidates(editor) {
	const result = [];
	const doc = editor?.view?.state?.doc;
	if (!doc) return result;

	doc.descendants((node, pos, parent) => {
		if (!node.isBlock) return true;
		const type = node.type.name;
		const parentType = parent?.type?.name || "";
		const isTopLevel = parent === doc;
		const isListItem = type === "listItem";
		const isTableRow = type === "tableRow";
		const isTextBlock = !!node.isTextblock;
		const isAtomicBlock = !!node.isAtom;
		const isWholeTopLevelBlock = isTopLevel && !["bulletList", "orderedList", "table"].includes(type);
		const isListFallback = isTextBlock && parentType === "listItem";

		if (isListItem || isTableRow || isWholeTopLevelBlock || isListFallback || isAtomicBlock) {
			const dom = editor.view.nodeDOM(pos);
			if (dom instanceof HTMLElement && dom.isConnected) {
				result.push({ node, offset: pos, element: dom });
			}
		}
		return true;
	});

	return result;
}

function elementOuterHeight(element, measuredHeight) {
	const style = window.getComputedStyle(element);
	const marginTop = Number.parseFloat(style.marginTop) || 0;
	const marginBottom = Number.parseFloat(style.marginBottom) || 0;
	return measuredHeight + marginTop + marginBottom;
}

function elementVerticalChrome(element) {
	const style = window.getComputedStyle(element);
	return [
		style.marginTop,
		style.marginBottom,
		style.paddingTop,
		style.paddingBottom,
		style.borderTopWidth,
		style.borderBottomWidth,
	].reduce((sum, value) => sum + (Number.parseFloat(value) || 0), 0);
}

// Diese Anteile existieren nur, damit die Vorlage im Layoutmodus weiterhin
// bedienbar bleibt. Der Text innerhalb eines Kontrollfluss-Containers bleibt
// bewusst normaler Inhalt; kompensiert werden nur Header, Zweigmarker und
// Rahmen. So wächst eine Seite um die echte Editor-UI, nicht um komplette
// alternative Briefvarianten.
function editorOnlyLayoutMetrics(element, measuredHeight) {
	if (!element) return { extra: 0, skipBreak: false };
	const footer = element.matches('[data-hv-baustein-name*="Footer" i]')
		? element
		: element.querySelector?.('[data-hv-baustein-name*="Footer" i]');
	if (footer) {
		return { extra: elementOuterHeight(element, measuredHeight), skipBreak: true };
	}
	if (element.matches(".jinja-if-container")) {
		const controls = element.querySelectorAll(
			".jinja-if-content > .jinja-if-block, " +
				'.jinja-if-content > .jinja-block[data-hv-branch="else"], ' +
				'.jinja-if-content > .jinja-block[data-hv-branch="elif"]'
		);
		const controlHeight = Array.from(controls).reduce((sum, control) => {
			return sum + elementOuterHeight(control, control.getBoundingClientRect().height);
		}, 0);
		return {
			extra: elementVerticalChrome(element) + controlHeight,
			skipBreak: true,
		};
	}
	if (element.matches(".jinja-if-block, .jinja-block")) {
		if (element.closest(".jinja-if-container")) return { extra: 0, skipBreak: true };
		return { extra: elementOuterHeight(element, measuredHeight), skipBreak: true };
	}
	return { extra: 0, skipBreak: false };
}

function renderPageSimulationSheets(canvas, pages, contentBottom) {
	const existing = Array.from(canvas.querySelectorAll(":scope > .hv-page-sim-sheet"));
	for (let index = existing.length; index < pages.length; index += 1) {
		const sheet = document.createElement("div");
		sheet.className = "hv-page-sim-sheet";
		canvas.prepend(sheet);
		existing.push(sheet);
	}
	for (let index = existing.length - 1; index >= pages.length; index -= 1) {
		existing[index].remove();
		existing.pop();
	}
	pages.forEach((page, index) => {
		const sheet = existing[index];
		sheet.style.top = `${page.top}px`;
		sheet.style.height = `${page.height}px`;
		sheet.style.setProperty("--hv-page-content-bottom", `${contentBottom}px`);
		sheet.dataset.page = String(index + 1);
	});
	const last = pages.at(-1);
	const minHeight = last ? last.top + last.height : 0;
	canvas.style.setProperty("--hv-editor-layout-min-height", `${minHeight}px`);
	canvas.__hvPageSimulationPages = pages.map((page) => ({ ...page }));
}

function applyPageSimulation(canvas, editor) {
	const pm = editor?.view?.dom;
	if (!canvas || !pm) return;
	updateFooterSourcePlacement(pm, true);

	const measured = measureWithoutPageSimulation(pm, () =>
		collectPageBreakCandidates(editor)
			.map((candidate) => {
				const rect = candidate.element.getBoundingClientRect();
				const editorLayout = editorOnlyLayoutMetrics(candidate.element, rect.height);
				return {
					...candidate,
					naturalTop: rect.top,
					height: rect.height,
					editorExtra: editorLayout.extra,
					skipBreak: editorLayout.skipBreak,
				};
			})
			.filter(({ height }) => height > 0)
	);
	const candidates = measured;
	if (!candidates.length) return;

	const page = currentPageSimulation();
	const canvasRect = canvas.getBoundingClientRect();
	const pxPerMm = canvasRect.width / page.pageWidthMm;
	const pageHeight = page.pageMm * pxPerMm;
	const pageGap = page.pageGapMm * pxPerMm;
	const contentTop = page.marginTopMm * pxPerMm;
	const contentBottom = page.marginBottomMm * pxPerMm;
	const contentHeight = pageHeight - contentTop - contentBottom;
	const decorations = [];
	const decorationKeys = [];
	let simulatedShift = 0;
	const movedElements = [];
	const pages = [{ top: 0, height: pageHeight, extra: 0, editorBudget: 0 }];
	let currentPage = pages[0];
	const growCurrentPage = (amount) => {
		const available = Math.max(0, currentPage.editorBudget - currentPage.extra);
		const growth = Math.min(Math.max(0, amount), available);
		if (growth <= 1) return 0;
		currentPage.extra += growth;
		currentPage.height = pageHeight + currentPage.extra;
		return growth;
	};

	const addDecoration = (docChild, gap) => {
		if (!docChild || gap <= 1) return false;
		const style = `--hv-page-sim-gap: ${gap}px`;
		decorationKeys.push(`${docChild.offset}:${docChild.offset + docChild.node.nodeSize}:${style}`);
		decorations.push(
			Decoration.node(docChild.offset, docChild.offset + docChild.node.nodeSize, {
				class: "hv-page-sim-next",
				style,
			})
		);
		return true;
	};

	for (const candidate of candidates) {
		const el = candidate.element;
		// Wurde ein Listenpunkt/Tabellenblock als Ganzes verschoben, darf ein
		// darin liegender Fallback-Kandidat keinen zweiten Abstand erzeugen.
		if (movedElements.some((parent) => parent !== el && parent.contains(el))) continue;

		const top = candidate.naturalTop - canvasRect.top + simulatedShift;
		const height = candidate.height;
		if (candidate.editorExtra > 0) {
			currentPage.editorBudget += Math.max(0, candidate.editorExtra);
		}
		if (candidate.skipBreak) {
			const editorBottom = currentPage.top + currentPage.height - contentBottom;
			growCurrentPage(top + height - editorBottom);
			continue;
		}
		if (height <= 0 || height > contentHeight) continue;

		const pageTop = currentPage.top;
		const pageContentTop = pageTop + contentTop;
		let pageContentBottom = pageTop + currentPage.height - contentBottom;
		let pageVisualBottom = pageTop + currentPage.height;
		let inPageGap = top >= pageVisualBottom - 1;

		if (top <= pageContentTop + 1) continue;
		if (!inPageGap && top + height <= pageContentBottom + 1) continue;
		growCurrentPage(top + height - pageContentBottom);
		pageContentBottom = pageTop + currentPage.height - contentBottom;
		pageVisualBottom = pageTop + currentPage.height;
		inPageGap = top >= pageVisualBottom - 1;
		if (!inPageGap && top + height <= pageContentBottom + 1) continue;

		const nextPageTop = pageTop + currentPage.height + pageGap;
		const nextContentTop = nextPageTop + contentTop;
		const gap = Math.max(0, nextContentTop - top);
		if (addDecoration(candidate, gap)) {
			simulatedShift += gap;
			movedElements.push(el);
			currentPage = { top: nextPageTop, height: pageHeight, extra: 0, editorBudget: 0 };
			pages.push(currentPage);
		}
	}

	renderPageSimulationSheets(canvas, pages, contentBottom);
	const key = [
		decorationKeys.join("|"),
		pages.map((entry) => `${entry.top}:${entry.height}`).join("|"),
	].join("::");
	if (editor.storage.hvPageSimulationKey === key) return;
	editor.storage.hvPageSimulationKey = key;
	editor.view.dispatch(
		editor.view.state.tr.setMeta(pageSimPluginKey, DecorationSet.create(editor.view.state.doc, decorations))
	);
}

// Per-Seite-Footer im Layoutmodus: legt im Bottom-Margin-Bereich jeder
// simulierten Seite ein absolut positioniertes Overlay mit dem gerenderten
// Footer-HTML aus dem Print Format ab. Liest den HTML-Stand aus dem globalen
// window.__hvEditorFooterHtml (in Editor.jsx an die App-Prop synced), damit
// schedulePageSimulation keine zusätzliche Signatur braucht.
function applyFooterOverlays(canvas, editor) {
	if (!canvas) return;
	const footerHtml = (typeof window !== "undefined" && window.__hvEditorFooterHtml) || "";
	const existing = canvas.querySelectorAll(".hv-page-sim-footer-overlay");
	const footerSource =
		editor?.view?.dom?.querySelector('[data-hv-baustein-name*="Footer" i]') || null;
	if (!footerHtml) {
		existing.forEach((el) => el.remove());
		return;
	}
	const pm = editor?.view?.dom;
	const page = currentPageSimulation();
	const canvasRect = canvas.getBoundingClientRect();
	const pxPerMm = canvasRect.width / page.pageWidthMm;
	const pageStep = (page.pageMm + page.pageGapMm) * pxPerMm;
	const pageHeightPx = page.pageMm * pxPerMm;
	const bottomMarginPx = page.marginBottomMm * pxPerMm;
	// Seitenanzahl: jede page-sim-next-Marker ist ein Seitenumbruch → pages = breaks + 1.
	const breaks = pm ? pm.querySelectorAll(".hv-page-sim-next").length : 0;
	const simulatedPages = canvas.__hvPageSimulationPages;
	const pageCount = Math.max(1, simulatedPages?.length || breaks + 1);

	for (let i = existing.length; i < pageCount; i += 1) {
		const el = document.createElement("div");
		el.className = "hv-page-sim-footer-overlay";
		canvas.appendChild(el);
	}
	const overlays = canvas.querySelectorAll(".hv-page-sim-footer-overlay");
	for (let i = overlays.length - 1; i >= pageCount; i -= 1) {
		overlays[i].remove();
	}
	const fresh = canvas.querySelectorAll(".hv-page-sim-footer-overlay");
	fresh.forEach((overlay, idx) => {
		// Top am Beginn des Bottom-Margin-Bereichs der Seite. Der Footer-Inhalt
		// hat selbst eine fixe Höhe (12mm laut Print Format), Rest des Margins
		// bleibt sichtbar leer wie im PDF.
		const simulated = simulatedPages?.[idx];
		const top = simulated
			? simulated.top + simulated.height - bottomMarginPx
			: idx * pageStep + pageHeightPx - bottomMarginPx;
		overlay.style.top = `${top}px`;
		if (overlay.dataset.footerHtml !== footerHtml) {
			overlay.innerHTML = footerHtml;
			overlay.dataset.footerHtml = footerHtml;
		}
		const canOpenFooter = !!footerSource;
		const footerName = footerSource?.dataset?.hvBausteinName || "Footer";
		const openFooter = () => {
			const rect = overlay.getBoundingClientRect();
			window.dispatchEvent(
				new CustomEvent("hv-baustein-popover", {
					detail: {
						name: footerName,
						rect: { left: rect.left, bottom: rect.bottom, top: rect.top },
					},
				})
			);
		};
		overlay.classList.toggle("is-interactive", canOpenFooter);
		overlay.tabIndex = canOpenFooter ? 0 : -1;
		overlay.setAttribute("role", canOpenFooter ? "button" : "presentation");
		overlay.setAttribute(
			"aria-label",
			canOpenFooter ? "Footer-Baustein bearbeiten" : "Gerenderter Seitenfooter"
		);
		overlay.title = canOpenFooter ? "Klick: Footer-Baustein bearbeiten" : "";
		overlay.onclick = canOpenFooter
			? (event) => {
				event.preventDefault();
				event.stopPropagation();
				openFooter();
			}
			: null;
		overlay.onkeydown = canOpenFooter
			? (event) => {
				if (event.key !== "Enter" && event.key !== " ") return;
				event.preventDefault();
				openFooter();
			}
			: null;
	});
}

function schedulePageSimulation(editor) {
	if (!editor) return;
	const run = () => {
		const canvas = document.querySelector(".editor-canvas.hv-baustein-layout");
		if (!canvas) {
			clearPageSimulationDecorations(editor);
			clearPageSimulation(editor.view?.dom);
			clearPageSimulationLayout(document.querySelector(".editor-canvas"));
			// Footer-Overlays räumen, wenn Layoutmodus aus ist (kein Canvas).
			document.querySelectorAll(".hv-page-sim-footer-overlay").forEach((el) => el.remove());
			return;
		}
		applyPageSimulation(canvas, editor);
		applyFooterOverlays(canvas, editor);
	};
	(window.__hvPageSimTimers || []).forEach((timer) => window.clearTimeout(timer));
	window.requestAnimationFrame(() => {
		run();
		window.__hvPageSimTimers = [80, 250, 600].map((delay) => window.setTimeout(run, delay));
	});
}

// =========================
// Kontrollfluss-Menü (Jinja-Snippets: if/for/set …)
// Platzhalter und Bausteine sind über die rechte Sidebar (Tabs „Platzhalter" /
// „Bausteine") erreichbar — hier nur Steuerstrukturen, die es dort nicht gibt.
// =========================

// Konstruiert das Roh-Token aus User-Input für die ``custom``-Snippets.
// Wir trimmen und entfernen vorab schon vorhandene Klammern, falls der User
// sie aus Gewohnheit selbst mitgetippt hat — sonst entstünde ``{% {% if x %} %}``.
function buildCustomToken(wrap, input) {
	const s = (input || "").trim();
	if (!s) return null;
	if (wrap === "block") {
		const inner = s.replace(/^\{%-?\s*|\s*-?%\}$/g, "").trim();
		return inner ? `{% ${inner} %}` : null;
	}
	if (wrap === "expr") {
		const inner = s.replace(/^\{\{\s*|\s*\}\}$/g, "").trim();
		return inner ? `{{ ${inner} }}` : null;
	}
	return null;
}

const SlashMenu = ({ open, x, y, onClose, onPick }) => {
	const snippets = SNIPPETS.map((s) => ({ kind: "snippet", item: s }));
	const [active, setActive] = useState(0);
	// Inline-Eingabe: idx des aktiven custom-Items + aktueller Input. ``null`` = kein
	// Custom-Input aktiv, dann läuft die normale Pfeiltasten-Navigation.
	const [customIdx, setCustomIdx] = useState(null);
	const [customValue, setCustomValue] = useState("");
	const customInputRef = useRef(null);

	useEffect(() => {
		if (open) {
			setActive(0);
			setCustomIdx(null);
			setCustomValue("");
		}
	}, [open]);

	useEffect(() => {
		// Globale Tasten-Navigation NUR, wenn kein Custom-Input aktiv ist —
		// sonst frisst der Menü-Listener Pfeiltasten/Enter im Textfeld.
		if (customIdx !== null) return;
		const onKey = (e) => {
			if (!open) return;
			if (e.key === "Escape") {
				e.preventDefault();
				onClose();
			} else if (e.key === "ArrowDown") {
				e.preventDefault();
				setActive((a) => Math.min(a + 1, snippets.length - 1));
			} else if (e.key === "ArrowUp") {
				e.preventDefault();
				setActive((a) => Math.max(a - 1, 0));
			} else if (e.key === "Enter") {
				e.preventDefault();
				const sel = snippets[active];
				if (!sel) return;
				if (sel.item.custom) {
					// Custom-Item: Inline-Input öffnen statt direkt einfügen.
					setCustomIdx(active);
					setCustomValue("");
				} else {
					onPick(sel);
				}
			}
		};
		window.addEventListener("keydown", onKey);
		return () => window.removeEventListener("keydown", onKey);
	}, [open, snippets, active, onClose, onPick, customIdx]);

	// Beim Öffnen des Inline-Inputs: Fokus rein.
	useEffect(() => {
		if (customIdx !== null && customInputRef.current) {
			customInputRef.current.focus();
		}
	}, [customIdx]);

	const submitCustom = () => {
		const sel = snippets[customIdx];
		if (!sel || !sel.item.custom) return;
		const token = buildCustomToken(sel.item.custom.wrap, customValue);
		if (!token) return; // Leere Eingabe: nichts tun
		onPick({
			kind: "snippet",
			item: { ...sel.item, value: token },
		});
	};

	if (!open) return null;
	return (
		<div className="slash-menu" style={{ left: x, top: y }}>
			<div className="slash-header">
				<span>Kontrollfluss einfügen</span>
				<button
					type="button"
					className="slash-close"
					onClick={onClose}
					title="Schließen (Esc)"
					aria-label="Schließen"
				>
					<Icon name="x" size={12} />
				</button>
			</div>
			<div className="slash-list">
				{snippets.map((m, i) => {
					const isCustom = !!m.item.custom;
					const isInputOpen = isCustom && customIdx === i;
					return (
						<div
							key={`s-${i}`}
							className={`slash-item ${i === active ? "active" : ""} ${isCustom ? "slash-item-custom" : ""}`}
							onMouseEnter={() => {
								// Andere Items hovern schließt den Inline-Input nicht (verwirrend), wir
								// markieren nur als aktiv für visuelles Feedback.
								setActive(i);
							}}
							onClick={() => {
								if (isCustom) {
									if (customIdx === i) {
										// Zweiter Klick: gleich submitten.
										submitCustom();
									} else {
										setCustomIdx(i);
										setCustomValue("");
									}
								} else {
									onPick(m);
								}
							}}
						>
							<span className="slash-icon">
								<Icon name="branch" size={13} />
							</span>
							<span className="slash-text">
								<div className="slash-label">{m.item.label}</div>
								<div className="slash-desc">{m.item.desc}</div>
								{isInputOpen && (
									<div
										className="slash-custom-input"
										onClick={(e) => e.stopPropagation()}
									>
										<input
											ref={customInputRef}
											type="text"
											value={customValue}
											placeholder={m.item.custom.placeholder || ""}
											onChange={(e) => setCustomValue(e.target.value)}
											onKeyDown={(e) => {
												if (e.key === "Enter") {
													e.preventDefault();
													submitCustom();
												} else if (e.key === "Escape") {
													e.preventDefault();
													setCustomIdx(null);
													setCustomValue("");
												}
											}}
										/>
										<button
											type="button"
											className="slash-custom-submit"
											onClick={(e) => {
												e.stopPropagation();
												submitCustom();
											}}
											disabled={!customValue.trim()}
										>
											Einfügen
										</button>
									</div>
								)}
							</span>
						</div>
					);
				})}
			</div>
		</div>
	);
};

// =========================
// Toolbar (TipTap-Chain-Commands + aktive States)
// =========================
const TBtn = ({ on, active, disabled, title, children }) => (
	<button
		className={`tool-btn ${active ? "is-active" : ""}`}
		title={title}
		disabled={disabled}
		onMouseDown={(e) => e.preventDefault()}
		onClick={on}
	>
		{children}
	</button>
);

const EditorToolbar = ({
	editor,
	disabled,
	onInsert,
	onImage,
	showGrid,
	onToggleGrid,
	bausteinLayoutMode,
	onToggleBausteinLayout,
}) => {
	const can = !!editor && !disabled;
	const isA = (name, attrs) => !!editor && editor.isActive(name, attrs);
	const chain = () => editor.chain().focus();
	const inTable = isA("table");
	const inIf = isA("hvIf");
	const insertOp = (txt) => chain().insertContent(txt).run();
	const OPS = [
		["=", " == ", "ist gleich"],
		["≠", " != ", "ist ungleich"],
		[">", " > ", "größer als"],
		["<", " < ", "kleiner als"],
		["und", " and ", "und"],
		["oder", " or ", "oder"],
		["nicht", "not ", "nicht / negieren"],
		["enthält", " in ", "enthält / in"],
	];
	const blockValue = isA("heading", { level: 1 })
		? "Überschrift 1"
		: isA("heading", { level: 2 })
			? "Überschrift 2"
			: isA("heading", { level: 3 })
				? "Überschrift 3"
				: "Fließtext";
	return (
		<div className="editor-toolbar">
			<div className="tool-group">
				<select
					className="block-style-select"
					value={blockValue}
					disabled={!can}
					onMouseDown={(e) => e.stopPropagation()}
					onChange={(e) => {
						const v = e.target.value;
						if (v === "Fließtext") chain().setParagraph().run();
						else {
							const level = Number(v.slice(-1));
							chain().toggleHeading({ level }).run();
						}
					}}
				>
					<option>Fließtext</option>
					<option>Überschrift 1</option>
					<option>Überschrift 2</option>
					<option>Überschrift 3</option>
				</select>
				<select
					className="block-style-select"
					title="Schriftgröße (Punkt — entspricht dem PDF)"
					value={(editor && editor.getAttributes("textStyle").fontSize) || ""}
					disabled={!can}
					onMouseDown={(e) => e.stopPropagation()}
					onChange={(e) => {
						const v = e.target.value;
						if (v) chain().setFontSize(v).run();
						else chain().unsetFontSize().run();
					}}
				>
					<option value="">Größe</option>
					<option value="8pt">8</option>
					<option value="9pt">9</option>
					<option value="10pt">10</option>
					<option value="11pt">11</option>
					<option value="12pt">12</option>
					<option value="14pt">14</option>
					<option value="16pt">16</option>
					<option value="18pt">18</option>
					<option value="20pt">20</option>
					<option value="24pt">24</option>
				</select>
				<select
					className="block-style-select"
					title="Zeilenabstand"
					value={
						(editor &&
							(editor.getAttributes("paragraph").lineHeight ||
								editor.getAttributes("heading").lineHeight)) ||
						""
					}
					disabled={!can}
					onMouseDown={(e) => e.stopPropagation()}
					onChange={(e) => {
						const v = e.target.value;
						if (v) chain().setLineHeight(v).run();
						else chain().unsetLineHeight().run();
					}}
				>
					<option value="">Abstand</option>
					<option value="1">1.0</option>
					<option value="1.15">1.15</option>
					<option value="1.35">1.35</option>
					<option value="1.5">1.5</option>
					<option value="2">2.0</option>
				</select>
			</div>
			<div className="tool-group">
				<TBtn title="Fett" active={isA("bold")} disabled={!can} on={() => chain().toggleBold().run()}>
					<Icon name="bold" />
				</TBtn>
				<TBtn title="Kursiv" active={isA("italic")} disabled={!can} on={() => chain().toggleItalic().run()}>
					<Icon name="italic" />
				</TBtn>
				<TBtn title="Unterstrichen" active={isA("underline")} disabled={!can} on={() => chain().toggleUnderline().run()}>
					<Icon name="underline" />
				</TBtn>
				<TBtn title="Hochgestellt" active={isA("superscript")} disabled={!can} on={() => chain().toggleSuperscript().run()}>
					<span style={{ fontSize: 12 }}>x²</span>
				</TBtn>
			</div>
			<div className="tool-group">
				<TBtn title="Links" active={isA({ textAlign: "left" })} disabled={!can} on={() => chain().setTextAlign("left").run()}>
					<Icon name="align-left" />
				</TBtn>
				<TBtn title="Zentriert" active={isA({ textAlign: "center" })} disabled={!can} on={() => chain().setTextAlign("center").run()}>
					<Icon name="align-center" />
				</TBtn>
				<TBtn title="Rechts" active={isA({ textAlign: "right" })} disabled={!can} on={() => chain().setTextAlign("right").run()}>
					<Icon name="align-right" />
				</TBtn>
				<TBtn title="Blocksatz" active={isA({ textAlign: "justify" })} disabled={!can} on={() => chain().setTextAlign("justify").run()}>
					<Icon name="align-justify" />
				</TBtn>
			</div>
			<div className="tool-group">
				<TBtn title="Liste" active={isA("bulletList")} disabled={!can} on={() => chain().toggleBulletList().run()}>
					<Icon name="list" />
				</TBtn>
				<TBtn title="Nummerierte Liste" active={isA("orderedList")} disabled={!can} on={() => chain().toggleOrderedList().run()}>
					<Icon name="list-ordered" />
				</TBtn>
				<TBtn
					title="Link"
					active={isA("link")}
					disabled={!can}
					on={() => {
						const prev = editor.getAttributes("link").href || "";
						const url = prompt("Link-URL:", prev);
						if (url === null) return;
						if (url === "") chain().unsetLink().run();
						else chain().setLink({ href: url }).run();
					}}
				>
					<Icon name="link" />
				</TBtn>
			</div>
			<div className="tool-group">
				<label className="tool-btn" title="Textfarbe" style={{ position: "relative" }}>
					<Icon name="palette" />
					<input
						type="color"
						disabled={!can}
						onChange={(e) => chain().setColor(e.target.value).run()}
						style={{ position: "absolute", inset: 0, opacity: 0, cursor: "pointer", width: "100%", height: "100%" }}
					/>
				</label>
				<TBtn title="Hervorheben" active={isA("highlight")} disabled={!can} on={() => chain().toggleHighlight({ color: "#fff2a8" }).run()}>
					<Icon name="highlight" />
				</TBtn>
			</div>
			<div className="tool-group">
				<TBtn title="Tabelle einfügen (2×2) — bearbeiten über das Menü an der Tabelle" disabled={!can} on={() => chain().insertTable({ rows: 2, cols: 2, withHeaderRow: false }).run()}>
					<Icon name="table" />
				</TBtn>
				<TBtn title="Bild einfügen" disabled={!can} on={onImage}>
					<Icon name="image" />
				</TBtn>
				<TBtn
					title={showGrid ? "Tabellen-Hilfslinien ausblenden" : "Tabellen-Hilfslinien einblenden"}
					active={!showGrid}
					on={onToggleGrid}
				>
					<Icon name="grid" />
				</TBtn>
				{inTable && (
					<TBtn
						title="Diese Zeile als Schleife wiederholen ({% for %})"
						active={isA("tableRow", {}) && !!editor.getAttributes("tableRow").loopExpr}
						disabled={!can}
						on={() => {
							const cur = editor.getAttributes("tableRow").loopExpr || "";
							const expr = prompt(
								"Schleifen-Ausdruck (z. B. row in payments) — leer = Schleife entfernen:",
								cur
							);
							if (expr === null) return;
							chain().setRowLoopExpr(expr.trim() || null).run();
						}}
					>
						<Icon name="repeat" />
					</TBtn>
				)}
			</div>
			{inIf && (
				<div className="tool-group op-group" title="Operatoren für die Bedingung">
					{OPS.map(([label, txt, tip]) => (
						<button
							key={label}
							className="tool-btn op-btn"
							title={tip}
							disabled={!can}
							onMouseDown={(e) => e.preventDefault()}
							onClick={() => insertOp(txt)}
						>
							{label}
						</button>
					))}
				</div>
			)}
			<div className="toolbar-spacer" />
			<div className="tool-group" style={{ borderRight: "none" }}>
				<button
					className={`tool-btn tool-btn-wide ${bausteinLayoutMode ? "primary-tool" : ""}`}
					onClick={onToggleBausteinLayout}
					title={bausteinLayoutMode ? "Bausteine als Chips anzeigen" : "Bausteine gerendert im Layout anzeigen"}
					disabled={!editor}
				>
					<Icon name="block" size={14} />
					<span>Layoutmodus</span>
				</button>
				<button className="tool-btn tool-btn-wide primary-tool" onClick={onInsert} title="Kontrollfluss einfügen (if / for / set …)" disabled={!can}>
					<Icon name="branch" size={14} />
					<span>Kontrollfluss</span>
				</button>
			</div>
		</div>
	);
};

// Schwebe-Menü für Tabellen (offizielles BubbleMenu-Addon + die in der Table-Extension
// bereits vorhandenen Befehle). Erscheint, sobald der Cursor in einer Tabelle steht.
const TableBubbleMenu = ({ editor }) => {
	if (!editor) return null;
	const run = (fn) => () => fn(editor.chain().focus()).run();
	return (
		<BubbleMenu
			editor={editor}
			pluginKey="hvTableBubble"
			// WICHTIG: @tiptap/react friert shouldShow beim ersten Mount ein (das Plugin-
			// useEffect hängt nicht an shouldShow). Beim Start ist die Vorlage noch leer
			// (canWrite=false), ein eingefrorenes `editable`-Prop bliebe also dauerhaft
			// false und das Menü erschiene nie. Daher live `editor.isEditable` lesen
			// (wird via editor.setEditable(editable) aktuell gehalten).
			shouldShow={({ editor }) => editor.isEditable && editor.isActive("table")}
			tippyOptions={{ placement: "top", maxWidth: "none" }}
		>
			<div className="table-bubble">
				<button title="Spalte rechts einfügen" onClick={run((c) => c.addColumnAfter())}>Sp ＋</button>
				<button title="Spalte löschen" onClick={run((c) => c.deleteColumn())}>Sp －</button>
				<span className="tb-sep" />
				<button title="Zeile darunter einfügen" onClick={run((c) => c.addRowAfter())}>Zeile ＋</button>
				<button title="Zeile löschen" onClick={run((c) => c.deleteRow())}>Zeile －</button>
				<span className="tb-sep" />
				<button title="Kopfzeile an/aus" onClick={run((c) => c.toggleHeaderRow())}>Kopf</button>
				<span className="tb-sep" />
				<button
					title="Rahmen dieser Tabelle im PDF drucken (an/aus)"
					className={editor.getAttributes("table").borders ? "is-active" : ""}
					onClick={() =>
						editor
							.chain()
							.focus()
							.updateAttributes("table", { borders: !editor.getAttributes("table").borders })
							.run()
					}
				>
					Rahmen
				</button>
				<span className="tb-sep" />
				<button className="tb-danger" title="Tabelle löschen" onClick={run((c) => c.deleteTable())}>
					Tabelle ✕
				</button>
			</div>
		</BubbleMenu>
	);
};

// =========================
// Editor (TipTap)
// =========================
export const Editor = ({
	template,
	recipient,
	loading,
	canWrite,
	contentRef,
	onDirty,
	onInsertItem,
	onPickRecipient,
	onMaximizePreview,
	onImageUpload,
	onSafety,
	bausteinLayoutMode,
	onToggleBausteinLayout,
	bausteinPreviews,
	placeholderPreviews,
	footerHtml,
	pageLayout,
}) => {
	const hasHtml = typeof template.htmlContent === "string";
	const [safety, setSafety] = useState(null); // null = sicher; sonst { lost, added }
	const editable = hasHtml && !!canWrite && !safety;
	const [revision, force] = useState(0);
	const fileInputRef = useRef(null);
	const editorRef = useRef(null);
	// Tabellen-Hilfslinien ein/aus (globale Ansichts-Präferenz, gemerkt).
	const [showGrid, setShowGrid] = useState(() => loadPref("tableGrid", true));
	useEffect(() => savePref("tableGrid", showGrid), [showGrid]);

	useEffect(() => {
		window.__hvBausteinLayoutMode = !!bausteinLayoutMode;
		window.__hvBausteinLayoutPreviews = bausteinPreviews || {};
		window.__hvPlaceholderLayoutPreviews = placeholderPreviews || {};
		window.dispatchEvent(new CustomEvent("hv-baustein-preview-refresh"));
	}, [bausteinLayoutMode, bausteinPreviews, placeholderPreviews]);

	const editor = useEditor({
		extensions: [...buildExtensions(), PageSimulationExtension],
		editable,
		content: "",
		editorProps: { attributes: { class: "tiptap-surface" } },
		onUpdate: ({ editor }) => {
			onDirty && onDirty();
			schedulePageSimulation(editor);
		},
		onSelectionUpdate: () => force((n) => n + 1),
		onTransaction: ({ editor, transaction }) => {
			if (transaction.getMeta(pageSimPluginKey)) return;
			force((n) => n + 1);
			schedulePageSimulation(editor);
		},
	});

	useEffect(() => {
		// NodeViews aktualisieren ihre Preview-DOM beim Refresh. Danach die
		// Footer-Zeile erneut aus dem Textfluss nehmen und die Seiten neu messen.
		schedulePageSimulation(editor);
	}, [editor, bausteinLayoutMode, bausteinPreviews, placeholderPreviews]);

	useEffect(() => {
		// Footer-HTML im window ablegen — schedulePageSimulation liest es von dort
		// (sonst müsste die Funktion durch die ganze Aufrufkette geschleift werden).
		window.__hvEditorFooterHtml = (bausteinLayoutMode && footerHtml) || "";
		window.__hvEditorPageLayout = pageLayout || {};
		schedulePageSimulation(editor);
	}, [bausteinLayoutMode, footerHtml, pageLayout, editor]);

	// Inhalt laden, wenn sich die Vorlage ändert (decorate -> TipTap). emitUpdate=false,
	// damit Laden nicht als dirty zählt.
	useEffect(() => {
		if (!editor) return;
		const original = template.htmlContent || "";
		editor.commands.setContent(decorateForTiptap(original), false);
		schedulePageSimulation(editor);
		// Token-Erhalt-Check: ging beim Laden ein Token verloren (nicht modellierbare Struktur)?
		const back = serializeToTokens(editor.getHTML());
		const d = diffTokens(original, back);
		const info = d.ok ? null : d;
		setSafety(info);
		onSafety && onSafety(info);
	}, [editor, template.id, template.htmlContent, onSafety]);

	useEffect(() => {
		if (editor) editor.setEditable(editable);
	}, [editor, editable]);

	useLayoutEffect(() => {
		const canvas = editorRef.current?.querySelector(".editor-canvas");
		if (!bausteinLayoutMode) {
			clearPageSimulationDecorations(editor);
			clearPageSimulation(editor?.view?.dom);
			clearPageSimulationLayout(canvas);
			return;
		}
		if (!canvas || !editor?.view?.dom) return;

		let raf = 0;
		const run = () => {
			raf = 0;
			applyPageSimulation(canvas, editor);
		};
		raf = window.requestAnimationFrame(run);

		const ro = new ResizeObserver(() => {
			if (raf) window.cancelAnimationFrame(raf);
			raf = window.requestAnimationFrame(run);
		});
		ro.observe(canvas);
		ro.observe(editor.view.dom);

		return () => {
			if (raf) window.cancelAnimationFrame(raf);
			ro.disconnect();
		};
	}, [editor, bausteinLayoutMode, revision, template.id, bausteinPreviews, placeholderPreviews]);

	useEffect(() => {
		const dom = editor?.view?.dom;
		if (!dom) return;
		const schedule = () => schedulePageSimulation(editor);
		dom.addEventListener("input", schedule, true);
		dom.addEventListener("keyup", schedule, true);
		dom.addEventListener("paste", schedule, true);
		return () => {
			dom.removeEventListener("input", schedule, true);
			dom.removeEventListener("keyup", schedule, true);
			dom.removeEventListener("paste", schedule, true);
		};
	}, [editor]);

	useEffect(() => {
		if (!editor || !bausteinLayoutMode) return;
		const run = () => {
			const canvas = editorRef.current?.querySelector(".editor-canvas.hv-baustein-layout");
			if (canvas) applyPageSimulation(canvas, editor);
		};
		run();
		const timer = window.setInterval(run, 250);
		return () => window.clearInterval(timer);
	}, [editor, bausteinLayoutMode]);

	// contentRef-API für App (getHtml/insertToken/editor).
	useEffect(() => {
		if (!editor || !contentRef) return;
		contentRef.current = {
			editor,
			getHtml: () => serializeToTokens(editor.getHTML()),
			insertToken: (raw) => insertRawToken(editor, raw),
		};
		return () => {
			if (contentRef.current && contentRef.current.editor === editor) contentRef.current = null;
		};
	}, [editor, contentRef]);

	// --- Kontrollfluss-Menü (Jinja-Snippets) ---
	const [slashOpen, setSlashOpen] = useState(false);
	const [slashPos, setSlashPos] = useState({ x: 0, y: 0 });
	const openSlash = useCallback(() => {
		const r = editorRef.current?.getBoundingClientRect();
		setSlashPos({ x: (r?.left || 100) + 60, y: (r?.top || 100) + 40 });
		setSlashOpen(true);
	}, []);
	const closeSlash = () => setSlashOpen(false);
	const onPick = (selection) => {
		if (selection.kind === "snippet") onInsertItem({ kind: "snippet", snippet: selection.item });
		closeSlash();
	};

	// --- Bild-Upload ---
	const handleImage = useCallback(() => {
		if (!editor) return;
		if (onImageUpload) fileInputRef.current?.click();
		else {
			const url = prompt("Bild-URL:");
			if (url) editor.chain().focus().setImage({ src: url }).run();
		}
	}, [editor, onImageUpload]);

	const onFileChosen = async (e) => {
		const file = e.target.files?.[0];
		e.target.value = "";
		if (!file || !editor) return;
		try {
			const url = await onImageUpload(file);
			if (url) editor.chain().focus().setImage({ src: url }).run();
		} catch (err) {
			alert("Bild-Upload fehlgeschlagen: " + ((err && err.message) || err));
		}
	};

	// Drag&Drop aus der Sidebar
	const [dragOver, setDragOver] = useState(false);
	const onDrop = (e) => {
		e.preventDefault();
		setDragOver(false);
		try {
			const data = JSON.parse(e.dataTransfer.getData("application/json"));
			if (data.kind === "placeholder") onInsertItem({ kind: "chip", token: data.token });
			else if (data.kind === "baustein") onInsertItem({ kind: "baustein", name: data.name });
		} catch (err) {
			/* ignore */
		}
	};

	return (
		<main className="center">
			<EditorToolbar
				editor={editor}
				disabled={!editable}
				onInsert={openSlash}
				onImage={handleImage}
				showGrid={showGrid}
				onToggleGrid={() => setShowGrid((v) => !v)}
				bausteinLayoutMode={bausteinLayoutMode}
				onToggleBausteinLayout={onToggleBausteinLayout}
			/>

			{safety && (
				<div className="editor-unsafe-banner">
					<Icon name="branch" size={14} />
					<span>
						Diese Vorlage enthält eine Struktur, die der Editor nicht verlustfrei abbilden kann
						{Object.keys(safety.lost || {}).length
							? ` (z. B. ${Object.keys(safety.lost).slice(0, 3).join(", ")})`
							: ""}
						. Read-only — bitte im klassischen Formular bearbeiten.
					</span>
				</div>
			)}

			<div className="editor-scroll" ref={editorRef}>
				<div
					className={`editor-canvas ${dragOver ? "drag-over" : ""} ${showGrid ? "" : "hv-no-grid"} ${bausteinLayoutMode ? "hv-baustein-layout" : ""}`}
					style={{
						"--hv-editor-page-width": `${pageLayout?.pageWidthMm || DEFAULT_PAGE_SIM.pageWidthMm}mm`,
						"--hv-editor-page-height": `${pageLayout?.pageHeightMm || DEFAULT_PAGE_SIM.pageMm}mm`,
						"--hv-editor-page-margin-top": `${pageLayout?.marginTopMm ?? DEFAULT_PAGE_SIM.marginTopMm}mm`,
						"--hv-editor-page-margin-right": `${pageLayout?.marginRightMm ?? DEFAULT_PAGE_SIM.marginRightMm}mm`,
						"--hv-editor-page-margin-bottom": `${pageLayout?.marginBottomMm ?? DEFAULT_PAGE_SIM.marginBottomMm}mm`,
						"--hv-editor-page-margin-left": `${pageLayout?.marginLeftMm ?? DEFAULT_PAGE_SIM.marginLeftMm}mm`,
					}}
					onDragOver={(e) => {
						e.preventDefault();
						setDragOver(true);
					}}
					onDragLeave={() => setDragOver(false)}
					onDrop={onDrop}
					onInput={() => schedulePageSimulation(editor)}
					onKeyUp={() => schedulePageSimulation(editor)}
					onMouseUp={() => schedulePageSimulation(editor)}
					onPaste={() => schedulePageSimulation(editor)}
				>
					{/* EditorContent und das BubbleMenu bleiben dauerhaft gemountet. Beim
					    Vorlagen-Laden (loading-Toggle) dürfen sie NICHT gegen einen Platzhalter
					    getauscht werden: TipTap/ProseMirror und tippy.js verwalten eigenes DOM
					    (das BubbleMenu hängt seinen Popper an document.body). Ein Unmount/Remount
					    während des React-Commits führt zu „removeChild: node is not a child"
					    und reißt die gesamte App ab. Der Ladezustand liegt daher nur als
					    Overlay über der Canvas, das BubbleMenu blendet sich via shouldShow aus. */}
					<EditorContent editor={editor} />
					{editor && <TableBubbleMenu editor={editor} />}
					{loading && <div className="editor-loading editor-loading-overlay">Vorlage wird geladen …</div>}
					{!loading && (
						<div className="editor-foot-hint">
							{editable
								? "Platzhalter & Bausteine sind ein Stück (als Ganzes löschbar). In Tabellen erscheint oben ein Menü (Spalte/Zeile +/−, Kopfzeile, löschen); ↻ wiederholt eine Zeile als {% for %}. Tabellen-Linien sind nur Bearbeitungshilfe – im PDF unsichtbar. Speichern oben rechts."
								: "Read-only (keine Schreibberechtigung)."}
						</div>
					)}
				</div>
			</div>

			<input ref={fileInputRef} type="file" accept="image/*" style={{ display: "none" }} onChange={onFileChosen} />

			<SlashMenu open={slashOpen} x={slashPos.x} y={slashPos.y} onClose={closeSlash} onPick={onPick} />
		</main>
	);
};
