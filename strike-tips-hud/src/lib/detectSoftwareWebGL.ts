let cached: boolean | null = null;

export function isSoftwareWebGL(): boolean {
  if (cached !== null) return cached as boolean;

  try {
    const canvas = document.createElement('canvas');
    const gl =
      (canvas.getContext('webgl2') as WebGLRenderingContext | null) ||
      (canvas.getContext('webgl') as WebGLRenderingContext | null);
    if (!gl) {
      cached = true;
      return true;
    }

    const ext = gl.getExtension('WEBGL_debug_renderer_info');
    if (!ext) {
      cached = false;
      return false;
    }

    const renderer = gl
      .getParameter(ext.UNMASKED_RENDERER_WEBGL as number)
      .toLowerCase();

    gl.getExtension('WEBGL_lose_context')?.loseContext?.();

    cached =
      renderer.includes('swiftshader') ||
      renderer.includes('software') ||
      renderer.includes('llvmpipe') ||
      renderer.includes('mesa offscreen') ||
      renderer.includes('basic') ||
      renderer.includes('chromium os mesa');

    return cached as boolean;
  } catch {
    cached = true;
    return true;
  }
}

export function clearWebGLCache(): void {
  cached = null;
}
