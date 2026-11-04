// One-command hero optimization: source PNG -> responsive WebP set.
// Usage: npm run optimize-hero
// Source stays in assets-src/ (never served); dist gets only the WebP set.
import sharp from 'sharp';
import { statSync } from 'fs';
import { fileURLToPath } from 'url';
import path from 'path';

const dir = path.dirname(fileURLToPath(import.meta.url));
const SRC = path.join(dir, '../assets-src/hero-race-source.png');
const OUT = (w) => path.join(dir, `../public/assets/hero-race-${w}.webp`);

for (const w of [1200, 800]) {
  await sharp(SRC).resize({ width: w, withoutEnlargement: true }).webp({ quality: 78 }).toFile(OUT(w));
  const kb = (statSync(OUT(w)).size / 1024).toFixed(1);
  console.log(`hero-race-${w}.webp: ${kb} KB`);
}
