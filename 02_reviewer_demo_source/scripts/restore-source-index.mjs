import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, '..');
const sourcePath = path.join(root, 'index.source.html');
const targetPath = path.join(root, 'index.html');

if (!fs.existsSync(sourcePath)) {
  throw new Error(`Missing ${sourcePath}`);
}

fs.copyFileSync(sourcePath, targetPath);
console.log(`Restored Vite source index: ${targetPath}`);
