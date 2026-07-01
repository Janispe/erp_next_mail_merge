from __future__ import annotations

import unittest

from mail_merge.mail_merge.utils.jinja_source_sanitizer import (
	normalize_jinja_html_entities,
	sanitize_richtext_jinja_source,
)


class TestNormalizeJinjaHtmlEntities(unittest.TestCase):
	def test_unescapes_quotes_inside_jinja_tag(self):
		src = "{{ baustein(&quot;SalutationBlock&quot;) }}"
		self.assertEqual(normalize_jinja_html_entities(src), '{{ baustein("SalutationBlock") }}')

	def test_unescapes_nbsp_inside_jinja_tag(self):
		src = "{{\xa0baustein(&quot;X&quot;)\xa0}}"
		self.assertEqual(normalize_jinja_html_entities(src), '{{ baustein("X") }}')

	def test_does_not_change_html_outside_jinja(self):
		src = "A &amp; B {{ 1 + 1 }}"
		self.assertEqual(normalize_jinja_html_entities(src), src)


class TestSanitizeRichtextJinjaSource(unittest.TestCase):
	def test_unwraps_hv_quill_badges_before_normalizing(self):
		src = (
			'<p>Start '
			'<span class="hv-jinja-badge" data-hv-jinja-token="{{ baustein(&quot;X&quot;) }}" '
			'contenteditable="false" draggable="false">{{ baustein("X") }}</span>'
			" End</p>"
		)
		self.assertEqual(sanitize_richtext_jinja_source(src), '<p>Start {{ baustein("X") }} End</p>')

	def test_unwraps_nested_contenteditable_spans(self):
		src = (
			'<p>'
			'<span class="hv-placeholder-badge" data-hv-placeholder="{{ baustein(&quot;HeaderBlock&quot;) }}" '
			'contenteditable="false" draggable="false">\ufeff'
			'<span contenteditable="false">{{ baustein("HeaderBlock") }}</span>\ufeff'
			"</span>"
			"</p>"
		)
		self.assertEqual(sanitize_richtext_jinja_source(src), '{{ baustein("HeaderBlock") }}')

	def test_unwraps_placeholder_only_paragraphs(self):
		src = '<div class="ql-editor read-mode"><p>{{ baustein("HeaderBlock") }}<br></p><p>Text</p></div>'
		self.assertEqual(
			sanitize_richtext_jinja_source(src),
			'{{ baustein("HeaderBlock") }}<p>Text</p>',
		)
