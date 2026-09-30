"""Schreibgeschuetzte Jinja-Umgebung fuer Serienbrief Vorlagen und Textbausteine.

Frappes Sandbox verhindert nur Python-Interna (``__class__``, Importe). Ueber das
``frappe``-Objekt der Sandbox koennte eine Vorlage aber schreiben, loeschen, Mails
senden oder Netzwerkanfragen stellen, und zwar mit den Rechten dessen, der rendert
(``frappe.db.set_value`` sogar ohne jede Rechtepruefung). Briefe brauchen das nie.

Deshalb gilt beim Rendern von Serienbrief-Inhalten:

1. ``frappe`` ist eine Positivliste lesender Funktionen, ``frappe.db`` ebenso.
2. Globale Helfer mit Seiteneffekten (``run_script``, ``FrappeClient``) fehlen.
3. Die Sandbox ruft auf Dokumenten und auf der Datenbank nur lesende Methoden auf;
   ``save``, ``delete``, ``db_set``, ``submit`` usw. scheitern mit SecurityError.
"""

from __future__ import annotations

import frappe
from frappe.database.database import Database
from frappe.model.base_document import BaseDocument
from frappe.utils.jinja import get_jenv
from frappe.utils.safe_exec import SAFE_DATA_UTILS, NamespaceDict, read_sql
from jinja2.defaults import DEFAULT_FILTERS

_FRAPPE_READ = (
	"bold",
	"date_format",
	"format",
	"format_date",
	"format_value",
	"full_name",
	"get_all",
	"get_cached_doc",
	"get_doc",
	"get_fullname",
	"get_gravatar",
	"get_identicon",
	"get_last_doc",
	"get_list",
	"get_meta",
	"get_system_settings",
	"get_url",
	"lang",
	"number_format",
	"sanitize_html",
	"throw",
	"time_format",
	"user",
	"utils",
)
# SQL muss unabhaengig vom Frappe-Render-Modus auf read_sql zeigen.
_DB_READ = (
	"count",
	"escape",
	"exists",
	"get_all",
	"get_default",
	"get_list",
	"get_single_value",
	"get_value",
	"sql",
)
_GLOBAL_READ = (
	"_",
	"_dict",
	"abs",
	"all",
	"any",
	"as_json",
	"bool",
	"cycler",
	"dict",
	"enumerate",
	"frappe",
	"html2text",
	"isinstance",
	"issubclass",
	"joiner",
	"json",
	"lipsum",
	"list",
	"max",
	"min",
	"namespace",
	"orjson",
	"range",
	"scrub",
	"set",
	"sorted",
	"sum",
	"tuple",
)
# Nur gepruefte Methoden: Ein get_* kann ebenfalls schreiben (z.B. get_password).
_DOCUMENT_READ = frozenset(
	{
		"get",
		"get_formatted",
		"get_label_from_fieldname",
		"as_dict",
		"as_json",
		"is_new",
		"has_value",
		"get_kostenmatrix_rows",
		"get_immobilien_basis",
	}
)


class ReadonlyNamespace(NamespaceDict):
	"""Meldet verbotene Zugriffe verstaendlich statt als leeres Attribut."""

	def __init__(self, label, values):
		super().__init__(values)
		object.__setattr__(self, "_label", label)

	def __getattr__(self, key):
		if key.startswith("__") or key == "_label":
			raise AttributeError(key)
		if key in self:
			return self[key]
		frappe.throw(
			frappe._("Serienbrief-Vorlagen dürfen nur lesen: {0}.{1} ist nicht verfügbar.").format(
				object.__getattribute__(self, "_label"), key
			),
			frappe.PermissionError,
		)


