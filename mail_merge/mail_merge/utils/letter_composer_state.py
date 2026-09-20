"""Input snapshots shared by composer and renderer."""

from __future__ import annotations

import hashlib
import json


def mapping(raw):
	try:
		value = json.loads(raw) if isinstance(raw, str) and raw else (raw or {})
	except (TypeError, ValueError):
		return {}
	return value if isinstance(value, dict) else {}


def input_fingerprint(doc):
	data = {
		"template": doc.get("vorlage"),
		"date": str(doc.get("date") or ""),
		"title": doc.get("title"),
		"doctype": doc.get("iteration_doctype"),
		"values": mapping(doc.get("variablen_werte")),
		"recipients": [
			[row.get("objekt"), row.get("iteration_doctype"), mapping(row.get("variablen_werte"))]
			for row in doc.get("iteration_objekte") or []
		],
	}
	return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()
