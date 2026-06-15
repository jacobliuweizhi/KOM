import { chromium } from '@playwright/test';
import fs from 'node:fs/promises';
import path from 'node:path';

const root = process.cwd();
const screenshotDir = path.join(root, 'artifacts', 'screenshots');
const singleFilePath = path.join(root, 'KOM_Reviewer_Interface_Single_File.html');
const defaultUrl = `file:///${singleFilePath.replaceAll('\\', '/')}`;
const url = process.env.KOM_INTERFACE_URL || defaultUrl;

const pages = [
  { key: 'overview', label: 'Overview', file: '01-overview.png', title: '01 Overview', note: '首页、研究摘要、工作流地图和标准化病例边界。' },
  { key: 'workspace', label: 'Case workspace', file: '02-case-workspace-q4.png', title: '02 Case workspace', note: '病例选择、患者画像、运行工作流、证据和处方预览。' },
  { key: 'assess', label: 'KOM-Assess', file: '03-kom-assess.png', title: '03 KOM-Assess', note: '评估模块、影像/病史/风险画像输出。' },
  { key: 'treat', label: 'KOM-Treat', file: '04-kom-treat-rag.png', title: '04 KOM-Treat', note: 'KOM-RAG 与 naive RAG baseline 对比、多智能体治疗方案。' },
  { key: 'sim', label: 'KOM-Sim', file: '05-kom-sim.png', title: '05 KOM-Sim', note: '医生处方输入模拟与 KOM 规则评分。' },
  { key: 'score', label: 'KOM-Score', file: '06-kom-score.png', title: '06 KOM-Score', note: '评分维度、关键公式和安全错误定义。' },
  { key: 'results', label: 'Results', file: '07-results.png', title: '07 Results', note: '系统结果、医生交互、RAG 指标和评价指标展示。' },
  { key: 'methods', label: 'Methods', file: '08-methods.png', title: '08 Methods', note: '研究设计、数据边界和审稿人方法说明。' },
  { key: 'glossary', label: 'Glossary', file: '09-glossary.png', title: '09 Glossary', note: '术语表和定义检索。' }
];

await fs.mkdir(screenshotDir, { recursive: true });

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 960 } });
page.setDefaultTimeout(12_000);

await page.goto(url, { waitUntil: 'networkidle' });
await page.getByRole('button', { name: 'Reset' }).click();
await page.waitForTimeout(200);

for (const shot of pages) {
  if (shot.key !== 'overview') {
    await page.getByRole('button', { name: shot.label }).click();
  }
  if (shot.key === 'workspace') {
    await page.getByTestId('case-card-Q4-04-9222596').click();
    await page.getByTestId('run-workflow').click();
  }
  if (shot.key === 'sim') {
    await page.getByRole('button', { name: 'Clinician + KOM', exact: true }).click();
    await page.getByTestId('sim-textarea').fill('Topical NSAID first; supervised low-impact exercise; weight support; safety review; follow-up escalation rules.');
  }
  if (shot.key === 'glossary') {
    await page.getByLabel('Search glossary').fill('naive RAG baseline');
  }
  await page.waitForTimeout(300);
  await page.screenshot({ path: path.join(screenshotDir, shot.file), fullPage: true });
}

const mobile = await browser.newPage({ viewport: { width: 390, height: 844 } });
await mobile.goto(`${url}#overview`, { waitUntil: 'networkidle' });
await mobile.screenshot({ path: path.join(screenshotDir, '10-mobile-overview.png'), fullPage: true });
await mobile.close();

await browser.close();

const indexItems = [
  ...pages,
  { key: 'mobile', file: '10-mobile-overview.png', title: '10 Mobile overview', note: '390px 移动端显示与页面选择器。' }
];

const generatedAt = new Date().toISOString();
const indexHtml = `<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>KOM 界面截图索引</title>
  <style>
    body { margin: 0; background: #f3f1eb; color: #111827; font-family: Georgia, "Microsoft YaHei", serif; }
    header { padding: 32px 40px; background: #111827; color: white; }
    h1 { margin: 0 0 8px; font-size: 34px; }
    .meta { color: #cbd5e1; }
    main { max-width: 1280px; margin: 0 auto; padding: 28px; }
    .card { margin: 0 0 34px; border: 1px solid #d8dedc; border-radius: 12px; background: white; box-shadow: 0 18px 40px rgba(15,23,42,.08); overflow: hidden; }
    .card h2 { margin: 0; padding: 18px 22px 4px; font-size: 24px; }
    .card p { margin: 0; padding: 0 22px 18px; color: #475569; font-size: 15px; }
    img { display: block; width: 100%; height: auto; border-top: 1px solid #e5e7eb; }
    code { background: #eef2f7; border-radius: 5px; padding: 2px 6px; }
  </style>
</head>
<body>
  <header>
    <h1>KOM Reviewer Interface 界面截图索引</h1>
    <div class="meta">生成时间：${generatedAt}。后续修改界面时，可以直接按编号指出页面和截图。</div>
  </header>
  <main>
    ${indexItems.map((item) => `<section class="card">
      <h2>${item.title}</h2>
      <p>${item.note}<br />文件：<code>artifacts/screenshots/${item.file}</code></p>
      <img src="artifacts/screenshots/${item.file}" alt="${item.title}" />
    </section>`).join('\n')}
  </main>
</body>
</html>`;

const indexPath = path.join(root, 'KOM_Interface_Screenshot_Index.html');
const cnIndexPath = path.join(root, 'KOM_界面截图索引.html');
await fs.writeFile(indexPath, indexHtml, 'utf8');
await fs.writeFile(cnIndexPath, indexHtml, 'utf8');

const manifest = {
  generatedAt,
  sourceUrl: url,
  screenshots: indexItems.map((item) => ({
    title: item.title,
    note: item.note,
    path: path.join(screenshotDir, item.file)
  })),
  indexPath,
  cnIndexPath
};

await fs.writeFile(path.join(root, 'artifacts', 'screenshots', 'screenshot-index-manifest.json'), JSON.stringify(manifest, null, 2), 'utf8');
console.log(JSON.stringify(manifest, null, 2));
