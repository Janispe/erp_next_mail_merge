"""Generic input descriptions shared by the renderer and its clients.

Names are context paths. Context defaults, template variables and block input
paths all use the same stored value mapping; recipient values take precedence.
"""
from __future__ import annotations

import frappe
from frappe.utils import nowdate

SCALAR_TYPES = {"Text", "String", "Datum", "Bool", "Zahl"}


def context_fields(run=None):
	return [{"name": "datum", "label": "Datum", "type": "Datum", "default": str((run.get("date") if run else None) or nowdate()), "required": False, "description": "Datum im Render-Kontext", "path": "datum", "aliases": ["datum_iso"]}]


def input_fields(template, run=None):
	from mail_merge.mail_merge.doctype.serienbrief_durchlauf import serienbrief_durchlauf as core
	fields = {f["name"]: f for f in context_fields(run)}
	defaults = core._parse_variable_values(template.get("variablen_werte"))
	for row in template.get("variables") or []:
		key = frappe.scrub(row.variable)
		kind = row.variable_type or "Text"
		if kind not in SCALAR_TYPES:
			continue
		entry = defaults.get(key) or {}
		fields[key] = {"name": key, "label": row.label or row.variable, "type": kind,
			"default": entry.get("value", fields.get(key, {}).get("default")),
			"required": not bool(row.get("optional")), "description": row.get("beschreibung") or "", "path": entry.get("path") or key}
	# Follow the same declared block dependencies as the template renderer.
	queue = [(r.baustein, r) for r in template.get("textbausteine") or [] if r.baustein]
	queue += [(n, None) for n in core._extract_inline_block_names(core._get_template_template_source(template))]
	seen = set()
	inline_paths = core._parse_mapping(template.get("inline_baustein_pfade"))
	inline_values = core._parse_mapping(template.get("inline_baustein_werte"))
	while queue:
		name, block_row = queue.pop(0)
		if name in seen:
			continue
		seen.add(name)
		block = frappe.get_cached_doc("Serienbrief Textbaustein", name)
		paths = {**core._get_block_default_path_map(block, template.haupt_verteil_objekt), **core._parse_mapping(block_row.get("pfad_zuordnung") if block_row else None), **(inline_paths.get(name) or {})}
		values = core._parse_variable_values(block_row.get("variablen_werte") if block_row else None)
		for row in block.get("variables") or []:
			key = frappe.scrub(row.variable)
			kind = row.variable_type or "Text"
			if kind not in SCALAR_TYPES:
				continue
			entry = values.get(key) or {}
			path = entry.get("path") or paths.get(key) or paths.get(row.variable) or key
			if path in fields:
				continue
			value = (inline_values.get(name) or {}).get(key, entry.get("value"))
			fields[path] = {"name": path, "path": path, "label": row.label or row.variable, "type": kind,
				"default": value, "required": not bool(row.get("optional")), "description": row.get("beschreibung") or block.title or name}
		queue += [(n, None) for n in core._extract_inline_block_names(core._get_textbaustein_template_source(block))]
	return list(fields.values())
