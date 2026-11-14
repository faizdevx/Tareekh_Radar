// Order-sheet photo reader: Tesseract.js runs in this browser (WebAssembly); the photo is never uploaded.
// The engine (~1 MB) and language data (English ~3 MB, Hindi ~1.4 MB) download once on first use, then the
// service worker keeps them for offline use.
const SRC = "https://cdn.jsdelivr.net/npm/tesseract.js@7.0.0/dist/tesseract.min.js";
let loading = null;
function loadLib() {
  loading ??= new Promise((res, rej) => {
    if (window.Tesseract) return res(window.Tesseract);
    const s = document.createElement("script");
    s.src = SRC; s.crossOrigin = "anonymous";
    s.onload = () => res(window.Tesseract); s.onerror = () => { loading = null; rej(new Error("ocr-load")); };
    document.head.appendChild(s);
  });
  return loading;
}

/** Read text from an image File. onProgress(0..1, status). Languages: English + Hindi. */
export async function readImage(file, onProgress) {
  const T = await loadLib();
  const worker = await T.createWorker(["eng", "hin"], 1, {
    logger: (m) => onProgress?.(typeof m.progress === "number" ? m.progress : 0, m.status || ""),
  });
  try {
    const { data } = await worker.recognize(file);
    return data.text || "";
  } finally {
    await worker.terminate();
  }
}
