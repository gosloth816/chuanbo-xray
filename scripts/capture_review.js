const { chromium } = require('playwright-core');
(async () => {
  const browser = await chromium.launch({headless: true, executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
  const page = await browser.newPage({viewport: {width: 1600, height: 1200}, deviceScaleFactor: 1});
  await page.goto('http://127.0.0.1:8501', {waitUntil: 'networkidle', timeout: 60000});
  await page.getByRole('button', {name: '加载合成演示案例'}).click();
  await page.waitForTimeout(2500);
  await page.getByRole('tab', {name: '② 证据审查台'}).click();
  await page.waitForTimeout(2000);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(400);
  const body = await page.locator('body').innerText();
  console.log(body.slice(body.indexOf('绿盾一号合成演示案例'), body.indexOf('绿盾一号合成演示案例') + 2400));
  await page.screenshot({path: 'docs/ui-review.png', fullPage: true});
  await browser.close();
})().catch(err => { console.error(err); process.exit(1); });
