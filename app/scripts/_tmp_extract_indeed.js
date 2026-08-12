const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({
    headless: false,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });
  const context = await browser.newContext({
    userAgent: 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    locale: 'pt-BR',
    viewport: { width: 1280, height: 800 },
  });
  const page = await context.newPage();

  try {
    await page.goto('https://br.indeed.com/viewjob?jk=257dc6b0985d37c9', {
      waitUntil: 'domcontentloaded',
      timeout: 30000,
    });

    await page.waitForTimeout(10000);

    const title = await page.title();
    console.log('=== TITLE ===');
    console.log(title);

    if (title.includes('Security Check') || title.includes('captcha') || title.includes('Cloudflare')) {
      console.log('BLOCKED by Cloudflare');
      const bodyText = await page.evaluate(() => document.body.innerText);
      console.log('=== BODY TEXT ===');
      console.log(bodyText.substring(0, 2000));
      await browser.close();
      return;
    }

    const bodyText = await page.evaluate(() => document.body.innerText);
    console.log('=== FULL BODY TEXT ===');
    console.log(bodyText);

  } catch (err) {
    console.error('Error:', err.message);
  }

  await browser.close();
})();
