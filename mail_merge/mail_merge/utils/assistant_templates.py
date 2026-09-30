"""Validate assistant-authored source before storing it; render-time guards remain mandatory."""

import re
from urllib.parse import unquote

import frappe
import tinycss2
from bs4 import BeautifulSoup
from jinja2 import TemplateError, nodes

from mail_merge.mail_merge.utils.jinja_readonly import readonly_jenv

MAX_SOURCE_CHARS = 50000
ACTIVE_TAGS = {
	"script",
	"iframe",
	"object",
	"embed",
	"svg",
	"math",
	"base",
	"meta",
	"link",
	"form",
	"input",
	"button",
	"textarea",
	"select",
	"video",
	"audio",
	"source",
}


def validate_assistant_source(source):
	if not isinstance(source, str) or not source.strip() or len(source) > MAX_SOURCE_CHARS:
		frappe.throw("Vorlageninhalt muss 1 bis 50000 Zeichen enthalten.")
	# Placeholder tokens are resolved by the renderer before Jinja evaluation.
	compiled_source = re.sub(r"\{\{\$\s*[^{}]+?\s*\$\}\}", "PREVIEW", source)
	env = readonly_jenv()
	try:
		tree = env.parse(compiled_source)
	except TemplateError as exc:
		frappe.throw(f"Jinja-Syntaxfehler: {exc}")

	def frappe_path(node):
		if isinstance(node, nodes.Name) and node.name == "frappe":
			return []
		if isinstance(node, (nodes.Getattr, nodes.Getitem)):
			parent = frappe_path(node.node)
			if parent is not None:
				key = (
					node.attr
					if isinstance(node, nodes.Getattr)
					else (node.arg.value if isinstance(node.arg, nodes.Const) else None)
				)
				return [*parent, key]
		return None

	for node in tree.find_all(
		(
			nodes.Getitem,
			nodes.Getattr,
			nodes.Name,
			nodes.Filter,
			nodes.Call,
			nodes.Include,
			nodes.Import,
			nodes.FromImport,
			nodes.Extends,
			nodes.EvalContextModifier,
		)
	):
		if isinstance(
			node, (nodes.Include, nodes.Import, nodes.FromImport, nodes.Extends, nodes.EvalContextModifier)
		):
			frappe.throw("KI-Vorlagen dürfen keine externen Jinja-Templates laden.")
		if isinstance(node, nodes.Name) and node.name.startswith("_") and node.name != "_":
			frappe.throw("Interne Jinja-Namen sind für KI-Vorlagen gesperrt.")
		path = frappe_path(node)
		if path:
			value = env.globals["frappe"]
			for key in path:
				if not isinstance(value, dict) or not isinstance(key, str) or key not in value:
					frappe.throw("Dieser Frappe-Aufruf ist für Briefinhalte gesperrt.")
				value = value[key]
		if isinstance(node, nodes.Getattr) and node.attr in {
			"save",
			"insert",
			"delete",
			"db_set",
			"submit",
			"cancel",
			"run_method",
			"get_password",
		}:
			frappe.throw("Schreibende Dokumentaktionen sind für Briefinhalte gesperrt.")
		if isinstance(node, nodes.Getattr) and node.attr.startswith("_"):
			frappe.throw("Interne Attribute sind für KI-Vorlagen gesperrt.")
		if isinstance(node, nodes.Filter) and node.name in {"safe", "attr"}:
			frappe.throw(f"Filter {node.name} ist für KI-Vorlagen gesperrt.")
		if (
			isinstance(node, nodes.Call)
			and isinstance(node.node, nodes.Name)
			and node.node.name in {"baustein", "textbaustein"}
		):
			if (
				len(node.args) != 1
				or not isinstance(node.args[0], nodes.Const)
				or not isinstance(node.args[0].value, str)
				or node.kwargs
				or node.dyn_args
				or node.dyn_kwargs
			):
				frappe.throw('Bausteine müssen mit einem festen Namen eingebunden werden: baustein("Name").')

	return validate_passive_html(source)


def validate_passive_html(source):
	"""Validate rendered HTML too, including existing blocks referenced by an AI source."""

	def unsafe_css(css):
		def walk(tokens):
			for token in tokens:
				if token.type in {"url", "error"}:
					return True
				if token.type == "at-keyword" and token.value.lower() == "import":
					return True
				if token.type == "function" and token.lower_name in {"url", "expression"}:
					return True
				if walk(getattr(token, "arguments", []) or getattr(token, "content", [])):
					return True
			return False

		return walk(tinycss2.parse_component_value_list(css)) or bool(
			re.search(r"-moz-binding|\{[{%]", css, re.I)
		)

	# Static HTML plus escaped Jinja results avoids active browser content. Resource
	# URLs are deliberately bounded: Chromium must not call arbitrary RPC endpoints.
	soup = BeautifulSoup(source, "html.parser")
	for tag in soup.find_all(True):
		if tag.name.lower() in ACTIVE_TAGS:
			frappe.throw(f"Aktives HTML ist für KI-Vorlagen gesperrt: {tag.name}.")
		for key, value in tag.attrs.items():
			value = " ".join(value) if isinstance(value, list) else str(value)
			if key.lower().startswith("on") or key.lower() in {
				"srcdoc",
				"srcset",
				"background",
				"action",
				"formaction",
			}:
				frappe.throw(f"Aktives HTML-Attribut ist gesperrt: {key}.")
			if "{{" in value or "{%" in value or "{#" in value:
				frappe.throw("Jinja in HTML-Attributen ist für KI-Vorlagen gesperrt.")
			decoded = value
			for _ in range(3):
				decoded = unquote(decoded)
			if key.lower() == "src" and (".." in decoded or "\\" in decoded):
				frappe.throw("Ungültiger Ressourcenpfad.")
			if key.lower() == "src" and not re.fullmatch(
				r"/(?:private/)?files/[A-Za-z0-9_.%/-]+|/assets/[A-Za-z0-9_.%/-]+", value
			):
				frappe.throw("Bilder dürfen nur lokale Dateien oder Assets referenzieren.")
			if key.lower() == "href" and not re.match(r"^(https?://|mailto:|#)", value, re.I):
				frappe.throw("Links dürfen nur HTTP(S), mailto oder Anker verwenden.")
			if key.lower() == "style" and unsafe_css(value):
				frappe.throw("Nachladendes oder aktives CSS ist für KI-Vorlagen gesperrt.")
		if tag.name.lower() == "style" and unsafe_css(tag.get_text()):
			frappe.throw("Nachladendes, dynamisches oder aktives CSS ist für KI-Vorlagen gesperrt.")
	return source
