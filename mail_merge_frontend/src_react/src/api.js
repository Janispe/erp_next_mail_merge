// High-level Daten-API für den Editor. Eingebettet (im Frappe-iframe) gehen die
// Aufrufe über die postMessage-Bridge an echte Backend-Methoden; standalone
// (npm run dev) fallen sie auf die Mock-Daten aus data.js zurück.

import { rpc, isEmbedded } from "./bridge.js";
import {
	TEMPLATE_TREE,
	CURRENT_TEMPLATE,
	PLACEHOLDER_GROUPS,
	TEXT_BAUSTEINE,
	SAMPLE_RECIPIENTS,
} from "./data.js";

export const embedded = isEmbedded();

const VERSION_API = "mail_merge.mail_merge.doctype.serienbrief_vorlage.serienbrief_vorlage.";

// Bereits geoeffnete Desk-Seiten koennen noch einen alten iframe-RPC-Host im
// Speicher haben, obwohl das neue Editor-Bundle schon geladen wurde. Dann kennt
// die Host-Allowlist z. B. ``versions`` noch nicht. Da iframe und Desk bewusst
// auf derselben Origin laufen, duerfen die fest verdrahteten Versionsmethoden
// in diesem Fall direkt ueber frappe.call aufgerufen werden. Nach einem normalen
// Seiten-Reload bleibt der strengere RPC-Pfad der Regelfall.
async function versionRpc(action, method, params) {
	try {
		return await rpc(action, params);
	} catch (originalError) {
		try {
			const desk = window.parent && window.parent.frappe;
			if (desk?.call) {
				const response = await desk.call({ method: VERSION_API + method, args: params || {} });
				return response?.message;
			}
		} catch (fallbackError) {
			throw fallbackError;
		}
		throw originalError;
	}
}

// Vorlagen-Baum: { groups: [{key,label,count,templates:[{id,title,modified}]}], total }
export async function loadTree() {
	if (!embedded) {
		const total = TEMPLATE_TREE.reduce((n, c) => n + c.templates.length, 0);
		return { groups: TEMPLATE_TREE, total, mock: true };
	}
	const res = await rpc("tree");
	return { ...res, mock: false };
}

// Einzelne Vorlage. Eingebettet → echtes HTML aus der DB (als template.htmlContent).
// Standalone → die statische Demo-Vorlage (Block-Modell).
function toEditorTemplate(t) {
	return {
		id: t.id,
		title: t.title,
		kategorie: t.kategorie_label || t.kategorie || "",
		haupt_verteil_objekt: t.haupt_verteil_objekt || "",
		content_type: t.content_type,
		content_position: t.content_position,
		modified: t.modified,
		modified_by: t.modified_by,
		canWrite: !!t.can_write,
		htmlContent: t.html || "",
		bausteinPaths: t.baustein_pfade || {},
		bausteinValues: t.baustein_werte || {},
		bausteinKeys: t.baustein_keys || {},
		variables: t.variables || [],
		variableAssignments: t.variable_assignments || [],
		restoredFromVersion: t.restored_from_version || "",
		restoredFromNumber: t.restored_from_number || 0,
		blocks: [],
		mock: false,
	};
}

export async function loadTemplate(id) {
	if (!embedded) {
		return { ...CURRENT_TEMPLATE, mock: true };
	}
	const t = await rpc("template", { name: id });
	return toEditorTemplate(t);
}

// Vorlage duplizieren. Gibt { name, title } der neuen Kopie zurück.
export async function copyTemplate(id, newTitle) {
	if (!embedded) {
		return { name: `${id}-kopie`, title: newTitle || "Kopie", mock: true };
	}
	return await rpc("copy", { template: id, new_title: newTitle });
}

// Vorlage löschen. Gibt { name } der gelöschten Vorlage zurück.
export async function deleteTemplate(id) {
	if (!embedded) {
		return { name: id, mock: true };
	}
	return await rpc("delete", { template: id });
}

// Vollstaendige, unveraenderliche Vorlagen-Snapshots.
export async function loadTemplateVersions(id) {
	if (!embedded) {
		return {
			items: [
				{ name: "demo-v3", number: 3, label: "Freigegebener Stand", source: "Gespeichert", change_summary: "Inhalt, Variablen", protected: true, is_current: true, created: new Date().toISOString(), created_by: "Administrator" },
				{ name: "demo-v2", number: 2, label: "", source: "Gespeichert", change_summary: "Inhalt", protected: false, is_current: false, created: new Date(Date.now() - 86400000).toISOString(), created_by: "Administrator" },
				{ name: "demo-v1", number: 1, label: "Ausgangsstand", source: "Ausgangsstand", change_summary: "Ausgangsstand", protected: false, is_current: false, created: new Date(Date.now() - 172800000).toISOString(), created_by: "Administrator" },
			],
		};
	}
	return await versionRpc("versions", "get_editor_versions", { template: id });
}

