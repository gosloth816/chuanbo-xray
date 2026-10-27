const { chromium } = require('playwright-core');
(async () => {
  const browser = await chromium.launch({headless: true, executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
  const page = await browser.newPage({viewport: {width: 1600, height: 1200}, deviceScaleFactor: 1});
  await page.goto('http://127.0.0.1:8501', {waitUntil: 'networkidle', timeout: 60000});
  await page.getByRole('tab', {name: '④ 关于与验证'}).click();
  await page.waitForTimeout(1200);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(300);
  const body = await page.locator('body').innerText();
  console.log(body.slice(body.indexOf('产品说明与 AI 使用披露'), body.indexOf('产品说明与 AI 使用披露') + 1500));
  await page.screenshot({path: 'docs/ui-about.png', fullPage: true});
  await browser.close();
})().catch(err => { console.error(err); process.exit(1); });
