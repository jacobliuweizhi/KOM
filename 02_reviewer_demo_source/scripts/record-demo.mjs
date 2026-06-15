import { chromium } from '@playwright/test';
import fs from 'node:fs/promises';
import path from 'node:path';

const root = process.cwd();
const artifactsDir = path.join(root, 'artifacts');
const screenshotDir = path.join(artifactsDir, 'screenshots');
const videoDir = path.join(artifactsDir, 'videos');
const url = process.env.KOM_DEMO_URL || 'http://127.0.0.1:5173';

await fs.mkdir(screenshotDir, { recursive: true });
await fs.mkdir(videoDir, { recursive: true });

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({
  viewport: { width: 1440, height: 960 },
  recordVideo: {
    dir: videoDir,
    size: { width: 1440, height: 960 }
  }
});

const page = await context.newPage();
page.setDefaultTimeout(12_000);

async function screenshot(name) {
  await page.screenshot({ path: path.join(screenshotDir, `${name}.png`), fullPage: true });
}

await page.goto(url);
await page.waitForLoadState('networkidle');
await screenshot('01-overview');

await page.getByRole('button', { name: 'Case workspace' }).click();
await page.getByTestId('case-card-Q4-04-9222596').click();
await page.getByTestId('run-workflow').click();
await page.waitForTimeout(700);
await screenshot('02-case-workspace-q4');

await page.getByRole('button', { name: 'KOM-Treat' }).click();
await page.waitForTimeout(700);
await screenshot('03-treat-rag-baseline');

await page.getByRole('button', { name: 'KOM-Sim' }).click();
await page.getByTestId('sim-textarea').fill('Topical NSAID first, supervised low-impact exercise, weight support, safety review, and follow-up.');
await page.waitForTimeout(700);
await screenshot('04-sim-clinician-kom');

await page.getByRole('button', { name: 'Results' }).click();
await page.waitForTimeout(700);
await screenshot('05-results-dashboard');

await page.getByRole('button', { name: 'KOM-Score' }).click();
await page.waitForTimeout(700);
await screenshot('06-score-definitions');

await page.getByRole('button', { name: 'Glossary' }).click();
await page.getByLabel('Search glossary').fill('naive RAG baseline');
await page.waitForTimeout(700);
await screenshot('07-glossary-search');

await page.getByRole('button', { name: 'Case workspace' }).click();
await page.getByRole('button', { name: 'Download report' }).click();
await page.waitForTimeout(700);

await context.close();
await browser.close();

const videos = await fs.readdir(videoDir);
const webm = videos.filter((file) => file.endsWith('.webm')).sort().at(-1);
const manifest = {
  recordedAt: new Date().toISOString(),
  url,
  viewport: '1440x960',
  video: webm ? path.join(videoDir, webm) : null,
  screenshots: (await fs.readdir(screenshotDir)).filter((file) => file.endsWith('.png')).sort().map((file) => path.join(screenshotDir, file))
};

await fs.writeFile(path.join(artifactsDir, 'recording-manifest.json'), JSON.stringify(manifest, null, 2), 'utf-8');
console.log(JSON.stringify(manifest, null, 2));
