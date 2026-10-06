import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { VersionHistoryModal } from './VersionHistoryModal.jsx';
import { loadTemplateVersions, renderTemplateVersionPreview } from '../api.js';
vi.mock('../api.js', () => ({ loadTemplateVersions: vi.fn(), renderTemplateVersionPreview: vi.fn(), compareTemplateVersion: vi.fn(), deleteTemplateVersion: vi.fn(), updateTemplateVersion: vi.fn(), groupTemplateVersions: vi.fn(), ungroupTemplateVersions: vi.fn(), loadTemplateVersionUsage: vi.fn() }));
let root, container;
beforeEach(() => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true); vi.clearAllMocks();
  URL.createObjectURL = vi.fn(() => 'blob:preview'); URL.revokeObjectURL = vi.fn();
  container = document.createElement('div'); document.body.appendChild(container); root = createRoot(container);
});
afterEach(async () => { await act(async () => root.unmount()); container.remove(); vi.unstubAllGlobals(); });
it('shows open inputs instead of an error PDF, then renders transient values', async () => {
  const field = { field: 'stichtag', label: 'Stichtag', type: 'Datum', required: true, fillable: true };
  loadTemplateVersions.mockResolvedValue({ items: [{ name: 'V5', number: 5, source: 'KI-Vorschlag', is_proposal: true }] });
  renderTemplateVersionPreview.mockImplementation(async ({ previewValues }) => previewValues.stichtag ? { ready: true, pdf_base64: btoa('%PDF-test'), inputs: [field], errors: [] } : { ready: false, pdf_base64: 'error-pdf', inputs: [field], errors: [{ code: 'MISSING_INPUT', action: 'provide_inputs', issues: [field] }] });
  await act(async () => root.render(<VersionHistoryModal open template={{ id: 'T' }} />));
  expect(container.textContent).toContain('PDFs 0/1 bereit');
  expect(container.textContent).toContain('mit offenen Eingaben');
  expect(container.textContent).toContain('kein Fehler im Vorlagentext');
  expect(container.querySelector('iframe')).toBeNull();
  const input = container.querySelector('input[type=date]');
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, '2026-10-06');
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
  });
  await act(async () => container.querySelector('form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })));
  expect(renderTemplateVersionPreview).toHaveBeenLastCalledWith(expect.objectContaining({ version: 'V5', previewValues: { stichtag: '2026-10-06' } }));
  expect(container.textContent).toContain('PDFs 1/1 bereit');
  expect(container.querySelector('iframe').src).toBe('blob:preview');
});
it('keeps placeholder previews separate from checked PDFs and restores strict mode', async () => {
  const field = { field: 'stichtag', label: 'Stichtag', type: 'Datum', required: true, fillable: true };
  loadTemplateVersions.mockResolvedValue({ items: [{ name: 'V5', number: 5 }] });
  renderTemplateVersionPreview.mockImplementation(async ({ placeholderMode }) => placeholderMode ? { ready: true, placeholder_mode: true, pdf_base64: btoa('%PDF-layout'), inputs: [field], errors: [], warnings: [{ code: 'LAYOUT_ONLY' }] } : { ready: false, pdf_base64: '', inputs: [field], errors: [{ code: 'MISSING_INPUT', action: 'provide_inputs', issues: [field] }] });
  await act(async () => root.render(<VersionHistoryModal open template={{ id: 'T' }} />));
  const toggle = container.querySelector('.preview-placeholder-option input');
  await act(async () => toggle.click());
  expect(renderTemplateVersionPreview).toHaveBeenLastCalledWith(expect.objectContaining({ placeholderMode: true }));
  expect(container.textContent).toContain('Layoutvorschau mit Variablennamen');
  expect(container.textContent).toContain('PDFs 0/1 bereit');
  expect(container.textContent).toContain('1 mit Platzhaltern');
  expect(container.querySelector('iframe')).not.toBeNull();
  await act(async () => toggle.click());
  expect(container.querySelector('iframe')).toBeNull();
  expect(container.textContent).toContain('mit offenen Eingaben');
});
it('groups selected proposals, expands intermediates, and can undo the grouping', async () => {
 const api = await import('../api.js');
 const records = [4,3,2,1].map(number => ({ name: `V${number}`, number, based_on: number > 1 ? `V${number-1}` : '', is_proposal: number > 1, can_group: number > 1, group_members: [] }));
 loadTemplateVersions.mockImplementation(async () => ({ can_manage_history: true, items: records.map(v => ({ ...v })) }));
 renderTemplateVersionPreview.mockResolvedValue({ ready: true, pdf_base64: btoa('%PDF') });
 api.groupTemplateVersions.mockImplementation(async (template, selection) => {
  for (const row of records) { row.can_group = false; if (row.name === 'V4') row.group_members = ['V3','V2']; else if (['V3','V2'].includes(row.name)) row.history_group = 'V4'; }
  return { head: 'V4' };
 });
 api.ungroupTemplateVersions.mockImplementation(async () => {
  for (const row of records) { row.history_group = ''; row.group_members = []; row.can_group = row.number > 1; }
  return { head: 'V4' };
 });
 await act(async () => root.render(<VersionHistoryModal open template={{ id: 'T' }} />));
 const button = text => [...container.querySelectorAll('button')].find(b => b.textContent.trim() === text);
 await act(async () => button('Vorschläge zusammenfassen').click());
 for (const n of [2,3]) await act(async () => container.querySelector(`[aria-label="Version ${n} auswählen"]`).click());
 expect(container.querySelector('[aria-label="Version 1 auswählen"]').disabled).toBe(true);
 await act(async () => button('Auswahl zusammenfassen (3)').click());
 expect(api.groupTemplateVersions).toHaveBeenCalledWith('T', ['V4','V2','V3']);
 expect(container.querySelectorAll('.version-select-row')).toHaveLength(2);
 await act(async () => button('Zwischenstände einblenden').click());
 expect(container.querySelectorAll('.version-select-row')).toHaveLength(4);
 await act(async () => button('Zusammenfassung auflösen').click());
 expect(api.ungroupTemplateVersions).toHaveBeenCalledWith('T', 'V4');
 expect(container.querySelectorAll('.version-select-row')).toHaveLength(4);
});