export async function updateTemplateVersion(template, version, { label, protected: isProtected }) {
	if (!embedded) return { name: version, label: label || "", protected: !!isProtected, mock: true };
	return await versionRpc("version_update", "update_editor_version", {
		template,
		version,
		label,
		is_protected: isProtected ? 1 : 0,
	});
}

export async function deleteTemplateVersion(template, version) {
	if (!embedded) return { name: version, remaining: 2, mock: true };
	return await versionRpc("version_delete", "delete_editor_version", { template, version });
}

export async function loadTemplateVersionDraft(template, version) {
	if (!embedded) return { ...CURRENT_TEMPLATE, restoredFromVersion: version, restoredFromNumber: 1, mock: true };
	const result = await versionRpc("version_restore", "restore_editor_version", { template, version });
	return toEditorTemplate(result);
}

export async function renderTemplateVersionPreview({ template, version, iterationDoctype, recipientId, druckSchwarzWeiss }) {
	if (!embedded) return { pdf_base64: "", mode: "mock" };
	return await versionRpc("version_preview", "render_editor_version_preview", {
		template,
		version,
		iteration_doctype: iterationDoctype || "",
		iteration_objekt: recipientId || "",
		druck_schwarz_weiss: druckSchwarzWeiss ? 1 : 0,
	});
}

export async function compareTemplateVersion(template, version) {
	if (!embedded) {
		return {
			sections: ["Inhalt"],
			diff: [
				{ type: "same", text: "Der bisherige " },
				{ type: "removed", text: "Text" },
				{ type: "added", text: "aktualisierte Text" },
			],
			stats: { variables_before: 2, variables_after: 3, blocks_before: 1, blocks_after: 1 },
		};
	}
	return await versionRpc("version_compare", "compare_editor_version", { template, version });
}

// Neues "Serienbrief Durchlauf"-Formular im Desk öffnen (Vorlage vorausgewählt).
// Navigiert das Eltern-Desk weg vom Editor — kein Rückgabewert nötig.
export async function openDurchlauf({ vorlage, title, iterationDoctype }) {
	if (!embedded) {
		return { ok: true, mock: true };
	}
	return await rpc("new_durchlauf", { vorlage, title, iteration_doctype: iterationDoctype });
}

// Klassische Frappe-Form der Vorlage öffnen. Escape-Hatch für den geführten
// Mapping-Wizard und Spezialfälle (Mehrfach-Baustein-Mappings via Alt-Datenmodell).
// Navigiert das Eltern-Desk weg vom Editor — kein Rückgabewert nötig.
export async function openClassicForm({ vorlage }) {
	if (!embedded) {
		return { ok: true, mock: true };
	}
	return await rpc("open_classic_form", { vorlage });
}

// "Zurück zur Liste" — vom Editor zum neuen Vorlagen-Browser springen.
// Eingebettet als NAV_ACTION; standalone (npm run dev) no-op.
export async function openBrowser() {
	if (!embedded) {
		return { ok: true, mock: true };
	}
	return await rpc("open_browser", {});
}

// Editierten Inhalt zurück in die Vorlage speichern. Gibt { id, modified } zurück.
// bausteinPaths = Pro-Baustein Input-Pfad-Overrides (Doctype-Variablen).
// bausteinValues = Pro-Baustein Werte für Text-/Bool-Variablen (selbes Format).
// bausteinKeys = Pro-Baustein Output-Key (Serienbrief Vorlagenbaustein.baustein_key).
export async function saveTemplate(
	id,
	html,
	bausteinPaths,
	bausteinValues,
	bausteinKeys,
	variables,
	variableAssignments,
	title,
	restoredFromVersion,
	forceNewVersion = false,
) {
	if (!embedded) {
		return { id, title, modified: "gerade eben (Demo)", mock: true };
	}
	const params = {
		name: id,
		html,
		baustein_pfade: JSON.stringify(bausteinPaths || {}),
		baustein_werte: JSON.stringify(bausteinValues || {}),
		baustein_keys: JSON.stringify(bausteinKeys || {}),
		variables: JSON.stringify(variables || []),
		variable_assignments: JSON.stringify(variableAssignments || []),
	};
	if (title != null) params.title = title;
	if (restoredFromVersion) params.restored_from_version = restoredFromVersion;
	if (forceNewVersion) params.force_new_version = 1;
	return await rpc("save", params);
}

