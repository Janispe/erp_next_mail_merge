"""Isolated contract tests for the real print helper; no site or PDF engine."""
import ast
from pathlib import Path
import re
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


class Flags(dict):
    __getattr__ = dict.get
    __setattr__ = dict.__setitem__


class TestPreviewPrintContract(unittest.TestCase):
    def test_named_in_memory_document_and_flag_restoration_on_print_failure(self):
        source = Path(__file__).parent / "mail_merge/doctype/serienbrief_vorlage/serienbrief_vorlage.py"
        tree = ast.parse(source.read_text())
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_render_through_serienbrief_dokument_print_format")
        for mock_mode in (False, True):
            with self.subTest(mock_mode=mock_mode):
                doc = SimpleNamespace(name=None, insert=Mock(side_effect=AssertionError("no insert")), save=Mock(side_effect=AssertionError("no save")))
                flags = Flags(hv_serienbrief_split_preview="original")
                def normal_print(doctype, name, **kw):
                    # Exact string operation required by pinned Frappe's filename path.
                    self.assertTrue(re.sub(r"[/\\%?#]", "_", kw["doc"].name))
                    self.assertIs(kw["doc"], doc)
                    self.assertEqual((doctype, name), ("Serienbrief Dokument", None))
                    self.assertEqual(kw["print_format"], "Serienbrief Dokument")
                    self.assertIs(kw["as_pdf"], True)
                    self.assertEqual(kw["pdf_options"], {"margin-top": "15mm"})
                    self.assertEqual(doc.html, '<div class="serienbrief-root"><div class="serienbrief-page"><p>synthetic</p></div></div>')
                    self.assertEqual((doc.vorlage, doc.docstatus), ("Synthetic template", 1))
                    self.assertEqual(flags.hv_serienbrief_split_preview, True if mock_mode else "original")
                    raise RuntimeError("synthetic print failure")
                printer = Mock(side_effect=normal_print)
                framework = SimpleNamespace(new_doc=Mock(return_value=doc), flags=flags, get_print=printer)
                namespace = {"frappe": framework, "_preview_pdf_options": lambda: {"margin-top": "15mm"}}
                exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), "exec"), namespace)
                with self.assertRaisesRegex(RuntimeError, "synthetic print failure"):
                    namespace[node.name]("<p>synthetic</p>", SimpleNamespace(name="Synthetic template"), docstatus=1, is_mock=mock_mode)
                framework.new_doc.assert_called_once_with("Serienbrief Dokument")
                printer.assert_called_once()
                doc.insert.assert_not_called()
                doc.save.assert_not_called()
                self.assertEqual(flags.hv_serienbrief_split_preview, "original")

    def test_core_filename_contract_rejects_unnamed_baseline(self):
        with self.assertRaises(TypeError):
            re.sub(r"[/\\%?#]", "_", None)
