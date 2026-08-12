const { chromium } = require('playwright');

(async () => {
  const url = 'https://www.glassdoor.com.br/Vaga/s%C3%A3o-paulo-s%C3%A3o-paulo-coordenador-a-de-redes-sociais-vagas-SRCH_IL.0,19_IC2479061_KO20,50.htm?jl=1010215448733&srs=JV_APPLYPANE';
  
  // Use the same user-data-dir from the playwright open command
  const browser = await chromium.launch({
    headless: false,
    args: ['--no-sandbox', '--disable-dev-shm-usage']
  });
  
  // Create context with the existing profile
  const context = await browser.newContext({
    storageState: undefined
  });
  
  const page = await context.newPage();
  
  console.log('Navigating to:', url);
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForTimeout(5000);
  
  const title = await page.title();
  console.log('Page title:', title);
  
  // Check if we're on the job listing page or search results
  const bodyText = await page.innerText('body');
  console.log('Body text length:', bodyText.length);
  console.log('='.repeat(80));
  console.log(bodyText.substring(0, 20000));
  
  await page.close();
  await browser.close();
})();
