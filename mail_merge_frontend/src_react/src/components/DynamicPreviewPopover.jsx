import React, { useEffect } from "react";
import { Icon } from "./Icon.jsx";

function previewKind(group) {
	return group === "variable" ? "Variable" : "Platzhalter";
}

export const DynamicPreviewPopover = ({ token, group, html, rect, onClose }) => {
	useEffect(() => {
		const mountedAt = Date.now();
		const onKey = (e) => {
			if (e.key === "Escape") onClose();
		};
		const onDown = (e) => {
			if (Date.now() - mountedAt < 50) return;
			if (!(e.target.closest && e.target.closest(".dynamic-preview-popover"))) onClose();
		};
		window.addEventListener("keydown", onKey);
		document.addEventListener("mousedown", onDown);
		return () => {
			window.removeEventListener("keydown", onKey);
			document.removeEventListener("mousedown", onDown);
		};
	}, [onClose]);

	const width = 360;
	const left = Math.max(8, Math.min(rect?.left ?? 100, window.innerWidth - width - 8));
	const below = (rect?.bottom ?? 100) + 7;
	const top = below + 230 <= window.innerHeight
		? below
		: Math.max(8, (rect?.top ?? 100) - 230 - 7);
	const expression = String(token || "")
		.replace(/^\{\{\s*\$?\s*/, "")
		.replace(/\s*\$?\s*\}\}$/, "")
		.trim();
	const kind = previewKind(group);

	return (
		<div
			className="dynamic-preview-popover"
			style={{ position: "fixed", left, top, zIndex: 330 }}
			onMouseDown={(e) => e.stopPropagation()}
		>
			<div className="dpp-header">
				<span className={`dpp-icon dpp-icon-${group === "variable" ? "variable" : "placeholder"}`}>
					{group === "variable" ? "ƒ" : "{}"}
				</span>
				<div className="dpp-heading">
					<span className="dpp-kind">{kind}</span>
					<strong>Aktuelle Vorschau</strong>
				</div>
				<button className="bp-close" onClick={onClose} aria-label="Vorschau schließen" title="Schließen">
					<Icon name="x" size={11} />
				</button>
			</div>
			<div className="dpp-body">
				<div className="dpp-label">Gerenderter Wert</div>
				{html ? (
					<div className="dpp-value" dangerouslySetInnerHTML={{ __html: html }} />
				) : (
					<div className="dpp-empty">Vorschau ist im Layoutmodus verfügbar.</div>
				)}
				<div className="dpp-label">Ausdruck</div>
				<code className="dpp-expression">{expression || token}</code>
			</div>
		</div>
	);
};
