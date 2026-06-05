const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const USER_DATA_DIR = path.resolve('.career-state/browser/linkedin');
const OUTPUT = 'inbox/linkedin_saved_jobs.json';
const SOURCE_URL = 'https://www.linkedin.com/jobs-tracker/';
const DEFAULT_MAX_PAGES = 2;
const DEEP_SCAN_MAX_PAGES = 100;

function parseArgs(argv) {
  const args = {
    maxPages: DEFAULT_MAX_PAGES,
  };

  for (let i = 0; i < argv.length; i++) {
    const item = argv[i];
    if (item === '--all') {
      args.maxPages = DEEP_SCAN_MAX_PAGES;
    } else if (item === '--max-pages') {
      const raw = argv[i + 1];
      const parsed = Number.parseInt(raw, 10);
      if (!Number.isInteger(parsed) || parsed < 1) {
        throw new Error('--max-pages must be a positive integer');
      }
      args.maxPages = parsed;
      i++;
    }
  }

  return args;
}

function usage() {
  console.log(`Usage: npm run linkedin:saved-jobs:extract
       npm run linkedin:saved-jobs:extract -- --max-pages 3
       npm run linkedin:saved-jobs:extract -- --all

Extracts LinkedIn saved jobs from the authenticated Playwright session and
writes ${OUTPUT}.

By default, extracts the saved jobs shown in LinkedIn's jobs tracker. Use --all
only for a historical/deep pagination sweep.`);
}

if (process.argv.includes('--help') || process.argv.includes('-h')) {
  usage();
  process.exit(0);
}

(async () => {
  const args = parseArgs(process.argv.slice(2));
  const browser = await chromium.launchPersistentContext(USER_DATA_DIR, {
    headless: true,
    args: ['--no-sandbox', '--disable-blink-features=AutomationControlled'],
  });

  const page = await browser.newPage();
  page.setDefaultTimeout(120000);

  const allJobs = [];
  const globalSeen = new Set();
  const scannedPages = [];
  let expectedTotal = null;

  for (let pg = 1; pg <= args.maxPages; pg++) {
    if (pg === 1) {
      console.log(`\n=== Tracker page ${pg} ===`);
      await page.goto(SOURCE_URL, { waitUntil: 'load', timeout: 120000 });
      await page.waitForTimeout(7000);
    } else {
      const clicked = await page.evaluate((targetPage) => {
        const normalize = (value) => (value || '').replace(/\s+/g, ' ').trim();
        const controls = [...document.querySelectorAll('button,a')];
        const target =
          controls.find((el) => normalize(el.getAttribute('aria-label')) === `Página ${targetPage}`) ||
          controls.find((el) => normalize(el.innerText || el.textContent) === String(targetPage)) ||
          controls.find((el) => /Próxima/.test(normalize(el.innerText || el.getAttribute('aria-label') || el.textContent)));
        if (!target) return false;
        target.click();
        return true;
      }, pg);
      if (!clicked) {
        console.log('No next tracker page control found; stopping pagination.');
        break;
      }
      console.log(`\n=== Tracker page ${pg} ===`);
      await page.waitForTimeout(5000);
    }

    const currentUrl = page.url();
    if (/\/login|checkpoint|authwall/i.test(currentUrl)) {
      throw new Error('LinkedIn session appears to be expired. Run: npm run linkedin:auth');
    }

    const pageData = await page.evaluate(() => {
      const result = [];
      const normalize = (value) => (value || '').replace(/\s+/g, ' ').trim();
      const bodyText = normalize(document.body.innerText || document.body.textContent);
      const savedCountMatch = bodyText.match(/Salvas\s*[·•]\s*(\d+)/i);
      const expectedTotal = savedCountMatch ? Number.parseInt(savedCountMatch[1], 10) : null;
      const links = document.querySelectorAll('a[href*="/jobs/view/"]');
      const seen = new Set();

      links.forEach((link) => {
        const href = link.getAttribute('href');
        const m = href && href.match(/\/jobs\/view\/(\d+)/);
        if (!m) return;
        const jobId = m[1];
        if (seen.has(jobId)) return;
        seen.add(jobId);

        const textParts = [...link.querySelectorAll('p')]
          .map((node) => normalize(node.innerText || node.textContent))
          .filter(Boolean);
        if (textParts.length < 2) return;

        const title = textParts[0];
        const companyLocation = textParts[1];
        const [companyRaw, ...locationParts] = companyLocation.split(/\s*[·•]\s*/);
        const company = normalize(companyRaw);
        const location = normalize(locationParts.join(' · '));

        result.push({
          jobId,
          title,
          company,
          location,
        });
      });

      return { expectedTotal, jobs: result };
    });
    if (Number.isInteger(pageData.expectedTotal)) expectedTotal = pageData.expectedTotal;
    const jobs = pageData.jobs;

    console.log(`Found ${jobs.length} jobs`);
    jobs.forEach((j) =>
      console.log(`  [${j.jobId}] ${j.title} @ ${j.company || '-'} | ${j.location || '-'}`)
    );

    const newJobs = jobs.filter((j) => !globalSeen.has(j.jobId));
    jobs.forEach((j) => globalSeen.add(j.jobId));
    allJobs.push(...jobs);
    scannedPages.push({
      page: pg,
      found: jobs.length,
      new: newJobs.length,
      url: currentUrl,
    });

    if (expectedTotal && globalSeen.size >= expectedTotal) {
      console.log(`Reached tracker saved count (${expectedTotal}); stopping pagination.`);
      break;
    }
    if (jobs.length === 0 || (pg > 1 && newJobs.length === 0)) {
      console.log('No new jobs found; stopping pagination.');
      break;
    }
  }

  // Deduplicate
  const seen = new Set();
  const unique = allJobs.filter((j) => {
    if (seen.has(j.jobId)) return false;
    seen.add(j.jobId);
    return true;
  });

  const clean = unique.map((j) => ({
    jobId: j.jobId,
    title: j.title,
    company: j.company,
    location: j.location,
    url: `https://www.linkedin.com/jobs/view/${j.jobId}/`,
  }));

  const invalid = clean.filter((j) => !j.jobId || !j.title || !j.company || !j.url);
  if (clean.length === 0) {
    throw new Error('No saved jobs were extracted. Check the LinkedIn session or page layout.');
  }
  if (invalid.length > 0) {
    const ids = invalid.map((j) => j.jobId || '(missing id)').join(', ');
    throw new Error(`Extracted jobs with missing required fields: ${ids}`);
  }

  fs.mkdirSync(path.dirname(OUTPUT), { recursive: true });
  fs.writeFileSync(
    OUTPUT,
    JSON.stringify(
      {
        extractedAt: new Date().toISOString(),
        source: SOURCE_URL,
        mode: args.maxPages === DEEP_SCAN_MAX_PAGES ? 'all' : 'recent',
        expectedTotal,
        total: clean.length,
        scannedPages: scannedPages.length,
        pageResults: scannedPages,
        jobs: clean,
      },
      null,
      2
    )
  );
  console.log(`\n✓ ${clean.length} jobs saved to ${OUTPUT}`);

  await browser.close();
})().catch((error) => {
  console.error(`\nError: ${error.message}`);
  process.exit(1);
});
