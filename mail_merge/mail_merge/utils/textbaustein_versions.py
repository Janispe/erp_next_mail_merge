"""Versionshistorie der Serienbrief Textbausteine und Baustein-Stuecklisten.

Bausteine werden beim Rendern nicht an eine Version gebunden: eine Korrektur
wirkt sofort in allen Vorlagen. Festgehalten wird aber, welche Baustein-Versionen
eine Vorlagenversion bzw. ein erzeugtes Serienbrief Dokument verwendet hat
(Stueckliste), damit alte Staende nachvollziehbar und originalgetreu
reproduzierbar bleiben.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List

import frappe
from frappe import _
from frappe.utils import cint, cstr

from mail_merge.mail_merge.utils import versioning
from mail_merge.mail_merge.utils.serienbrief_pdf_form import read_file_url_bytes
from mail_merge.mail_merge.utils.textbaustein_loader import (
	TEXTBAUSTEIN,
	FixedTextbausteinVersionMissing,
	fixed_version_number,
	get_textbaustein,
	parse_fixed_versions,
)

VERSION_DOCTYPE = "Serienbrief Textbausteinversion"
_MAX_BLOCKS = 200

_SCALAR_FIELDS = (
	"title",
	"content_type",
	"render_position",
	"description",
	"text_content",
	"html_content",
	"jinja_content",
	"pdf_file",
	"pdf_pages",
	"pdf_flatten",
)
_CHILD_FIELDS = ("variables", "outputs", "standardpfade", "pdf_field_mappings")


def snapshot_content(snapshot: Dict[str, Any]) -> str:
	if cstr(snapshot.get("content_type")).strip() == "HTML + Jinja":
		return "\n".join(
			part
			for part in (cstr(snapshot.get("jinja_content") or ""), cstr(snapshot.get("html_content") or ""))
			if part.strip()
		)
	return cstr(snapshot.get("text_content") or "")


def change_sections(before: Dict[str, Any] | None, after: Dict[str, Any]) -> List[str]:
	if not before:
		return [_("Ausgangsstand")]
	sections: List[str] = []
	if snapshot_content(before) != snapshot_content(after):
		sections.append(_("Inhalt"))
	pdf_fields = ("pdf_file", "pdf_file_hash", "pdf_pages", "pdf_flatten", "pdf_field_mappings")
	if any(before.get(field) != after.get(field) for field in pdf_fields):
		sections.append(_("PDF-Formular"))
	if before.get("variables") != after.get("variables"):
		sections.append(_("Variablen"))
	if before.get("outputs") != after.get("outputs"):
		sections.append(_("Ausgaben"))
	if before.get("standardpfade") != after.get("standardpfade"):
		sections.append(_("Standardpfade"))
	if before.get("title") != after.get("title"):
		sections.append(_("Titel"))
	if any(before.get(field) != after.get(field) for field in ("content_type", "render_position", "description")):
		sections.append(_("Einstellungen"))
	return sections or [_("Keine inhaltliche Aenderung")]


def _file_content_hash(file_url: str) -> str:
	content_hash = frappe.db.get_value("File", {"file_url": file_url, "is_folder": 0}, "content_hash")
	if content_hash:
		return cstr(content_hash)
	try:
		return hashlib.md5(read_file_url_bytes(file_url)).hexdigest()
	except Exception:
		return ""


def _pdf_snapshot(doc) -> Dict[str, Any]:
	"""Die URL allein beweist nicht den Inhalt: die Datei-Pruefsumme wird mitgehasht."""
	file_url = cstr(doc.get("pdf_file") or "").strip()
	return {"pdf_file_hash": _file_content_hash(file_url) if file_url else ""}


def _pin_pdf_file(doc, version, snapshot: Dict[str, Any]) -> None:
	"""Haengt die PDF-Datei zusaetzlich an die Version.

	Frappe loescht eine Datei auf der Platte erst, wenn kein anderer File-Datensatz
	denselben Inhalt referenziert. Ersetzt jemand die PDF am Baustein, bleibt die
	alte dadurch fuer Vorschau und Wiederherstellung erhalten.
	"""
	file_url = cstr(snapshot.get("pdf_file") or "").strip()
	attached = frappe.get_all(
		"File",
		filters={"attached_to_doctype": VERSION_DOCTYPE, "attached_to_name": version.name},
		fields=["name", "file_url"],
	)
	for row in attached:
		# Aufgefrischter Arbeitsstand: nicht mehr referenzierte Vorgaenger-PDF freigeben.
		if row.file_url != file_url:
			frappe.delete_doc("File", row.name, ignore_permissions=True, force=True)
	if not file_url or file_url.startswith(("http://", "https://")):
		return
	if any(row.file_url == file_url for row in attached):
		return
	try:
		# Rohbytes statt file_url: nur so erkennt Frappe die Datei am Inhalts-Hash wieder und
		# legt einen zweiten Verweis auf dieselbe Datei an (eine file_url wird als Text gelesen).
		frappe.get_doc(
			{
				"doctype": "File",
				"file_name": file_url.rsplit("/", 1)[-1],
				"content": read_file_url_bytes(file_url),
				"is_private": 1 if file_url.startswith("/private/") else 0,
				"attached_to_doctype": VERSION_DOCTYPE,
				"attached_to_name": version.name,
			}
		).insert(ignore_permissions=True)
	except Exception:
		frappe.log_error(
			frappe.get_traceback(),
			f"Textbausteinversion {version.name}: PDF {file_url} konnte nicht festgehalten werden.",
		)


SPEC = versioning.VersionSpec(
	doctype=TEXTBAUSTEIN,
	version_doctype=VERSION_DOCTYPE,
	owner_field="textbaustein",
	scalar_fields=_SCALAR_FIELDS,
	child_fields=_CHILD_FIELDS,
	change_sections=change_sections,
	extra_snapshot=_pdf_snapshot,
	after_version_saved=_pin_pdf_file,
	# autoname = format:{title}: der Titel IST der Name und wird nicht per Wiederherstellung umbenannt.
	restore_skip_fields=("title",),
)


def create_textbaustein_version(doc, *, default_source: str = "Gespeichert"):
	return versioning.create_version(
		SPEC,
		doc,
		source=cstr(doc.flags.get("version_source") or default_source),
		label=cstr(doc.flags.get("version_label") or ""),
		restored_from=cstr(doc.flags.get("version_restored_from") or ""),
		force=bool(doc.flags.get("force_textbaustein_version")),
	)


def doc_from_snapshot(name: str, snapshot: Dict[str, Any]):
	"""Ungespeicherter Baustein mit historischem Stand, fuer Vorschau-Renderings."""
	values = {key: snapshot.get(key) for key in (*_SCALAR_FIELDS, *_CHILD_FIELDS) if key in snapshot}
	doc = frappe.get_doc({"doctype": TEXTBAUSTEIN, **values})
	doc.name = name
	return doc


def version_by_number(name: str, version_number: int):
	rows = frappe.get_all(
		VERSION_DOCTYPE,
		filters={"textbaustein": name, "version_number": cint(version_number)},
		fields=["name", "version_number", "content_hash", "snapshot"],
		limit=1,
	)
	return rows[0] if rows else None


def fixed_textbaustein_doc(name: str, version_number: int):
	"""Baustein im Stand einer von der Vorlage fixierten Version.

	Kein stiller Rueckfall auf den aktuellen Stand: wer fixiert, will genau diesen Text.
	"""
	version = version_by_number(name, version_number)
	if not version:
		frappe.throw(
			_("Textbaustein {0}: die fixierte Version {1} existiert nicht.").format(name, version_number),
			FixedTextbausteinVersionMissing,
		)
	return doc_from_snapshot(name, versioning.parse_snapshot(SPEC, version.snapshot))


def normalize_fixed_versions(template) -> None:
	"""Normalisiert ``baustein_versionen`` und prueft, dass jede Version existiert."""
	raw = template.get("baustein_versionen")
	if isinstance(raw, str) and raw.strip():
		try:
			data = json.loads(raw)
		except ValueError:
			frappe.throw(_("Fixierte Baustein-Versionen: ungültiges JSON."))
		if not isinstance(data, dict):
			frappe.throw(_("Fixierte Baustein-Versionen: erwartet wird {\"<Baustein>\": <Versionsnummer>}."))
	fixed = parse_fixed_versions(raw)
	for name, number in fixed.items():
		if not version_by_number(name, number):
			frappe.throw(_("Textbaustein {0}: Version {1} existiert nicht.").format(name, number))
	template.baustein_versionen = json.dumps(dict(sorted(fixed.items())), ensure_ascii=False) if fixed else None


def _row_value(row, key: str) -> str:
	value = row.get(key) if hasattr(row, "get") else getattr(row, key, None)
	return cstr(value or "").strip()


def collect_textbaustein_names(template) -> List[str]:
	"""Alle von einer Vorlage erreichbaren Bausteine, transitiv ueber Inline-Aufrufe.

	Erfasst werden Tabellen-Bausteine, ``{{ baustein("X") }}`` im Vorlageninhalt und
	Inline-Aufrufe in Bausteinen selbst. Dynamisch berechnete Namen sind statisch
	nicht erkennbar und fehlen deshalb.
	"""
	from mail_merge.mail_merge.doctype.serienbrief_durchlauf.serienbrief_durchlauf import (
		_extract_inline_block_names,
		_get_template_template_source,
		_get_textbaustein_template_source,
	)

	queue = [_row_value(row, "baustein") for row in (template.get("textbausteine") or [])]
	queue.extend(_extract_inline_block_names(_get_template_template_source(template)))
	names: List[str] = []
	seen: set[str] = set()
	while queue and len(seen) < _MAX_BLOCKS:
		name = cstr(queue.pop(0)).strip()
		if not name or name in seen:
			continue
		seen.add(name)
		try:
			# Mit Vorlage laden: verschachtelte Aufrufe folgen dem Inhalt der fixierten Version.
			block = get_textbaustein(name, template=template)
		except frappe.DoesNotExistError:
			continue
		names.append(name)
		queue.extend(_extract_inline_block_names(_get_textbaustein_template_source(block)))
	return names


def textbaustein_bill(template) -> List[Dict[str, Any]]:
	"""Stueckliste: welche Baustein-Version die Vorlage fuer jeden Baustein jetzt verwendet."""
	bill = []
	for name in collect_textbaustein_names(template):
		fixed_number = fixed_version_number(template, name)
		if fixed_number:
			version = version_by_number(name, fixed_number)
			if version:
				bill.append(
					{
						"baustein": name,
						"version": version.name,
						"version_number": version.version_number,
						"content_hash": version.content_hash,
						"fixiert": True,
					}
				)
			continue
		block = frappe.get_doc(TEXTBAUSTEIN, name)
		version_name = versioning.ensure_current_version(SPEC, block)
		if not version_name:
			continue
		number, content_hash = frappe.db.get_value(
			VERSION_DOCTYPE, version_name, ["version_number", "content_hash"]
		)
		bill.append(
			{
				"baustein": name,
				"version": version_name,
				"version_number": number,
				"content_hash": content_hash,
			}
		)
	return bill


def parse_bill(raw) -> List[Dict[str, Any]]:
	try:
		data = frappe.parse_json(raw) if isinstance(raw, str) else raw
	except Exception:
		return []
	return [row for row in (data or []) if isinstance(row, dict) and row.get("baustein")]


def pinned_docs_from_bill(bill) -> Dict[str, Any]:
	"""Historische Baustein-Staende einer Stueckliste; fehlende Versionen bleiben aktuell."""
	docs = {}
	for row in parse_bill(bill):
		raw = frappe.db.get_value(VERSION_DOCTYPE, cstr(row.get("version")), "snapshot")
		if not raw:
			continue
		docs[row["baustein"]] = doc_from_snapshot(row["baustein"], versioning.parse_snapshot(SPEC, raw))
	return docs


def versions_used_in_bills(name: str) -> set[str]:
	"""Baustein-Versionen, die Vorlagen fixieren oder auf die Vorlagenversionen bzw.
	erzeugte Dokumente verweisen."""
	used: set[str] = set()
	for raw in frappe.get_all(
		"Serienbrief Vorlage",
		filters={"baustein_versionen": ["like", f"%{json.dumps(name, ensure_ascii=False)}%"]},
		pluck="baustein_versionen",
	):
		number = parse_fixed_versions(raw).get(name)
		version = version_by_number(name, number) if number else None
		if version:
			used.add(version.name)
	needle = f'%"baustein":{json.dumps(name, ensure_ascii=False)}%'
	for doctype in ("Serienbrief Vorlagenversion", "Serienbrief Dokument"):
		if not frappe.get_meta(doctype).has_field("textbaustein_versionen"):
			continue
		for raw in frappe.get_all(
			doctype, filters={"textbaustein_versionen": ["like", needle]}, pluck="textbaustein_versionen"
		):
			used.update(cstr(row.get("version")) for row in parse_bill(raw) if row["baustein"] == name)
	used.discard("")
	return used


def bill_changes(bill) -> List[Dict[str, Any]]:
	"""Vergleicht eine Stueckliste mit dem aktuellen Stand der Bausteine."""
	changes = []
	for row in parse_bill(bill):
		# Fixierte Staende aendern sich nicht; ein Wechsel der Fixierung steht im Vorlagen-Snapshot.
		if row.get("fixiert"):
			continue
		name = row["baustein"]
		if not frappe.db.exists(TEXTBAUSTEIN, name):
			changes.append({**row, "status": "geloescht"})
			continue
		current_hash = versioning.snapshot_hash(
			versioning.build_snapshot(SPEC, frappe.get_doc(TEXTBAUSTEIN, name))
		)
		if current_hash != row.get("content_hash"):
			changes.append({**row, "status": "geaendert"})
	return changes


def textbaustein_usage(name: str) -> List[Dict[str, Any]]:
	"""Vorlagen, die den Baustein direkt oder ueber andere Bausteine verwenden."""
	from mail_merge.mail_merge.doctype.serienbrief_durchlauf.serienbrief_durchlauf import (
		_extract_inline_block_names,
		_get_template_template_source,
	)

	usage = []
	for template_name in frappe.get_all("Serienbrief Vorlage", pluck="name", order_by="name asc"):
		template = frappe.get_cached_doc("Serienbrief Vorlage", template_name)
		names = collect_textbaustein_names(template)
		if name not in names:
			continue
		direct = {_row_value(row, "baustein") for row in (template.get("textbausteine") or [])}
		direct.update(_extract_inline_block_names(_get_template_template_source(template)))
		usage.append(
			{
				"vorlage": template_name,
				"title": cstr(template.get("title") or template_name),
				"direkt": name in direct,
				# Fixierte Vorlagen sind von Aenderungen am Baustein nicht betroffen.
				"fixierte_version": fixed_version_number(template, name) or None,
			}
		)
	return usage


def render_version_refs(template) -> Dict[str, Any]:
	"""Felder fuer ein Serienbrief Dokument: mit welchen Staenden wurde gerendert."""
	from mail_merge.mail_merge.doctype.serienbrief_vorlage.serienbrief_vorlage import TEMPLATE_VERSION_SPEC

	try:
		template_doc = frappe.get_doc("Serienbrief Vorlage", template.name)
		return {
			"vorlagenversion": versioning.ensure_current_version(TEMPLATE_VERSION_SPEC, template_doc),
			"textbaustein_versionen": json.dumps(
				textbaustein_bill(template_doc), ensure_ascii=False, separators=(",", ":")
			),
		}
	except Exception:
		# Nachvollziehbarkeit darf das Erzeugen der Briefe nie verhindern.
		frappe.log_error(frappe.get_traceback(), "Serienbrief: Versionsstand nicht ermittelbar")
		return {}
