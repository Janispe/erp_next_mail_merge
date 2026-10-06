import unittest
from unittest.mock import patch
import frappe
from jinja2.exceptions import UndefinedError
from mail_merge.mail_merge.utils.preview_diagnostics import PreviewInputError, apply_preview_values, preview_error, require_preview_inputs
from mail_merge.mail_merge.doctype.serienbrief_vorlage import serienbrief_vorlage as api

class TestPreviewDiagnostics(unittest.TestCase):
 def doc(self):
  return frappe.get_doc({'doctype': 'Serienbrief Vorlage', 'name': 'Preview test', 'title': 'Preview test', 'template_mode': 'Jinja', 'standardtext': '<p>{{ anschrift }} {{ stichtag }}</p>', 'variables': [
   {'variable': 'anschrift', 'label': 'Wohnungsanschrift', 'variable_type': 'Text'},
   {'variable': 'stichtag', 'label': 'Stichtag', 'variable_type': 'Datum'},
   {'variable': 'zahl', 'variable_type': 'Zahl', 'optional': 1},
   {'variable': 'flag', 'variable_type': 'Bool', 'optional': 1},
  ]})
 def test_all_open_inputs(self):
  d=self.doc()
  with self.assertRaises(PreviewInputError) as caught: require_preview_inputs(d,{})
  result=preview_error(caught.exception,d)
  self.assertEqual(result['code'],'MISSING_INPUT')
  self.assertEqual([i['field'] for i in result['issues']],['anschrift','stichtag'])
 def test_false_zero_and_optional_are_valid(self):
  require_preview_inputs(self.doc(),{'anschrift':'Adresse','stichtag':'2026-10-06','flag':False,'zahl':0})
 def test_transient_values_and_types(self):
  d=self.doc(); apply_preview_values(d,{'anschrift':'Adresse','stichtag':'2026-10-06','zahl':0,'flag':False})
  values=frappe.parse_json(d.variablen_werte)
  self.assertIs(values['flag']['value'],False);self.assertEqual(values['zahl']['value'],0)
  for values in ({'unknown':'x'},{'stichtag':'morgen'},{'zahl':'0'},'{bad json'):
   with self.assertRaises(PreviewInputError): apply_preview_values(self.doc(),values)
 def test_undeclared_variable_is_template_error(self):
  result=preview_error(UndefinedError("'unbekannt' is undefined"),self.doc())
  self.assertEqual(result['code'],'UNDEFINED_VARIABLE');self.assertEqual(result['action'],'review_template')
 def test_missing_recipient_path_is_not_open_input(self):
  result=preview_error(frappe.ValidationError('Pfad <b>objekt.adresse</b> für Variable <b>anschrift</b> in der Vorlage Beispiel konnte nicht aufgelöst werden.'),self.doc())
  self.assertEqual(result['code'],'MISSING_DATA');self.assertEqual(result['action'],'check_recipient_data')
  self.assertEqual(result['issues'][0]['path'],'objekt.adresse')
 def test_invalid_field_is_template_error(self):
  result=preview_error(frappe.ValidationError('Feld unbekannt existiert nicht im DocType Mietvertrag'),self.doc())
  self.assertEqual(result['code'],'INVALID_TEMPLATE_FIELD')
 def test_input_failure_never_calls_pdf_renderer(self):
  with patch.object(api,'_require_template_preview_permission'), patch.object(api,'_render_through_serienbrief_dokument_print_format') as pdf:
   result=api.render_template_preview_pdf(template_doc=self.doc().as_dict(),split_preview=True)
  self.assertFalse(result['ready']);self.assertEqual(result['pdf_base64'],'');self.assertEqual(result['errors'][0]['code'],'MISSING_INPUT');pdf.assert_not_called()
 def test_pdf_failure_is_structured(self):
  d=self.doc();apply_preview_values(d,{'anschrift':'Adresse','stichtag':'2026-10-06'})
  with patch.object(api,'_require_template_preview_permission'),patch.object(api,'_build_split_preview_html',return_value='<p>Brief</p>'),patch.object(api,'_render_through_serienbrief_dokument_print_format',side_effect=RuntimeError('private values')):
   result=api.render_template_preview_pdf(template_doc=d.as_dict(),split_preview=True)
  self.assertFalse(result['ready']);self.assertEqual(result['errors'][0]['action'],'check_pdf_renderer');self.assertNotIn('private values',str(result))

