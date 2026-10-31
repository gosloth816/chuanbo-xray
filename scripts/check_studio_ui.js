const {chromium} = require('../.tools/browser/node_modules/playwright-core');
const fs = require('fs');
(async () => {
  const browser = await chromium.launch({headless:true, executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
  const url = process.env.STUDIO_CHECK_URL || 'http://127.0.0.1:8507';
  try {
    const page = await browser.newPage({viewport:{width:1440,height:1050}});
    await page.goto(url,{waitUntil:'networkidle'});
    await page.getByRole('button',{name:'加载合成演示',exact:true}).click();
    await page.getByLabel('产品名称',{exact:true}).waitFor();
    await page.waitForFunction(()=>Array.from(document.querySelectorAll('input')).some(el=>el.value==='演示苹果'));
    await page.screenshot({path:'docs/ui-studio-product-final.png',fullPage:true});
    await page.getByRole('tab',{name:'③ 文案工作台',exact:true}).click();
    await page.getByText('合成演示：下面的文案预先编写',{exact:false}).waitFor();
    await page.getByLabel('正文',{exact:true}).first().fill('演示苹果，5斤一箱，39元。');
    await page.getByRole('button',{name:'保存修改',exact:true}).first().click();
    await page.getByText('修改已保存并留痕。',{exact:true}).waitFor();
    await page.screenshot({path:'docs/ui-studio-drafts-final.png',fullPage:true});
    const downloaded = page.waitForEvent('download');
    await page.getByRole('button',{name:'下载创作记录 JSON',exact:true}).click();
    const file = await downloaded;
    await file.saveAs('.test-temp/studio-record.json');
    const record=JSON.parse(fs.readFileSync('.test-temp/studio-record.json','utf8'));
    if(!record.synthetic || !record.events.some(e=>e.action==='human_edit'))throw Error('演示标识或修改留痕缺失');
    await page.getByRole('tab',{name:'④ 发布前检查',exact:true}).click();
    await page.getByRole('button',{name:'一键送至传播 X 光',exact:true}).click();
    await page.getByRole('tab',{name:'② 证据审查台',exact:true}).click();
    await page.getByText('齐鲁卖点发布前审核',{exact:true}).waitFor();
    await page.screenshot({path:'docs/ui-studio-xray-final.png',fullPage:true});
    const mobile=await browser.newPage({viewport:{width:390,height:844}});
    await mobile.goto(url,{waitUntil:'networkidle'});
    await mobile.getByRole('button',{name:'加载合成演示',exact:true}).waitFor();
    await mobile.screenshot({path:'docs/ui-studio-mobile-final.png',fullPage:true});
    if(await mobile.evaluate(()=>document.documentElement.scrollWidth>innerWidth+2))throw Error('移动端横向溢出');
    fs.writeFileSync('docs/studio_browser_check.json',JSON.stringify({passed:true,checked_at:new Date().toISOString(),real_model_verified:false,checks:['合成示例加载','文案编辑与留痕','JSON导出','传播X光送审','手机无横向溢出']},null,2));
    console.log('创作编辑、记录下载、传播X光交接与手机布局通过；未验证真实模型。');
  }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
