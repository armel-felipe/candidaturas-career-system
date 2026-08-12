const { chromium } = require('playwright');

(async () => {
  const url = 'https://www.glassdoor.com.br/Vaga/s%C3%A3o-paulo-s%C3%A3o-paulo-coordenador-a-de-redes-sociais-vagas-SRCH_IL.0,19_IC2479061_KO20,50.htm?jl=1010215448733&srs=JV_APPLYPANE';
  
  // Use the same profile dir from the playwright open command
  const profileDir = '/tmp/playwright_chromiumdev_profile-tOuM8v';
  
  const context = await chromium.launchPersistentContext(profileDir, {
    headless: false,
    args: ['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'],
    viewport: { width: 1366, height: 900 }
  });
  
  const page = await context.newPage();
  
  console.log('Navigating to:', url);
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForTimeout(5000);
  
  const title = await page.title();
  console.log('Page title:', title);
  
  const bodyText = await page.innerText('body');
  console.log('Body text length:', bodyText.length);
  console.log('='.repeat(80));
  console.log(bodyText.substring(0, 20000));
  
  await page.close();
  await context.close();
})();
