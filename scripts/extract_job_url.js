#!/usr/bin/env node

const fs = require("fs");
const path = require("path");
const { spawnSync } = require("child_process");

function parseArgs(argv) {
  const args = {
    url: "",
    fallbackCompany: "",
    fallbackRole: "",
    timeoutMs: 90000,
  };

  for (let i = 0; i < argv.length; i += 1) {
    const item = argv[i];
    if (item === "--url") {
      args.url = argv[++i] || "";
    } else if (item === "--fallback-company") {
      args.fallbackCompany = cleanText(argv[++i] || "");
    } else if (item === "--fallback-role") {
      args.fallbackRole = cleanText(argv[++i] || "");
    } else if (item === "--timeout-ms") {
      args.timeoutMs = Number(argv[++i]);
    } else if (item === "--help" || item === "-h") {
      printHelp();
      process.exit(0);
    } else {
      throw new Error(`Argumento desconhecido: ${item}`);
    }
  }

  if (!args.url) throw new Error("Informe a URL com --url.");
  if (!Number.isFinite(args.timeoutMs) || args.timeoutMs < 10000) {
    throw new Error("--timeout-ms deve ser um número >= 10000.");
  }
  return args;
}

function printHelp() {
  console.log(`Uso:
  npm run url:extract -- --url "<url-da-vaga>"

Opções:
  --fallback-company <texto>  Empresa fallback quando a página não trouxer metadado bom.
  --fallback-role <texto>     Cargo fallback quando a página não trouxer metadado bom.
  --timeout-ms <ms>           Timeout total. Padrão: 90000.
`);
}

