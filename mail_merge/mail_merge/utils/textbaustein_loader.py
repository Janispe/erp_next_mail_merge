"""Einziger Ladepfad des Renderers fuer Serienbrief Textbausteine.

Aufloesung in dieser Reihenfolge:

1. Fixierte Version: legt die Vorlage in ``baustein_versionen`` eine Versionsnummer
   fest, gilt diese fuer den Baustein ueberall in der Vorlage, auch verschachtelt.
   Fehlt die Version, ist das ein harter Fehler.
2. Historischer Stand innerhalb von ``pinned_textbausteine`` (z. B. die Vorschau
   einer alten Vorlagenversion). Die Bindung liegt auf ``frappe.local`` und wirkt
   deshalb nur im aktuellen Request/Thread.
3. Sonst der aktuelle Stand.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from functools import lru_cache

import frappe
from frappe.utils import cint, cstr

TEXTBAUSTEIN = "Serienbrief Textbaustein"
_PIN_ATTR = "mail_merge_pinned_textbausteine"


class FixedTextbausteinVersionMissing(frappe.ValidationError):
	pass


def parse_fixed_versions(raw) -> dict[str, int]:
	"""``baustein_versionen`` der Vorlage als {Baustein: Versionsnummer > 0}."""
	if isinstance(raw, str):
		return dict(_parse_fixed_versions_json(raw))
	if not isinstance(raw, dict):
		return {}
	return {
		cstr(name).strip(): cint(number)
		for name, number in raw.items()
		if cstr(name).strip() and cint(number) > 0
	}


@lru_cache(maxsize=256)
def _parse_fixed_versions_json(raw: str) -> tuple[tuple[str, int], ...]:
	# Wird pro Baustein-Zugriff gebraucht; der Rohtext ist ein guter Cache-Schluessel.
	if not raw.strip():
		return ()
	try:
		data = json.loads(raw)
	except ValueError:
		return ()
	return tuple(parse_fixed_versions(data).items()) if isinstance(data, dict) else ()


def fixed_version_number(template, name: str) -> int:
	"""Von der Vorlage fixierte Versionsnummer eines Bausteins, 0 = immer aktuell."""
	if not template:
		return 0
	return parse_fixed_versions(template.get("baustein_versionen")).get(name, 0)


def get_textbaustein(name: str, template=None):
	version_number = fixed_version_number(template, name)
	if version_number:
		return _get_fixed_textbaustein(name, version_number)
	pinned = getattr(frappe.local, _PIN_ATTR, None)
	if pinned and name in pinned:
		return pinned[name]
	return frappe.get_cached_doc(TEXTBAUSTEIN, name)


def _get_fixed_textbaustein(name: str, version_number: int):
	from mail_merge.mail_merge.utils.textbaustein_versions import fixed_textbaustein_doc

	# Snapshots sind unveraenderlich: je Request einmal laden genuegt.
	cache = getattr(frappe.local, "mail_merge_fixed_textbausteine", None)
	if cache is None:
		cache = {}
		frappe.local.mail_merge_fixed_textbausteine = cache
	key = (name, version_number)
	if key not in cache:
		cache[key] = fixed_textbaustein_doc(name, version_number)
	return cache[key]


@contextmanager
def pinned_textbausteine(docs_by_name: dict):
	previous = getattr(frappe.local, _PIN_ATTR, None)
	merged = dict(previous or {})
	merged.update(docs_by_name or {})
	setattr(frappe.local, _PIN_ATTR, merged)
	try:
		yield
	finally:
		setattr(frappe.local, _PIN_ATTR, previous)
