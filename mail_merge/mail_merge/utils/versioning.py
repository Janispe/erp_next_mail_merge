"""Gemeinsame Snapshot-Versionierung fuer Serienbrief Vorlagen und Textbausteine.

Jede Version ist ein unveraenderlicher, vollstaendiger JSON-Snapshot des
wiederherstellbaren Zustands. Unbenannte Speicherungen desselben Benutzers
innerhalb von 15 Minuten werden zu einem Arbeitsstand zusammengefasst; benannte,
geschuetzte, wiederhergestellte und explizit erzwungene Versionen nie.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, cstr, get_datetime, now_datetime

VERSION_SESSION_SECONDS = 15 * 60
CHILD_META_FIELDS = {
	"doctype", "name", "owner", "creation", "modified", "modified_by",
	"parent", "parentfield", "parenttype", "docstatus",
}


@dataclass(frozen=True)
class VersionSpec:
	doctype: str
	version_doctype: str
	# Data-Feld der Version, das auf das versionierte Dokument zeigt. Absichtlich kein
	# Link: die Historie soll das Loeschen des Dokuments nicht verhindern.
	owner_field: str
	scalar_fields: tuple[str, ...]
	child_fields: tuple[str, ...]
	change_sections: Callable[[Dict[str, Any] | None, Dict[str, Any]], List[str]]
	# Zusaetzliche, gehashte Snapshot-Schluessel (z. B. Pruefsumme einer PDF-Datei).
	extra_snapshot: Callable[[Any], Dict[str, Any]] | None = None
	# Zusaetzliche, NICHT gehashte Felder der Versionszeile (z. B. Baustein-Stueckliste).
	extra_version_fields: Callable[[Any], Dict[str, Any]] | None = None
	# Nach Anlage oder Auffrischung einer Version (z. B. Dateien festhalten).
	after_version_saved: Callable[[Any, Any, Dict[str, Any]], None] | None = None
	# Beim Anwenden eines Snapshots nicht zu uebernehmende Felder.
	restore_skip_fields: tuple[str, ...] = field(default_factory=tuple)
	# Nachtraeglich eingefuehrte Felder: nur gesetzt im Snapshot, damit bestehende
	# Staende ihre Pruefsumme behalten. Beim Wiederherstellen fehlend = leer.
	optional_scalar_fields: tuple[str, ...] = field(default_factory=tuple)
	non_live_sources: tuple[str, ...] = field(default_factory=tuple)


def version_doctype_available(spec: VersionSpec) -> bool:
	"""Beim ersten ``bench migrate`` kann der Python-Code vor dem DocType geladen sein."""
	try:
		return bool(frappe.db.table_exists(spec.version_doctype))
	except Exception:
		return False


def snapshot_child_row(row) -> Dict[str, Any]:
	data = row.as_dict() if hasattr(row, "as_dict") else dict(row or {})
	return {
		key: value
		for key, value in data.items()
		if key not in CHILD_META_FIELDS and not key.startswith("_")
	}


def build_snapshot(spec: VersionSpec, doc) -> Dict[str, Any]:
	"""Serialisiert den vollstaendigen, wiederherstellbaren Zustand."""
	snapshot: Dict[str, Any] = {"schema_version": 1, "doctype": spec.doctype}
	for fieldname in spec.scalar_fields:
		snapshot[fieldname] = doc.get(fieldname)
	for fieldname in spec.optional_scalar_fields:
		if doc.get(fieldname) not in (None, "", 0):
			snapshot[fieldname] = doc.get(fieldname)
	for fieldname in spec.child_fields:
		snapshot[fieldname] = [snapshot_child_row(row) for row in (doc.get(fieldname) or [])]
	if spec.extra_snapshot:
		snapshot.update(spec.extra_snapshot(doc) or {})
	return snapshot


def snapshot_json(snapshot: Dict[str, Any]) -> str:
	return json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def snapshot_hash(snapshot: Dict[str, Any]) -> str:
	return hashlib.sha256(snapshot_json(snapshot).encode("utf-8")).hexdigest()


def parse_snapshot(spec: VersionSpec, raw: str | Dict[str, Any] | None) -> Dict[str, Any]:
	data = frappe.parse_json(raw) if isinstance(raw, str) else raw
	if not isinstance(data, dict) or data.get("doctype") != spec.doctype:
		frappe.throw(_("Die gespeicherte Version ist ungueltig."))
	return data


def apply_snapshot(spec: VersionSpec, doc, snapshot: Dict[str, Any]) -> None:
	for fieldname in spec.scalar_fields:
		if fieldname in snapshot and fieldname not in spec.restore_skip_fields:
			doc.set(fieldname, snapshot.get(fieldname))
	for fieldname in spec.optional_scalar_fields:
		if fieldname not in spec.restore_skip_fields:
			doc.set(fieldname, snapshot.get(fieldname))
	for fieldname in spec.child_fields:
		rows = snapshot.get(fieldname)
		if isinstance(rows, list) and fieldname not in spec.restore_skip_fields:
			doc.set(fieldname, [dict(row) for row in rows if isinstance(row, dict)])


def _live_filters(spec: VersionSpec, owner_name: str):
	filters = {spec.owner_field: owner_name}
	if spec.non_live_sources:
		filters["source"] = ["not in", list(spec.non_live_sources)]
	return filters


def latest_version(spec: VersionSpec, owner_name: str):
	rows = frappe.get_all(
		spec.version_doctype,
		filters=_live_filters(spec, owner_name),
		fields=[
			"name", "version_number", "version_label", "source", "is_protected",
			"restored_from", "content_hash", "snapshot", "creation", "modified", "owner",
			*(["sealed"] if _has_seal(spec) else []),
		],
		order_by="version_number desc",
		limit=1,
	)
	return rows[0] if rows else None


def can_coalesce(
	latest,
	*,
	source: str,
	label: str,
	restored_from: str,
	force: bool,
	now=None,
	user: str | None = None,
) -> bool:
	"""Unbenannte Kurzzeit-Speicherungen derselben Sitzung bilden einen Arbeitsstand."""
	if not latest or force or cstr(source).strip() != "Gespeichert":
		return False
	if cstr(label).strip() or cstr(restored_from).strip():
		return False
	if cstr(latest.source).strip() != "Gespeichert":
		return False
	if cstr(latest.version_label).strip() or cint(latest.is_protected) or cstr(latest.restored_from).strip():
		return False
	if cstr(latest.owner).strip() != cstr(user or frappe.session.user).strip():
		return False
	created = get_datetime(latest.creation)
	current = get_datetime(now or now_datetime())
	seconds = (current - created).total_seconds()
	return 0 <= seconds <= VERSION_SESSION_SECONDS


def _has_seal(spec: VersionSpec) -> bool:
	try:
		return frappe.get_meta(spec.version_doctype).has_field("sealed")
	except Exception:
		return False


def seal_version(spec: VersionSpec, version_name: str | None) -> None:
	"""Version festschreiben: sie wird nie mehr als Arbeitsstand aufgefrischt.

	Jede Stelle, die auf eine Version verweist (Festlegung, Durchlauf, Nachweis im
	Dokument, Stueckliste, Wiederherstellung, Vorschlag), schreibt sie fest. Sonst
	koennte eine spaetere Speicherung derselben Sitzung ihren Inhalt ersetzen.
	"""
	if version_name and version_doctype_available(spec) and _has_seal(spec):
		frappe.db.sql(
			f"update `tab{spec.version_doctype}` set sealed=1 where name=%s and sealed=0", version_name
		)


def _seal_if_unchanged(spec: VersionSpec, version_name: str, content_hash: str) -> bool:
	"""Festschreiben nur, wenn die Version noch genau diesen Inhalt hat (atomar)."""
	if not _has_seal(spec):
		return True
	frappe.db.sql(
		f"update `tab{spec.version_doctype}` set sealed=1 where name=%s and content_hash=%s",
		(version_name, content_hash),
	)
	# Sperrendes Lesen sieht den aktuellen Stand, nicht den Snapshot der Transaktion.
	row = frappe.db.sql(
		f"select sealed, content_hash from `tab{spec.version_doctype}` where name=%s for update",
		version_name,
	)
	return bool(row) and bool(cint(row[0][0])) and row[0][1] == content_hash


def _may_refresh(spec: VersionSpec, version_name: str) -> bool:
	"""Nur nicht festgeschriebene und gerade nicht gesperrte Arbeitsstaende auffrischen.

	SKIP LOCKED: Schreibt ein anderer Vorgang die Version gerade fest (etwa ein langer
	Hintergrund-Render), wartet das Speichern nicht, sondern legt eine neue Version an.
	"""
	if not _has_seal(spec):
		return True
	row = frappe.db.sql(
		f"select sealed from `tab{spec.version_doctype}` where name=%s for update skip locked",
		version_name,
	)
	return bool(row) and not cint(row[0][0])


def _refresh_session_version(spec: VersionSpec, doc, latest, snapshot: Dict[str, Any], content_hash: str):
	previous_rows = frappe.get_all(
		spec.version_doctype,
		filters={**_live_filters(spec, doc.name), "version_number": ["<", latest.version_number]},
		fields=["snapshot"],
		order_by="version_number desc",
		limit=1,
	)
	previous = parse_snapshot(spec, previous_rows[0].snapshot) if previous_rows else None
	version = frappe.get_doc(spec.version_doctype, latest.name)
	version.flags.allow_session_refresh = True
	version.change_summary = ", ".join(spec.change_sections(previous, snapshot))
	version.content_hash = content_hash
	version.snapshot = snapshot_json(snapshot)
	if spec.extra_version_fields:
		version.update(spec.extra_version_fields(doc) or {})
	version.save(ignore_permissions=True)
	if spec.after_version_saved:
		spec.after_version_saved(doc, version, snapshot)
	return version.name


def create_version(
	spec: VersionSpec,
	doc,
	*,
	source: str = "Gespeichert",
	label: str = "",
	restored_from: str = "",
	force: bool = False,
	based_on: str = "",
	seal: bool = False,
):
	"""Legt Meilensteine an und fasst schnelle, unbenannte Speicherungen zusammen.

	``seal``: die gelieferte Version wird zugleich festgeschrieben (siehe seal_version).
	"""
	if not doc or not doc.name or not version_doctype_available(spec):
		return None
	snapshot = build_snapshot(spec, doc)
	content_hash = snapshot_hash(snapshot)

	# Die Dokumentzeile sperren: parallele Speicherungen erhalten dadurch stabile,
	# fortlaufende Versionsnummern.
	frappe.db.sql(f"select name from `tab{spec.doctype}` where name=%s for update", doc.name)
	latest = latest_version(spec, doc.name)
	if latest and latest.content_hash == content_hash and not force:
		if not seal or _seal_if_unchanged(spec, latest.name, content_hash):
			return latest.name
	coalesce = (
		not seal
		and can_coalesce(latest, source=source, label=label, restored_from=restored_from, force=force)
		and _may_refresh(spec, latest.name)
	)
	if coalesce:
		return _refresh_session_version(spec, doc, latest, snapshot, content_hash)

	previous = parse_snapshot(spec, latest.snapshot) if latest else None
	if based_on:
		base = require_version(spec, based_on, doc.name)
		previous = parse_snapshot(spec, base.snapshot)
	# Vorschläge zählen für eindeutige Nummern, aber niemals als Live-Stand.
	last_number = frappe.db.get_value(
		spec.version_doctype, {spec.owner_field: doc.name}, "version_number", order_by="version_number desc"
	)
	values = {
		"doctype": spec.version_doctype,
		spec.owner_field: doc.name,
		"version_number": cint(last_number) + 1,
		"version_label": cstr(label).strip(),
		"source": cstr(source).strip() or "Gespeichert",
		"change_summary": ", ".join(spec.change_sections(previous, snapshot)),
		"restored_from": cstr(restored_from).strip() or None,
		"content_hash": content_hash,
		"snapshot": snapshot_json(snapshot),
	}
	if spec.non_live_sources:
		values["assistant_created"] = int(bool(doc.get("assistant_created")))
		values["based_on"] = based_on or None
		values["is_protected"] = int(source in spec.non_live_sources)
	if seal and _has_seal(spec):
		values["sealed"] = 1
	if spec.extra_version_fields:
		values.update(spec.extra_version_fields(doc) or {})
	version = frappe.get_doc(values)
	version.insert(ignore_permissions=True)
	# Ausgangspunkte von Vorschlaegen und Wiederherstellungen bleiben unveraenderlich.
	seal_version(spec, based_on)
	seal_version(spec, restored_from)
	if spec.after_version_saved:
		spec.after_version_saved(doc, version, snapshot)
	return version.name


def ensure_current_version(
	spec: VersionSpec, doc, *, source: str = "Systemänderung", seal: bool = False
) -> str | None:
	"""Version, die exakt dem aktuellen Stand entspricht; legt sie bei Drift an.

	Drift entsteht, wenn ein Stand am ``on_update`` vorbei geschrieben wurde
	(``db.set_value``, SQL-Skripte) oder die Historie vor dem Dokument fehlt.
	``seal``: wer die Version referenziert, schreibt sie fest. Aendert eine parallele
	Speicherung sie gerade, entsteht stattdessen eine neue, festgeschriebene Version.
	"""
	if not doc or not doc.name or not version_doctype_available(spec):
		return None
	current_hash = snapshot_hash(build_snapshot(spec, doc))
	latest = latest_version(spec, doc.name)
	if latest and latest.content_hash == current_hash:
		if not seal or latest.get("sealed") or _seal_if_unchanged(spec, latest.name, current_hash):
			return latest.name
	return create_version(spec, doc, source=source if latest else "Ausgangsstand", seal=seal)


def rename_versions(spec: VersionSpec, old: str, new: str) -> None:
	if version_doctype_available(spec):
		frappe.db.sql(
			f"update `tab{spec.version_doctype}` set `{spec.owner_field}`=%s where `{spec.owner_field}`=%s",
			(new, old),
		)


def require_version(spec: VersionSpec, version_name: str, owner_name: str):
	if not version_doctype_available(spec):
		frappe.throw(_("Die Versionshistorie ist noch nicht installiert. Bitte zuerst migrieren."))
	if not version_name or not frappe.db.exists(spec.version_doctype, version_name):
		frappe.throw(_("Die gewaehlte Version existiert nicht mehr."))
	version = frappe.get_doc(spec.version_doctype, version_name)
	if cstr(version.get(spec.owner_field)).strip() != owner_name:
		frappe.throw(_("Die gewaehlte Version gehoert nicht zu diesem Dokument."), frappe.PermissionError)
	return version


def version_metadata(version, *, current_hash: str = "", current_version: str = "") -> Dict[str, Any]:
	return {
		"name": version.name,
		"number": cint(version.version_number),
		"label": cstr(version.version_label or ""),
		"source": cstr(version.source or "Gespeichert"),
		"change_summary": cstr(version.change_summary or ""),
		"protected": bool(cint(version.is_protected)),
		"restored_from": cstr(version.restored_from or ""),
		"based_on": cstr(version.get("based_on") or ""),
		"history_group": cstr(version.get("history_group") or ""),
		"assistant_created": bool(version.get("assistant_created")) or cstr(version.source).startswith("KI-"),
		"is_proposal": version.source == "KI-Vorschlag",
		"sealed": bool(cint(version.get("sealed"))),
		"content_hash": cstr(version.content_hash or ""),
		"is_current": bool(
			current_hash
			and current_version
			and version.name == current_version
			and version.content_hash == current_hash
		),
		"created": version.creation.isoformat() if hasattr(version.creation, "isoformat") else cstr(version.creation),
		"created_by": cstr(version.owner or ""),
	}


def delete_block_reason(
	version,
	*,
	latest_name: str,
	first_name: str,
	referenced_names: set[str],
	evidence_names: set[str] = frozenset(),
) -> str:
	if version.name == latest_name:
		return _("Der aktuelle Stand kann nicht gelöscht werden.")
	if version.name == first_name or cstr(version.source).strip() == "Ausgangsstand":
		return _("Der Ausgangsstand kann nicht gelöscht werden.")
	if cint(version.is_protected):
		return _("Geschützte Versionen müssen vor dem Löschen entsperrt werden.")
	if version.get("history_group"):
		return _("Bitte zunächst die Zusammenfassung dieser Version auflösen.")
	if version.name in referenced_names:
		return _("Andere Versionen basieren auf diesem Stand oder verwenden ihn für eine Wiederherstellung.")
	if version.name in evidence_names:
		return _("Diese Version ist von einer Vorlage fixiert oder wurde für Serienbriefe verwendet und bleibt als Nachweis erhalten.")
	return ""


def rows_with_delete_metadata(rows, *, current_hash: str, current_version: str, evidence_names=frozenset(), non_live_sources=()):
	live = [row for row in rows if row.source not in non_live_sources]
	latest_name = live[0].name if live else ""
	first_name = live[-1].name if live else ""
	referenced_names = {cstr(row.get(key)).strip() for row in rows for key in ("restored_from", "based_on", "history_group") if row.get(key)}
	items = []
	for row in rows:
		item = version_metadata(row, current_hash=current_hash, current_version=current_version)
		reason = delete_block_reason(
			row,
			latest_name=latest_name,
			first_name=first_name,
			referenced_names=referenced_names,
			evidence_names=evidence_names,
		)
		item["can_delete"] = not bool(reason)
		item["delete_block_reason"] = reason
		items.append(item)
	return items


def list_versions(spec: VersionSpec, doc, *, evidence_names=frozenset()) -> Dict[str, Any]:
	"""Nummerierte Snapshot-Historie, neueste Version zuerst."""
	if not version_doctype_available(spec):
		return {"items": [], "current_hash": ""}
	current_hash = snapshot_hash(build_snapshot(spec, doc))
	rows = frappe.get_all(
		spec.version_doctype,
		filters={spec.owner_field: doc.name},
		fields=[
			"name", "version_number", "version_label", "source", "change_summary",
			"is_protected", "restored_from", "content_hash", "creation", "owner",
			*(["based_on", "assistant_created"] if spec.non_live_sources else []),
			*(["sealed"] if _has_seal(spec) else []),
			*(["history_group"] if frappe.get_meta(spec.version_doctype).has_field("history_group") else []),
		],
		order_by="version_number desc",
		limit_page_length=0,
	)
	live = [row for row in rows if row.source not in spec.non_live_sources]
	current_version = live[0].name if live and live[0].content_hash == current_hash else ""
	return {
		"items": rows_with_delete_metadata(
			rows,
			current_hash=current_hash,
			current_version=current_version,
			evidence_names=evidence_names,
			non_live_sources=spec.non_live_sources,
		),
		"current_hash": current_hash,
	}


def update_version_metadata(version, *, label=None, is_protected=None) -> None:
	"""Bearbeitet nur die kuratierten Metadaten; der Snapshot bleibt unveraenderlich."""
	if label is not None:
		version.version_label = cstr(label).strip()[:140]
	if is_protected is not None:
		version.is_protected = 1 if cint(is_protected) else 0
	version.save(ignore_permissions=True)


def delete_version(spec: VersionSpec, version, owner_name: str, *, evidence_names=frozenset()) -> Dict[str, Any]:
	"""Loescht nur entbehrliche historische Versionen; Nummern werden nie neu vergeben."""
	rows = frappe.get_all(
		spec.version_doctype,
		filters={spec.owner_field: owner_name},
		fields=["name", "source", "is_protected", "restored_from", *(["based_on"] if spec.non_live_sources else []), *(["history_group"] if frappe.get_meta(spec.version_doctype).has_field("history_group") else [])],
		order_by="version_number desc",
		limit_page_length=0,
	)
	live = [row for row in rows if row.source not in spec.non_live_sources]
	reason = delete_block_reason(
		version,
		latest_name=live[0].name if live else "",
		first_name=live[-1].name if live else "",
		referenced_names={cstr(row.get(key)).strip() for row in rows for key in ("restored_from", "based_on", "history_group") if row.get(key)},
		evidence_names=evidence_names,
	)
	if reason:
		frappe.throw(reason)
	frappe.delete_doc(spec.version_doctype, version.name, ignore_permissions=True)
	return {
		"name": version.name,
		"remaining": frappe.db.count(spec.version_doctype, {spec.owner_field: owner_name}),
	}


def word_diff(before: str, after: str, limit: int = 800) -> List[Dict[str, str]]:
	token_re = re.compile(r"\s+|[\wÀ-ɏ€§]+|[^\w\s]", flags=re.UNICODE)
	left = token_re.findall(before)
	right = token_re.findall(after)
	matcher = difflib.SequenceMatcher(a=left, b=right, autojunk=False)
	segments: List[Dict[str, str]] = []
	for tag, i1, i2, j1, j2 in matcher.get_opcodes():
		if tag in ("equal", "delete", "replace") and i1 != i2:
			segments.append({"type": "same" if tag == "equal" else "removed", "text": "".join(left[i1:i2])})
		if tag in ("insert", "replace") and j1 != j2:
			segments.append({"type": "added", "text": "".join(right[j1:j2])})
		if len(segments) >= limit:
			segments.append({"type": "same", "text": "\n… Vergleich gekuerzt …"})
			break
	return segments


class ImmutableVersionDocument(Document):
	"""Fester Meilenstein oder kurzfristig zusammengefasster, unbenannter Arbeitsstand."""

	_IMMUTABLE_FIELDS: tuple[str, ...] = ()

	def validate(self):
		if self.is_new() or not self.name:
			return
		self._keep_sealed()
		if self.flags.get("allow_session_refresh"):
			return
		stored = frappe.db.get_value(self.doctype, self.name, self._IMMUTABLE_FIELDS, as_dict=True)
		if not stored:
			return
		for fieldname in self._IMMUTABLE_FIELDS:
			if cstr(stored.get(fieldname)) != cstr(self.get(fieldname)):
				frappe.throw(
					_("Der Snapshot einer Version ist unveraenderlich. Nur Bezeichnung und Schutzstatus duerfen geaendert werden."),
					frappe.ValidationError,
				)

	def _keep_sealed(self):
		"""Festschreiben ist einseitig.

		Ein vor dem Festschreiben geladenes Dokument traegt noch ``sealed = 0`` und wuerde
		es beim Speichern (z. B. Bezeichnung aendern) zuruecksetzen. Massgeblich ist deshalb
		der gesperrt gelesene Datenbankstand.
		"""
		if not self.meta.has_field("sealed"):
			return
		if not cint(frappe.db.get_value(self.doctype, self.name, "sealed", for_update=True)):
			return
		if self.flags.get("allow_session_refresh"):
			frappe.throw(_("Eine festgeschriebene Version kann nicht mehr aufgefrischt werden."))
		self.sealed = 1

	def on_trash(self):
		if cint(self.is_protected):
			frappe.throw(_("Geschuetzte Versionen koennen nicht geloescht werden."))
