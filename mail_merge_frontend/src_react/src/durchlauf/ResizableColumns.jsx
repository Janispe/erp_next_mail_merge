import React, { useState } from "react";
const clamp = n => Math.max(300, Math.min(620, n));
export function ResizableColumns({ children }) {
  const [width, setWidth] = useState(() => {
    try { const value = Number(localStorage.getItem('mail-merge-variable-width')); return value ? clamp(value) : 380; } catch { return 380; }
  });
  const change = value => { const next = clamp(value); setWidth(next); try { localStorage.setItem('mail-merge-variable-width', String(next)); } catch {} };
  const [left, ...rest] = React.Children.toArray(children);
  return <div className="dl-main dl-main-resizable" style={{ '--dl-config-width': `${width}px` }}>
    {left}
    <div className="dl-column-resizer" role="separator" aria-label="Breite des Variablenbereichs" aria-orientation="vertical" aria-valuemin={300} aria-valuemax={620} aria-valuenow={width} tabIndex={0}
      title="Ziehen oder mit den Pfeiltasten vergrößern und verkleinern"
      onDoubleClick={() => change(380)}
      onPointerDown={e => { e.currentTarget.setPointerCapture(e.pointerId); e.currentTarget.dataset.startX = e.clientX; e.currentTarget.dataset.startWidth = width; }}
      onPointerMove={e => { if (e.currentTarget.hasPointerCapture(e.pointerId)) change(Number(e.currentTarget.dataset.startWidth) + e.clientX - Number(e.currentTarget.dataset.startX)); }}
      onPointerUp={e => { if (e.currentTarget.hasPointerCapture(e.pointerId)) e.currentTarget.releasePointerCapture(e.pointerId); }}
      onKeyDown={e => { if (['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(e.key)) { e.preventDefault(); change(e.key === 'Home' ? 300 : e.key === 'End' ? 620 : width + (e.key === 'ArrowRight' ? 20 : -20)); } }}/>
    {rest}
  </div>;
}