// Bausteine (Serienbrief Textbaustein) für die Bausteine-Sidebar.
export async function loadBausteine() {
	if (!embedded) {
		return {
			items: TEXT_BAUSTEINE.map((b) => ({
				name: b.name,
				title: b.name,
				description: b.desc || "",
				preview: (b.preview || "").replace(/\n+/g, " · "),
				inputs: b.inputs || [],
				outputs: b.outputs || [],
				standardpfade: b.standardpfade || [],
			})),
		};
	}
	// Embedded: rpc liefert items inkl. inputs/outputs/standardpfade.
	return await rpc("bausteine");
}

export async function loadEditorPrintFormatCss() {
	if (!embedded) return {
		print_format: "",
		css: "",
		page_layout: {
			pageWidthMm: 210,
			pageHeightMm: 297,
			marginTopMm: 20,
			marginRightMm: 20,
			marginBottomMm: 16,
			marginLeftMm: 25,
		},
	};
	return await rpc("editor_print_css", {});
}

// Gerendertes Page-Footer-HTML (mit Mock-Zahlungsdaten + Kategorienpfad) zum
// Einblenden im Editor-Layoutmodus pro Seite. Liefert {html, error}.
export async function loadEditorFooterHtml(templateName) {
	if (!embedded) return { html: "", error: "" };
	return await rpc("editor_footer", { template: templateName || "" });
}

// Voller Platzhalter-Baum (Parität zum alten Formular-Picker): Gruppen mit
// rekursivem Feld-Baum, abgeleitet aus dem Iterationsobjekt + Variablen + Referenzen.
export async function loadPlaceholderTree(name, mode = "standard") {
	if (!embedded) {
		// Mock: flache Gruppen in Baum-Form überführen
		const groups = PLACEHOLDER_GROUPS.map((g) => ({
			key: g.key,
			label: g.label,
			icon: g.icon,
			tree: g.items.map((it) => ({ label: it.label, token: it.token, type: "", children: [] })),
		}));
		return {
			groups: mode === "advanced" ? [] : groups,
			standard_count: PLACEHOLDER_GROUPS.reduce((total, group) => total + group.items.length, 0),
			advanced_count: PLACEHOLDER_GROUPS.reduce((total, group) => total + group.items.length, 0),
			disabled_count: 0,
		};
	}
	return await rpc("placeholder_tree", { name: name || "", mode });
}

// Zentrales Profil für die Platzhalterdarstellung im normalen Frappe-Formular
// öffnen. Die Konfiguration lebt bewusst im Mail-Merge-Modul, nicht am Ziel-DocType.
export async function openPlaceholderProfile(doctype) {
	if (!embedded || !doctype) return { ok: true, mock: true };
	// Der Editor und das Frappe-Desk laufen auf derselben Origin. Direkt über das
	// Eltern-Desk navigieren, damit der Button auch in bereits geöffneten Desk-
	// Sitzungen funktioniert, deren RPC-Host die neue Aktion noch nicht kennt.
	try {
		const desk = window.parent && window.parent.frappe;
		if (desk?.db?.exists && desk?.set_route && desk?.new_doc) {
			const exists = await desk.db.exists("Serienbrief Platzhalterprofil", doctype);
			if (exists) await desk.set_route("Form", "Serienbrief Platzhalterprofil", doctype);
			else await desk.new_doc("Serienbrief Platzhalterprofil", { ziel_doctype: doctype });
			return { ok: true };
		}
	} catch (_) {
		// Falls der direkte Desk-Zugriff in einer späteren Einbettung nicht möglich
		// ist, bleibt die strikt erlaubte RPC-Navigation als Fallback erhalten.
	}
	return await rpc("open_placeholder_profile", { doctype });
}

// Echte Zielobjekt (z. B. Mietverträge) für den Vorschau-Picker.
export async function loadRecipients(doctype, query) {
	if (!embedded) {
		return { items: SAMPLE_RECIPIENTS.map((r) => ({ id: r.id, label: r.label })), doctype: "Zielobjekt" };
	}
	return await rpc("recipients", { doctype: doctype || "", query: query || "" });
}

