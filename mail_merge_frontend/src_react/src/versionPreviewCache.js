export function createVersionPreviewCache(renderPreview) {
  const values = new Map();
  const requests = new Map();
  let generation = 0;

  return {
    has(key) {
      return values.has(key);
    },

    get(key) {
      return values.get(key);
    },

    load(key, params) {
      if (values.has(key)) return Promise.resolve(values.get(key));
      if (requests.has(key)) return requests.get(key);

      const requestGeneration = generation;
      const request = Promise.resolve()
        .then(() => renderPreview(params))
        .then((result) => {
          const preview = { ...result, pdf_base64: result?.pdf_base64 || "" };
          if (preview.ready === false) preview.pdf_base64 = "";
          if (requestGeneration === generation) values.set(key, preview);
          return preview;
        })
        .finally(() => {
          if (requests.get(key) === request) requests.delete(key);
        });
      requests.set(key, request);
      return request;
    },

    clear() {
      generation += 1;
      values.clear();
      requests.clear();
    },
  };
}

export function versionPreviewContextKey({ templateId, iterationDoctype, recipientId, druckSchwarzWeiss }) {
  return [templateId || "", iterationDoctype || "", recipientId || "", druckSchwarzWeiss ? "sw" : "farbe"].join("|");
}