def _readonly_frappe(safe_frappe) -> ReadonlyNamespace:
	values = {key: safe_frappe[key] for key in _FRAPPE_READ if key in safe_frappe}
	# Ausnahmeklassen (frappe.ValidationError …) sind reine Werte.
	values.update({key: value for key, value in safe_frappe.items() if key[:1].isupper()})
	db = {key: safe_frappe["db"][key] for key in _DB_READ if key in safe_frappe["db"]}
	db["sql"] = read_sql
	# image_to_base64 calls its argument's save() outside the sandbox.
	# No object/file conversion helpers are exposed to brief source.
	values["utils"] = ReadonlyNamespace(
		"frappe.utils",
		{
			key: value
			for key, value in SAFE_DATA_UTILS.items()
			if key not in {"image_to_base64", "pdf_to_base64", "get_thumbnail_base64_for_image"}
		},
	)
	values["db"] = ReadonlyNamespace("frappe.db", db)
	return ReadonlyNamespace("frappe", values)


def is_read_method(name: str) -> bool:
	return name in _DOCUMENT_READ


def _write_functions():
	from frappe.model.delete_doc import delete_doc
	from frappe.model.rename_doc import rename_doc

	return {
		delete_doc,
		rename_doc,
		frappe.delete_doc,
		frappe.rename_doc,
		frappe.sendmail,
		frappe.enqueue,
		frappe.render_template,
		frappe.get_print,
		frappe.attach_print,
		frappe.call,
		frappe.new_doc,
		frappe.copy_doc,
		frappe.log_error,
		frappe.publish_realtime,
	}


def readonly_jenv(**overlay):
	"""Wie ``get_jenv().overlay(**overlay)``, aber ohne schreibende Moeglichkeiten."""
	env = get_jenv().overlay(**overlay)
	# Kein geerbtes run_script, resolve_class, log oder ungepruefter Jinja-Hook.
	globals_ = {key: env.globals[key] for key in _GLOBAL_READ if key in env.globals}
	# Filter werden von Jinja direkt aufgerufen, ohne is_safe_callable.
	filters = dict(DEFAULT_FILTERS)
	for key in ("json", "len", "int", "str", "flt"):
		if key in env.filters:
			filters[key] = env.filters[key]
	env.filters = filters
	safe_frappe = globals_.get("frappe")
	if safe_frappe is not None:
		globals_["frappe"] = _readonly_frappe(safe_frappe)
	env.globals = globals_

	base_is_safe_callable = env.is_safe_callable
	write_functions = _write_functions()

	def is_safe_callable(obj) -> bool:
		if not base_is_safe_callable(obj):
			return False
		owner = getattr(obj, "__self__", None)
		name = getattr(obj, "__name__", "")
		if isinstance(owner, BaseDocument):
			return is_read_method(name)
		if isinstance(owner, Database):
			# Die rohe db.sql-Methode ist schreibfaehig. SQL ist nur ueber
			# die separat freigegebene read_sql-Funktion erlaubt.
			return name != "sql" and (name in _DB_READ or name == "get_values")
		try:
			return obj not in write_functions
		except TypeError:
			# Nicht hashbare Aufrufbare sind keine der bekannten Schreibfunktionen.
			return True

	env.is_safe_callable = is_safe_callable
	env.serienbrief_readonly_frappe = globals_.get("frappe")
	return env


def readonly_context(env, context: dict) -> dict:
	"""Ein uebergebenes ``frappe`` im Kontext darf die Positivliste nicht umgehen."""
	if "frappe" in context:
		context = dict(context)
		safe_frappe = env.serienbrief_readonly_frappe
		# Der interne Vorschau-Proxy darf nur seine geprueften Lese-Mocks
		# austauschen. Insbesondere bleibt sql immer read_sql.
		from mail_merge.mail_merge.doctype.serienbrief_vorlage.serienbrief_vorlage import (
			SplitPreviewFrappeProxy,
		)

		proxy = context["frappe"]
		if type(proxy) is SplitPreviewFrappeProxy:
			values = dict(safe_frappe)
			for key in ("get_doc", "get_cached_doc", "throw"):
				values[key] = getattr(proxy, key)
			db = dict(safe_frappe["db"])
			for key in ("get_all", "get_list", "get_value", "get_single_value", "exists", "count"):
				db[key] = getattr(proxy.db, key)
			values["db"] = ReadonlyNamespace("frappe.db", db)
			safe_frappe = ReadonlyNamespace("frappe", values)
		context["frappe"] = safe_frappe
	return context
