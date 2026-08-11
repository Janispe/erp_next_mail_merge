import { describe, expect, it, vi } from "vitest";
import { createVersionPreviewCache, versionPreviewContextKey } from "./versionPreviewCache.js";

describe("version preview cache", () => {
  it("renders each context and version only once", async () => {
    const render = vi.fn().mockResolvedValue({ pdf_base64: "pdf-v1" });
    const cache = createVersionPreviewCache(render);

    await cache.load("context|v1", { version: "v1" });
    await cache.load("context|v1", { version: "v1" });

    expect(render).toHaveBeenCalledTimes(1);
    expect(cache.get("context|v1")).toBe("pdf-v1");
  });

  it("deduplicates concurrent background and foreground requests", async () => {
    let finish;
    const render = vi.fn(() => new Promise((resolve) => { finish = resolve; }));
    const cache = createVersionPreviewCache(render);
    const foreground = cache.load("context|v2", { version: "v2" });
    const background = cache.load("context|v2", { version: "v2" });

    await Promise.resolve();
    expect(render).toHaveBeenCalledTimes(1);
    finish({ pdf_base64: "pdf-v2" });
    await expect(Promise.all([foreground, background])).resolves.toEqual(["pdf-v2", "pdf-v2"]);
  });

  it("separates recipient and print contexts", () => {
    expect(versionPreviewContextKey({ templateId: "T", recipientId: "A", druckSchwarzWeiss: false }))
      .not.toBe(versionPreviewContextKey({ templateId: "T", recipientId: "B", druckSchwarzWeiss: false }));
    expect(versionPreviewContextKey({ templateId: "T", recipientId: "A", druckSchwarzWeiss: false }))
      .not.toBe(versionPreviewContextKey({ templateId: "T", recipientId: "A", druckSchwarzWeiss: true }));
  });
});
