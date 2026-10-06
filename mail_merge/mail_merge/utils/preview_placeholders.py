"""Opt-in layout previews; unresolved declared scalar inputs stay visibly named."""

from mail_merge.mail_merge.utils.preview_diagnostics import preview_inputs


def fill_preview_placeholders(doc, context):
	from mail_merge.mail_merge.doctype.serienbrief_durchlauf.serienbrief_durchlauf import _coerce_context_value

	fields = []
	for field in preview_inputs(doc):
		value = context.get(field['field'])
		if not field['required'] or not field['fillable'] or value is not None and value != '':
			continue
		kind = field['type']
		if kind not in {'Text', 'String', 'Datum', 'Zahl', 'Bool'}:
			continue
		# Conditions need typed samples. Output expressions are named separately,
		# so neither formatting nor arithmetic presents samples as actual data.
		sample = {'Datum': '2000-01-01', 'Zahl': 1, 'Bool': False}.get(kind, f"[{field['field']}]")
		context[field['field']] = _coerce_context_value(sample, kind)
		fields.append(field)
	context['_serienbrief_placeholder_fields'] = [field['field'] for field in fields]
	return fields


def placeholder_template(jenv, source, fields):
	"""Replace only output expressions in an ephemeral AST, preserving control flow.

	This intentionally checks layout, not the correctness of expressions that
	need missing inputs. The original source and version are never modified.
	"""
	from jinja2 import nodes
	from jinja2.visitor import NodeTransformer

	class NamedOutputs(NodeTransformer):
		def visit_Output(self, node, *args, **kwargs):
			for i, expression in enumerate(node.nodes):
				names = [expression] if isinstance(expression, nodes.Name) else []
				names += list(expression.find_all(nodes.Name))
				missing = sorted({name.name for name in names if name.ctx == 'load' and name.name in fields})
				if missing:
					node.nodes[i] = nodes.Const(' / '.join(f'[{name}]' for name in missing), lineno=expression.lineno)
			return node

	return jenv.from_string(NamedOutputs().visit(jenv.parse(source)))


def placeholder_notice():
	return {'code': 'LAYOUT_ONLY', 'message': 'Layoutvorschau mit Variablennamen. Bedingungen verwenden Beispielwerte; die Prüfung mit echten Eingaben steht noch aus.'}
