import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, '..');
const dist = path.join(root, 'dist');
const sourceHtmlPath = path.join(dist, 'index.html');
const singleFileName = 'KOM_Reviewer_Interface_单文件双击打开.html';
const asciiSingleFileName = 'KOM_Reviewer_Interface_Single_File.html';
const distSinglePath = path.join(dist, singleFileName);
const rootSinglePath = path.join(root, singleFileName);
const distAsciiSinglePath = path.join(dist, asciiSingleFileName);
const rootAsciiSinglePath = path.join(root, asciiSingleFileName);
const rootIndexPath = path.join(root, 'index.html');

if (!fs.existsSync(sourceHtmlPath)) {
  throw new Error(`Missing built index.html: ${sourceHtmlPath}. Run npm run build first.`);
}

let html = fs.readFileSync(sourceHtmlPath, 'utf8');

html = html.replace(
  /<link rel="stylesheet" crossorigin href="([^"]+)">/g,
  (_match, href) => {
    const cssPath = path.join(dist, href.replace(/^\//, ''));
    const css = fs.readFileSync(cssPath, 'utf8');
    return `<style>\n${css}\n</style>`;
  }
);

html = html.replace(
  /<script type="module" crossorigin src="([^"]+)"><\/script>/g,
  (_match, src) => {
    const jsPath = path.join(dist, src.replace(/^\//, ''));
    const js = fs.readFileSync(jsPath, 'utf8');
    return `<script type="module">\n${js}\n</script>`;
  }
);

html = html.replace(
  '<title>KOM Reviewer Interface</title>',
  '<title>KOM Reviewer Interface - Single File</title>'
);

const stamp = new Date().toISOString();
html = html.replace(
  '</head>',
  `  <meta name="kom-single-file-build" content="${stamp}" />\n  </head>`
);

fs.writeFileSync(distSinglePath, html, 'utf8');
fs.writeFileSync(rootSinglePath, html, 'utf8');
fs.writeFileSync(distAsciiSinglePath, html, 'utf8');
fs.writeFileSync(rootAsciiSinglePath, html, 'utf8');
fs.writeFileSync(rootIndexPath, html, 'utf8');

console.log(JSON.stringify({
  status: 'ok',
  generatedAt: stamp,
  distSinglePath,
  rootSinglePath,
  distAsciiSinglePath,
  rootAsciiSinglePath,
  rootIndexPath,
  bytes: fs.statSync(rootSinglePath).size
}, null, 2));