// Maximale Bildgröße fürs Frontend-Upload. Schutz vor 100+ MB-Bildern, die
// FileReader.readAsDataURL den UI-Thread blockieren lassen und durch Base64-
// Encoding noch ~33 % Memory-Overhead haben. Backend könnte zusätzlich limitieren.
const MAX_UPLOAD_BYTES = 10 * 1024 * 1024; // 10 MB

// Bild in den Frappe-File-Store hochladen, gibt die /files/…-URL zurück. Base64 nur im
// Transit; gespeichert wird die URL (kein Base64-Bloat in der Vorlage). Standalone → null
// (Editor fällt dann auf URL-Eingabe zurück).
export async function uploadImage(file, templateName) {
	if (!embedded) return null;
	if (file && file.size > MAX_UPLOAD_BYTES) {
		const mb = (file.size / 1024 / 1024).toFixed(1);
		throw new Error(`Bild ist ${mb} MB groß — max 10 MB erlaubt.`);
	}
	const dataUrl = await new Promise((resolve, reject) => {
		const r = new FileReader();
		r.onload = () => resolve(r.result);
		r.onerror = reject;
		r.readAsDataURL(file);
	});
	const base64 = String(dataUrl).split(",")[1] || "";
	const res = await rpc("upload_image", {
		filename: file.name,
		content_base64: base64,
		template: templateName || "",
	});
	return res && res.file_url;
}

// PDF-Vorschau rendern. Mit Zielobjekt → echte Daten (Durchlauf-Pfad, gespeicherte
// Vorlage); ohne → Split-Preview mit Beispielwerten. Gibt { pdf_base64, mode }.
export async function renderPreview({
	templateName,
	hauptVerteilObjekt,
	recipientId,
	html,
	variables,
	bausteinPaths,
	bausteinValues,
	bausteinKeys,
	previewValues,
	druckSchwarzWeiss,
}) {
	if (!embedded) return { pdf_base64: "", mode: "mock" };
	// Live-Vorschau: aktueller (ungespeicherter) Editor-Stand wird serverseitig in-memory
	// auf die Vorlage angewandt und gerendert.
	const params = { template: templateName };
	if (html != null) params.html = html;
	if (variables != null) params.variables = JSON.stringify(variables);
	if (bausteinPaths != null) params.baustein_pfade = JSON.stringify(bausteinPaths);
	if (bausteinValues != null) params.baustein_werte = JSON.stringify(bausteinValues);
	if (bausteinKeys != null) params.baustein_keys = JSON.stringify(bausteinKeys);
	// Transiente Vorschau-Werte für Eingabe-Variablen (nicht gespeichert).
	if (previewValues && Object.keys(previewValues).length) {
		params.preview_values = JSON.stringify(previewValues);
	}
	if (druckSchwarzWeiss) {
		params.druck_schwarz_weiss = 1;
	}
	if (recipientId && hauptVerteilObjekt) {
		params.iteration_doctype = hauptVerteilObjekt;
		params.iteration_objekt = recipientId;
	} else {
		params.split_preview = 1;
	}
	return await rpc("editor_preview", params);
}

// Gerenderte HTML-Snippets für die im Editor vorkommenden {{ baustein("…") }}.
// Wird nur für den Layoutmodus genutzt; gespeichert bleibt weiter der Roh-Token.
export async function renderBausteinPreviews({
	templateName,
	hauptVerteilObjekt,
	recipientId,
	html,
	variables,
	bausteinPaths,
	bausteinValues,
	bausteinKeys,
	previewValues,
}) {
	if (!embedded) return { items: {} };
	const params = { template: templateName };
	if (html != null) params.html = html;
	if (variables != null) params.variables = JSON.stringify(variables);
	if (bausteinPaths != null) params.baustein_pfade = JSON.stringify(bausteinPaths);
	if (bausteinValues != null) params.baustein_werte = JSON.stringify(bausteinValues);
	if (bausteinKeys != null) params.baustein_keys = JSON.stringify(bausteinKeys);
	if (previewValues && Object.keys(previewValues).length) {
		params.preview_values = JSON.stringify(previewValues);
	}
	if (recipientId && hauptVerteilObjekt) {
		params.iteration_doctype = hauptVerteilObjekt;
		params.iteration_objekt = recipientId;
	}
	return await rpc("baustein_previews", params);
}
