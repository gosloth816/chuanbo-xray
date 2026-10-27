const { chromium } = require('playwright-core');
(async () => {
  const browser = await chromium.launch({headless: true, executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
  const page = await browser.newPage({viewport: {width: 1440, height: 1100}, deviceScaleFactor: 1});
  await page.goto('http://127.0.0.1:8501', {waitUntil: 'networkidle', timeout: 60000});
  await page.waitForTimeout(3000);
  const title = await page.title();
  const body = await page.locator('body').innerText();
  console.log(JSON.stringify({title, body: body.slice(0, 1400)}, null, 2));
  await page.screenshot({path: 'docs/ui-home.png', fullPage: true});
  await browser.close();
})().catch(err => { console.error(err); process.exit(1); });

