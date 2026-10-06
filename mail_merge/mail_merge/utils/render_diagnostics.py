"""Technical render diagnostics shared by the editor and agent APIs; no source or value dumps."""

import re

def exception_chain(exc):
	chain, seen = [], set()
	while exc is not None and id(exc) not in seen and len(chain) < 12:
		chain.append(exc)
		seen.add(id(exc))
		exc = exc.__cause__ or (None if exc.__suppress_context__ else exc.__context__)
	return chain


def technical_message(exc):
	"""Technical causes without arbitrary exception strings, values or source dumps."""
	from jinja2.exceptions import SecurityError, TemplateSyntaxError, UndefinedError

	if isinstance(exc, TemplateSyntaxError):
		# Jinja's parser diagnostic contains syntax/token names, not rendered data.
		return re.sub(r"\s+", " ", str(exc.message)).strip()[:300]
	if isinstance(exc, SecurityError):
		return "Jinja-Zugriff durch die Lesesandbox blockiert."
	if isinstance(exc, UndefinedError):
		if str(exc) == "Wert ist None":
			return "Ein Jinja-Ausdruck liefert None."
		return "Eine Jinja-Variable oder ein Attribut ist nicht definiert."
	if isinstance(exc, ZeroDivisionError):
		return "Division durch null."
	if isinstance(exc, TypeError):
		match = re.fullmatch(
			r"'([A-Za-z_][A-Za-z0-9_]*)' object is not (callable|iterable|subscriptable)", str(exc)
		)
		if match:
			operation = {
				"callable": "als Funktion aufgerufen",
				"iterable": "in einer Schleife verwendet",
				"subscriptable": "per Index angesprochen",
			}[match[2]]
			return f"Ein Wert vom Typ {match[1]} wird {operation}, unterstützt diesen Zugriff aber nicht."
		return "Unpassender Datentyp für die ausgeführte Operation."
	if isinstance(exc, RecursionError):
		return "Maximale Rekursionstiefe überschritten; zyklische Bausteinaufrufe prüfen."
	if isinstance(exc, TimeoutError) or type(exc).__name__ == "TimeoutError":
		return "Zeitlimit bei der Verarbeitung überschritten."
	if isinstance(exc, OSError):
		return "Betriebssystemfehler bei der Verarbeitung" + (
			f" (errno {exc.errno})." if exc.errno is not None else "."
		)
	if type(exc).__name__ in {"PdfReadError", "PdfStreamError"}:
		return "PDF-Daten konnten nicht gelesen werden."
	if isinstance(exc, ValueError):
		return "Ungültiger Wert bei der Verarbeitung."
	return f"Technischer Fehler vom Typ {type(exc).__name__}."


def render_diagnostic(exc, *, phase="render"):
	from jinja2.exceptions import TemplateSyntaxError

	chain = exception_chain(exc)
	root = chain[-1]
	diagnostic = {
		"phase": next(
			(
				e.serienbrief_render_phase
				for e in reversed(chain)
				if getattr(e, "serienbrief_render_phase", None)
			),
			phase,
		),
		"exception_type": type(root).__name__,
		"message": technical_message(root),
	}
	block = next(
		(e.serienbrief_render_block for e in reversed(chain) if getattr(e, "serienbrief_render_block", None)),
		None,
	)
	if block:
		diagnostic["baustein"] = block
	engine = next(
		(e.serienbrief_pdf_engine for e in reversed(chain) if getattr(e, "serienbrief_pdf_engine", None)),
		None,
	)
	if engine:
		diagnostic["pdf_engine"] = engine
	line = root.lineno if isinstance(root, TemplateSyntaxError) else None
	for cause in reversed(chain):
		tb = cause.__traceback__
		while tb is not None:
			if tb.tb_frame.f_code.co_filename == "<template>":
				line = tb.tb_lineno
			tb = tb.tb_next
		if line:
			break
	if isinstance(line, int) and line > 0:
		diagnostic.update(line=line, line_reference="jinja_processed")
	return diagnostic
