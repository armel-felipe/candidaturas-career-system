const { chromium } = require('playwright');

(async () => {
  const url = 'https://www.glassdoor.com.br/Vaga/s%C3%A3o-paulo-s%C3%A3o-paulo-coordenador-a-de-redes-sociais-vagas-SRCH_IL.0,19_IC2479061_KO20,50.htm?jl=1010215448733&srs=JV_APPLYPANE';
  
  const profileDir = '/home/ubuntu/projetos/candidaturas/.career-state/browser/glassdoor-profile';
  
  const context = await chromium.launchPersistentContext(profileDir, {
    headless: false,
    args: ['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'],
    viewport: { width: 1366, height: 900 },
    locale: 'pt-BR'
  });
  
  const page = context.pages()[0] || await context.newPage();
  
  console.log('Navigating to:', url);
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForTimeout(3000);
  
  const title = await page.title();
  console.log('Page title:', title);
  console.log('URL:', page.url());
  
  // Check if logged in
  const loginButton = await page.$('text=Entrar');
  if (loginButton) {
    console.log('NOT_LOGGED_IN');
    console.log('Waiting for user to login via noVNC...');
    // Wait up to 15 minutes for login
    for (let i = 0; i < 90; i++) {
      await page.waitForTimeout(10000);
      const stillLogin = await page.$('text=Entrar');
      if (!stillLogin) {
        console.log('Login detected! Waiting for page to load...');
        await page.waitForTimeout(3000);
        break;
      }
      if (i % 6 === 0) console.log(`Still waiting... (${Math.floor(i/6)} min)`);
    }
  }
  
  // Now try to get the job content
  // Check if we need to navigate to the specific job
  if (page.url().includes('SRCH_IL') && !page.url().includes('jl=')) {
    console.log('On search page, clicking on job listing...');
    // Click on the specific job
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await page.waitForTimeout(5000);
  }
  
  const bodyText = await page.innerText('body');
  console.log('Body text length:', bodyText.length);
  console.log('='.repeat(80));
  console.log(bodyText.substring(0, 20000));
  
  // Try specific selectors
  const selectors = [
    '[class*="jobDescriptionContent"]',
    '[class*="JobDescription"]',
    '[data-test*="jobDescription"]',
    '[class*="jobDescription"]',
    'div.jobDescriptionContent'
  ];
  
  for (const sel of selectors) {
    try {
      const els = await page.$$(sel);
      for (const el of els) {
        const text = await el.innerText();
        if (text.length > 100) {
          console.log('\n=== JOB DESCRIPTION via', sel, '(len=' + text.length + ') ===');
          console.log(text);
        }
      }
    } catch(e) {}
  }
  
  // Don't close - keep browser open for user
  console.log('\nDONE_EXTRACTION');
  console.log('Browser staying open. Press Ctrl+C to close.');
  // Keep alive
  await new Promise(() => {});
})();
