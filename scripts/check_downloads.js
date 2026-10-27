const { chromium } = require('playwright-core');
const fs = require('fs');
(async () => {
  const browser = await chromium.launch({headless: true, executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
  const page = await browser.newPage({viewport: {width: 1600, height: 1200}});
  await page.goto('http://127.0.0.1:8501', {waitUntil: 'networkidle', timeout: 60000});
  await page.getByRole('button', {name: '加载合成演示案例'}).click();
  await page.waitForTimeout(2000);
  await page.getByRole('tab', {name: '③ 导出报告'}).click();
  await page.waitForTimeout(1500);
  const results = [];
  for (const name of ['下载 HTML 报告', '下载 Markdown 报告', '下载结构化 JSON']) {
    const [download] = await Promise.all([
      page.waitForEvent('download', {timeout: 30000}),
      page.getByRole('button', {name}).click(),
    ]);
    const path = await download.path();
    const size = fs.statSync(path).size;
    results.push({button: name, suggested_filename: download.suggestedFilename(), size_bytes: size, non_empty: size > 1000});
  }
  const record = {
    ran_at: new Date().toISOString(),
    url: 'http://127.0.0.1:8501',
    browser: 'Microsoft Edge (Playwright headless)',
    synthetic_demo_case: true,
    screenshots: ['docs/ui-home.png', 'docs/ui-review.png', 'docs/ui-report.png', 'docs/ui-about.png', 'docs/ui-mobile.png', 'docs/ui-upload-review.png'],
    downloads: results,
    passed: results.every(item => item.non_empty),
  };
  fs.writeFileSync('docs/browser_smoke.json', JSON.stringify(record, null, 2), 'utf8');
  console.log(JSON.stringify(results, null, 2));
  if (!record.passed) process.exit(1);
  await browser.close();
})().catch(err => { console.error(err); process.exit(1); });


