const { chromium } = require('playwright-core');
(async () => {
  const browser = await chromium.launch({headless: true, executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
  const page = await browser.newPage({viewport: {width: 390, height: 844}, deviceScaleFactor: 1});
  await page.goto('http://127.0.0.1:8501', {waitUntil: 'networkidle', timeout: 60000});
  await page.waitForTimeout(3000);
  console.log((await page.locator('body').innerText()).slice(0, 900));
  await page.screenshot({path: 'docs/ui-mobile.png', fullPage: true});
  await browser.close();
})().catch(err => { console.error(err); process.exit(1); });
