import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { beforeEach, afterEach, expect, it, vi } from 'vitest';
import { VersionUsagePanel } from './VersionUsagePanel.jsx';
import { loadTemplateVersionUsage } from '../api.js';
vi.mock('../api.js', () => ({ loadTemplateVersionUsage: vi.fn() }));
let root, container;
beforeEach(() => {
 vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);vi.clearAllMocks();
 container=document.createElement('div');document.body.appendChild(container);root=createRoot(container);
});
afterEach(async () => { await act(async () => root.unmount());container.remove();vi.unstubAllGlobals(); });
it('shows linked PDFs and runs, switches to the whole template, and paginates', async () => {
 loadTemplateVersionUsage.mockImplementation(async ({kind}) => ({
  items: [{ name: kind === 'documents' ? 'DOC' : 'RUN', title: kind === 'documents' ? 'Brief A' : 'Lauf A', url: '/desk/record', pdf_url: kind === 'documents' ? '/private/files/a.pdf' : null, durchlauf: kind === 'documents' ? 'RUN' : null, version_number: 3, status: 'Generiert' }],
  counts: { documents: 22, runs: 1 }, total: kind === 'documents' ? 22 : 1, has_more: kind === 'documents',
 }));
 await act(async () => root.render(<VersionUsagePanel template="T" version="V5" grouped/>));
 expect(container.textContent).toContain('zusammengefassten Zwischenstände');
 expect(container.querySelector('a[href="/private/files/a.pdf"]')).not.toBeNull();
 const button = text => [...container.querySelectorAll('button')].find(b => b.textContent.startsWith(text));
 await act(async () => button('Weiter').click());
 expect(loadTemplateVersionUsage).toHaveBeenLastCalledWith(expect.objectContaining({ offset: 20, version: 'V5' }));
 await act(async () => { const select = container.querySelector('select');select.value='template';select.dispatchEvent(new Event('change',{bubbles:true})); });
 expect(loadTemplateVersionUsage).toHaveBeenLastCalledWith(expect.objectContaining({ version: '', offset: 0 }));
 await act(async () => button('Durchläufe').click());
 expect(loadTemplateVersionUsage).toHaveBeenLastCalledWith(expect.objectContaining({ kind: 'runs' }));
 expect(container.textContent).toContain('Lauf A');
});
