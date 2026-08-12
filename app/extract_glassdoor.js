const { chromium } = require('playwright');

(async () => {
  const url = 'https://www.glassdoor.com.br/Vaga/s%C3%A3o-paulo-s%C3%A3o-paulo-coordenador-a-de-redes-sociais-vagas-SRCH_IL.0,19_IC2479061_KO20,50.htm?jl=1010215448733&srs=JV_APPLYPANE';
  
  // Connect to the running Chromium via CDP
  let browser;
  try {
    browser = await chromium.connectOverCDP('http://127.0.0.1:9222');
  } catch(e) {
    console.log('CDP connect failed, launching new browser...');
    browser = await chromium.launch({ headless: false, display: ':99' });
  }
  
  const context = browser.contexts[0] || await browser.newContext();
  const page = await context.newPage();
  
  console.log('Navigating to:', url);
  await page.goto(url, { waitUntil: 'networkidle', timeout: 60000 });
  await page.waitForTimeout(3000);
  
  const title = await page.title();
  console.log('Page title:', title);
  
  // Get full page text
  const bodyText = await page.innerText('body');
  console.log('Body text length:', bodyText.length);
  console.log('='.repeat(80));
  console.log(bodyText.substring(0, 15000));
  
  // Try specific selectors for job description
  const selectors = [
    '[class*="jobDescriptionContent"]',
    '[class*="job-description"]',
    '[id*="JobDescriptionContainer"]',
    '[data-test*="jobDescription"]',
    '.jobDescriptionContent',
    '[class*="JobDescription"]'
  ];
  
  for (const sel of selectors) {
    try {
      const el = await page.$(sel);
      if (el) {
        const text = await el.innerText();
        console.log('\n=== FOUND JOB DESCRIPTION via', sel, '===');
        console.log(text);
        break;
      }
    } catch(e) {}
  }
  
  await page.close();
  await browser.close();
})();
