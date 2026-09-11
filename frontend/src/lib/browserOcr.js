/**
 * Browser-side OCR fallback (Tesseract.js).
 *
 * Used only when the server cannot be reached. It extracts text and nothing more:
 * the text is posted to `/analyze-text` and the Python rule engine decides
 * compliance, exactly as it does for a server-side scan.
 *
 * The file this replaces also contained a second, JavaScript reimplementation of
 * the Legal Metrology rules. Two rule engines meant a phone and the server could
 * disagree about whether a package was lawful, which is not a defensible position
 * for an enforcement tool. There is now one rule engine.
 */

let workerPromise = null;

/** One worker for the session; spinning one up per image costs several seconds. */
async function getWorker(onProgress) {
  if (!workerPromise) {
    workerPromise = import('tesseract.js').then(({ createWorker }) =>
      createWorker('eng', 1, {
        logger: (message) => {
          if (message.status === 'recognizing text' && onProgress) {
            onProgress(Math.round((message.progress || 0) * 100));
          }
        },
      }),
    );
  }
  return workerPromise;
}

export async function terminateOcr() {
  if (!workerPromise) return;
  try {
    const worker = await workerPromise;
    await worker.terminate();
  } catch {
    /* already gone */
  } finally {
    workerPromise = null;
  }
}

/**
 * Reads one image and returns { text, segments } where each segment carries the
 * bounding box the server expects, so font-height analysis still has real geometry.
 */
export async function readImage(file, onProgress) {
  const worker = await getWorker(onProgress);
  const { data } = await worker.recognize(file);

  const lines = data?.lines ?? [];
  const segments = lines
    .filter((line) => (line.text || '').trim())
    .map((line) => {
      const { x0, y0, x1, y1 } = line.bbox || {};
      return {
        text: line.text.trim(),
        confidence: Number(((line.confidence ?? 0) / 100).toFixed(4)),
        box:
          x0 === undefined
            ? null
            : [
                [x0, y0],
                [x1, y0],
                [x1, y1],
                [x0, y1],
              ],
      };
    })
    .filter((segment) => segment.box);

  return { text: data?.text ?? '', segments };
}

/** Reads several angles and merges their segments, tagging which image each came from. */
export async function readImages(files, onProgress) {
  const allSegments = [];
  const texts = [];
  let dimensions = null;

  for (let index = 0; index < files.length; index += 1) {
    const { text, segments } = await readImage(files[index], (percent) =>
      onProgress?.(Math.round(((index + percent / 100) / files.length) * 100)),
    );
    texts.push(text);
    segments.forEach((segment) => allSegments.push({ ...segment, image_index: index + 1 }));

    if (index === 0) dimensions = await imageDimensions(files[0]);
  }

  return { text: texts.join('\n'), segments: allSegments, dimensions };
}

function imageDimensions(file) {
  return new Promise((resolve) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      resolve([img.naturalHeight, img.naturalWidth]);
      URL.revokeObjectURL(url);
    };
    img.onerror = () => {
      resolve([1000, 1000]);
      URL.revokeObjectURL(url);
    };
    img.src = url;
  });
}