function cleanText(value) {
  return String(value || "")
    .replace(/\r/g, "")
    .replace(/\u00a0/g, " ")
    .split("\n")
    .map((line) => line.trim())
    .join("\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function slugify(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 80) || "vaga";
}

function validateUrl(rawUrl) {
  let parsed;
  try {
    parsed = new URL(rawUrl);
  } catch {
    throw new Error("URL inválida.");
  }
  if (!/^https?:$/.test(parsed.protocol)) {
    throw new Error("A URL precisa usar http ou https.");
  }
  const host = parsed.hostname.replace(/^www\./, "");
  if (host === "linkedin.com" || host.endsWith(".linkedin.com")) {
    throw new Error("LinkedIn deve usar o intake dedicado: linkedin-job ou linkedin-post.");
  }
  return parsed.toString();
}

function projectRoot() {
  return path.resolve(__dirname, "..");
}

function statePath(root) {
  return path.join(root, ".career-state", "url_job_extract.json");
}

function saveState(root, payload) {
  const output = statePath(root);
  fs.mkdirSync(path.dirname(output), { recursive: true });
  fs.writeFileSync(output, JSON.stringify(payload, null, 2) + "\n", "utf8");
}

function portalName(host) {
  const normalized = String(host || "").replace(/^www\./, "");
  if (normalized.includes("gupy")) return "gupy";
  if (normalized.includes("inhire")) return "inhire";
  if (normalized.includes("ashby")) return "ashby";
  if (normalized.includes("greenhouse")) return "greenhouse";
  if (normalized.includes("lever")) return "lever";
  if (normalized.includes("workday")) return "workday";
  return normalized;
}

function candidateFromTitle(title) {
  const cleaned = cleanText(title);
  if (!cleaned) return { role: "", company: "" };
  const separators = [" | ", " - ", " — ", " @ "];
  for (const separator of separators) {
    if (!cleaned.includes(separator)) continue;
    const [left, right] = cleaned.split(separator).map((part) => cleanText(part));
    if (left && right) {
      return { role: left, company: right };
    }
  }
  return { role: cleaned, company: "" };
}

function normalizeCompanyFallback(host) {
  const base = String(host || "")
    .replace(/^www\./, "")
    .split(".")
    .slice(0, -1)
    .join(" ");
  return cleanText(base.replace(/[-_]+/g, " "));
}

async function textFromFirst(page, selectors) {
  for (const selector of selectors) {
    const locator = page.locator(selector).first();
    try {
      if (await locator.count()) {
        const text = cleanText(await locator.innerText({ timeout: 3000 }));
        if (text) return text;
      }
    } catch {
      // Try next selector.
    }
  }
  return "";
}

async function metaContent(page, name) {
  try {
    const locator = page.locator(`meta[name="${name}"], meta[property="${name}"]`).first();
    if (await locator.count()) {
      return cleanText((await locator.getAttribute("content")) || "");
    }
  } catch {
    return "";
  }
  return "";
}

async function jsonLdSnapshot(page) {
  try {
    return await page.$$eval('script[type="application/ld+json"]', (nodes) =>
      nodes
        .map((node) => {
          try {
            return JSON.parse(node.textContent || "");
          } catch {
            return null;
          }
        })
        .filter(Boolean)
    );
  } catch {
    return [];
  }
}

function firstTruthy(values) {
  for (const value of values) {
    const cleaned = cleanText(value);
    if (cleaned) return cleaned;
  }
  return "";
}

function flattenJsonLd(items) {
  const flat = [];
  const visit = (item) => {
    if (!item) return;
    if (Array.isArray(item)) {
      item.forEach(visit);
      return;
    }
    if (typeof item !== "object") return;
    flat.push(item);
    if (Array.isArray(item["@graph"])) item["@graph"].forEach(visit);
  };
  visit(items);
  return flat;
}

async function extractLargestJobSection(page) {
  const result = await page.evaluate(() => {
    const selectors = [
      "main",
      "article",
      "[role='main']",
      ".job-description",
      ".description",
      ".posting",
      ".content",
      ".job-posting",
      ".opportunity-description",
    ];

    const keywordRe = /responsibil|requisit|qualifica|about the job|descri[cç][aã]o|atividades|what you'll do|requirements|job description|você vai|you will/i;
    const seen = new Set();
    const candidates = [];

    for (const selector of selectors) {
      document.querySelectorAll(selector).forEach((node) => {
        if (!node || seen.has(node)) return;
        seen.add(node);
        const text = (node.innerText || "").replace(/\u00a0/g, " ").trim();
        if (text.length < 300) return;
        const score = text.length + (keywordRe.test(text) ? 5000 : 0);
        candidates.push({ text, score });
      });
    }

    if (!candidates.length) {
      document.querySelectorAll("section, div").forEach((node) => {
        const text = (node.innerText || "").replace(/\u00a0/g, " ").trim();
        if (text.length < 600) return;
        const score = text.length + (keywordRe.test(text) ? 5000 : 0);
        candidates.push({ text, score });
      });
    }

    candidates.sort((a, b) => b.score - a.score);
    return candidates[0] ? candidates[0].text : "";
  });
  return cleanText(result);
}

async function extractJob(page, url, args) {
  const parsed = new URL(url);
  const host = parsed.hostname.replace(/^www\./, "");
  const portal = portalName(host);

  const title = cleanText(await page.title());
  const h1 = await textFromFirst(page, [
    "h1",
    "[data-testid='job-title']",
    "[data-qa='job-title']",
    ".posting-headline h2",
    "[data-automation-id='jobPostingHeader']",
  ]);
  const companyText = await textFromFirst(page, [
    "[data-testid='company-name']",
    "[data-qa='company-name']",
    ".company-name",
    ".posting-categories .sort-by-time",
    "[data-automation-id='company']",
    ".text-company-name",
  ]);
  const descriptionText = await textFromFirst(page, [
    "[data-testid='job-description']",
    "[data-qa='job-description']",
    ".job-description",
    ".posting-page .content",
    ".content .section-wrapper",
    "[data-automation-id='jobPostingDescription']",
  ]);
  const ogTitle = await metaContent(page, "og:title");
  const metaDescription = await metaContent(page, "description");
  const ogDescription = await metaContent(page, "og:description");
  const jsonLd = flattenJsonLd(await jsonLdSnapshot(page));
  const jobPosting = jsonLd.find((item) => String(item["@type"] || "").includes("JobPosting")) || {};

  const titleCandidate = candidateFromTitle(firstTruthy([h1, ogTitle, title]));
  const role = firstTruthy([
    args.fallbackRole,
    cleanText(jobPosting.title),
    h1,
    titleCandidate.role,
  ]);
  const company = firstTruthy([
    args.fallbackCompany,
    cleanText(jobPosting.hiringOrganization && jobPosting.hiringOrganization.name),
    companyText,
    titleCandidate.company,
    normalizeCompanyFallback(host),
  ]);
  const description = firstTruthy([
    cleanText(jobPosting.description),
    descriptionText,
    await extractLargestJobSection(page),
    metaDescription,
    ogDescription,
  ]);

  return {
    url,
    host,
    portal,
    title,
    role,
    company,
    description,
    meta_description: metaDescription,
    og_description: ogDescription,
  };
}

function composeSavedText(data) {
  const parts = [
    `Fonte: ${data.url}`,
    `Portal: ${data.portal}`,
    `Empresa: ${data.company}`,
    `Cargo: ${data.role}`,
    "",
    data.description,
  ];
  return cleanText(parts.join("\n"));
}

function saveJobDescription(root, data) {
  const command = [
    path.join(root, "scripts", "python.sh"),
    "scripts/save_job_description.py",
    "--company",
    data.company,
    "--role",
    data.role,
    "--stdin",
  ];
  const completed = spawnSync(command[0], command.slice(1), {
    cwd: root,
    input: composeSavedText(data),
    encoding: "utf8",
  });
  if (completed.status !== 0) {
    throw new Error((completed.stderr || completed.stdout || "Falha ao salvar descricao da vaga.").trim());
  }
  const match = String(completed.stdout || "").match(/Job description saved:\s*(.+)/);
  if (!match) {
    throw new Error("Extracao terminou, mas o caminho salvo da descricao nao foi encontrado.");
  }
  return cleanText(match[1]);
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const url = validateUrl(args.url);
  let chromium;
  try {
    ({ chromium } = require("playwright"));
  } catch (error) {
    throw new Error(`Playwright indisponível: ${error.message}`);
  }

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  page.setDefaultTimeout(args.timeoutMs);

  try {
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: args.timeoutMs });
    await page.waitForLoadState("networkidle", { timeout: 15000 }).catch(() => {});
    await page.waitForTimeout(1200);
    const data = await extractJob(page, url, args);
    if (!data.role) throw new Error("Nao foi possivel inferir o cargo da vaga.");
    if (!data.company) throw new Error("Nao foi possivel inferir a empresa da vaga.");
    if (!data.description || data.description.length < 500) {
      throw new Error(`Descricao extraida muito curta (${data.description.length} chars).`);
    }
    const root = projectRoot();
    const outputPath = saveJobDescription(root, data);
    const payload = {
      status: "ok",
      source_url: url,
      host: data.host,
      portal: data.portal,
      company: data.company,
      role: data.role,
      output_path: outputPath,
      description_chars: data.description.length,
      extracted_at: new Date().toISOString(),
    };
    saveState(root, payload);
    console.log(JSON.stringify(payload, null, 2));
  } finally {
    await page.close().catch(() => {});
    await browser.close().catch(() => {});
  }
}

main().catch((error) => {
  console.error(String(error && error.message ? error.message : error));
  process.exit(1);
});
