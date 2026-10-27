const { chromium } = require('playwright-core');
const fs = require('fs');
(async () => {
  const browser = await chromium.launch({headless: true, executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
  const page = await browser.newPage({viewport: {width: 1600, height: 1200}});
  await page.goto('http://127.0.0.1:8501', {waitUntil: 'networkidle', timeout: 60000});
  const inputs = page.locator('input[type=file]');
  const count = await inputs.count();
  await inputs.nth(0).setInputFiles('D:/projects/chuanbo-xray/data/demo/case_01/promotional_copy.txt');
  await inputs.nth(1).setInputFiles([
    'D:/projects/chuanbo-xray/data/demo/case_01/product_manual.txt',
    'D:/projects/chuanbo-xray/data/demo/case_01/trial_summary.txt',
  ]);
  await page.waitForTimeout(2500);
  await page.getByRole('button', {name: '开始诊断'}).click();
  await page.waitForTimeout(3500);
  await page.getByRole('tab', {name: '② 证据审查台'}).click();
  await page.waitForTimeout(1500);
  const body = await page.locator('body').innerText();
  const checks = {
    upload_inputs_found: count === 3,
    review_created: body.includes('审核编号') && body.includes('宣传主张'),
    six_claims: body.includes('CLM-001') && body.includes('CLM-006'),
    evidence_panel: body.includes('查看原始证据'),
    no_exception_text: !body.includes('分析未完成') && !body.includes('Traceback'),
  };
  const record = {
    ran_at: new Date().toISOString(),
    url: 'http://127.0.0.1:8501',
    files: ['promotional_copy.txt', 'product_manual.txt', 'trial_summary.txt'],
    checks,
    passed: Object.values(checks).every(Boolean),
  };
  fs.writeFileSync('docs/upload_flow.json', JSON.stringify(record, null, 2), 'utf8');
  await page.screenshot({path: 'docs/ui-upload-review.png', fullPage: true});
  console.log(JSON.stringify(record, null, 2));
  await browser.close();
  if (!record.passed) process.exit(1);
})().catch(err => { console.error(err); process.exit(1); });