class TestPlaceholderPreview(unittest.TestCase):
 def doc(self):
  d=TestPreviewDiagnostics().doc()
  d.html_content = '<p>{{ anschrift }}</p><p>{{ frappe.utils.formatdate(stichtag) }}</p>'
  d.content_type = 'HTML + Jinja'
  return d
 def test_typed_expressions_are_named_only_in_layout_mode(self):
  from mail_merge.mail_merge.utils.preview_placeholders import fill_preview_placeholders
  from mail_merge.mail_merge.doctype.serienbrief_durchlauf.serienbrief_durchlauf import _render_serienbrief_template
  d=self.doc();context={}
  fields=fill_preview_placeholders(d,context)
  self.assertEqual([f['field'] for f in fields],['anschrift','stichtag'])
  html=_render_serienbrief_template(d.html_content,context)
  self.assertIn('[anschrift]',html);self.assertIn('[stichtag]',html);self.assertNotIn('2000',html)
 def test_existing_values_and_data_paths_are_preserved(self):
  from mail_merge.mail_merge.utils.preview_placeholders import fill_preview_placeholders
  d=self.doc();d.variablen_werte=frappe.as_json({'anschrift':{'path':'objekt.adresse'}})
  context={'stichtag':'2026-10-06','zahl':0,'flag':False}
  self.assertEqual(fill_preview_placeholders(d,context),[])
  self.assertEqual(context['stichtag'],'2026-10-06');self.assertNotIn('anschrift',context)
 def test_unknown_variables_still_fail(self):
  from mail_merge.mail_merge.utils.preview_placeholders import fill_preview_placeholders
  from mail_merge.mail_merge.doctype.serienbrief_durchlauf.serienbrief_durchlauf import _render_serienbrief_template
  context={};fill_preview_placeholders(self.doc(),context)
  with self.assertRaises(frappe.ValidationError):_render_serienbrief_template('{{ unbekannt }}',context)
 def test_placeholder_pdf_has_warning_and_does_not_touch_source(self):
  d=self.doc();before=d.as_json()
  with patch.object(api,'_require_template_preview_permission'),patch.object(api,'_render_through_serienbrief_dokument_print_format',return_value=b'%PDF-layout') as pdf:
   result=api.render_template_preview_pdf(template_doc=d.as_dict(),split_preview=True,placeholder_mode=1)
  self.assertTrue(result['ready'],result.get('errors'));self.assertTrue(result['placeholder_mode'])
  self.assertEqual(result['warnings'][0]['code'],'LAYOUT_ONLY')
  self.assertEqual([f['field'] for f in result['placeholders']],['anschrift','stichtag'])
  self.assertIn('Layoutvorschau',pdf.call_args.args[0]);self.assertIn('[stichtag]',pdf.call_args.args[0])
  self.assertEqual(d.as_json(),before)

 def test_conditions_use_typed_samples_but_calculated_output_is_named(self):
  from mail_merge.mail_merge.utils.preview_placeholders import fill_preview_placeholders
  from mail_merge.mail_merge.doctype.serienbrief_durchlauf.serienbrief_durchlauf import _render_serienbrief_template
  d=self.doc()
  for row in d.variables:row.optional=0
  context={};fill_preview_placeholders(d,context)
  result=_render_serienbrief_template('{% if flag %}JA{% else %}NEIN{% endif %} {{ zahl * 2 }}',context)
  self.assertEqual(result,'NEIN [zahl]')
 def test_placeholders_never_use_cached_pdf(self):
  d=self.doc();d.preview_pdf_file='/files/old-preview.pdf'
  with patch.object(api,'_load_template_doc',return_value=d),patch.object(api,'_require_template_preview_permission'),patch.object(api,'read_file_url_bytes') as cached,patch.object(api,'_render_through_serienbrief_dokument_print_format',return_value=b'%PDF-layout'):
   result=api.render_template_preview_pdf(template=d.name,placeholder_mode=1)
  self.assertTrue(result['ready'],result['errors']);self.assertTrue(result['placeholder_mode']);cached.assert_not_called()
