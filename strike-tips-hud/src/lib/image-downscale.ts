/** Client-side image downscale (Oct-2026: full-res phone photos blew past
 *  provider payload limits — "request too large" before any model saw pixels).
 *  High-contrast TAB grids stay OCR-able at 1568px while payload drops ~90%.
 */
export const MAX_EDGE_PX = 1568;
export const JPEG_QUALITY = 0.85;
/** Below this byte size the original file passes through untouched. */
export const PASSTHROUGH_BYTES = 500 * 1024;

export interface Downscaled {
  data: string; // base64, no data: prefix
  mimeType: string;
  downscaled: boolean;
}

function loadBitmap(file: Blob): Promise<ImageBitmap> {
  if (typeof createImageBitmap === 'function') {
    return createImageBitmap(file);
  }
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      URL.revokeObjectURL(url);
      if ('decode' in img) {
        (img.decode() as Promise<void>).then(
          () => createImageBitmap(img).then(resolve, reject),
          reject,
        );
      } else {
        createImageBitmap(img).then(resolve, reject);
      }
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error('undecodable image'));
    };
    img.src = url;
  });
}

export async function downscaleImage(file: File): Promise<Downscaled> {
  const fallback = async (): Promise<Downscaled> => {
    const buf = new Uint8Array(await file.arrayBuffer());
    let bin = '';
    const CH = 0x8000;
    for (let i = 0; i < buf.length; i += CH) {
      bin += String.fromCharCode.apply(null, buf.subarray(i, i + CH) as unknown as number[]);
    }
    return { data: btoa(bin), mimeType: file.type || 'image/jpeg', downscaled: false };
  };

  if (!file.type.startsWith('image/')) {
    return fallback();
  }
  try {
    const bmp = await loadBitmap(file);
    const longest = Math.max(bmp.width, bmp.height);
    if (file.size <= PASSTHROUGH_BYTES && longest <= MAX_EDGE_PX) {
      bmp.close?.();
      return fallback();
    }
    const scale = Math.min(1, MAX_EDGE_PX / longest);
    const w = Math.max(1, Math.round(bmp.width * scale));
    const h = Math.max(1, Math.round(bmp.height * scale));
    const canvas = document.createElement('canvas');
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext('2d');
    if (!ctx) {
      bmp.close?.();
      return fallback();
    }
    ctx.drawImage(bmp, 0, 0, w, h);
    bmp.close?.();
    const url = canvas.toDataURL('image/jpeg', JPEG_QUALITY);
    const data = url.split(',')[1] || '';
    if (!data) return fallback();
    return { data, mimeType: 'image/jpeg', downscaled: true };
  } catch {
    return fallback();
  }
}
