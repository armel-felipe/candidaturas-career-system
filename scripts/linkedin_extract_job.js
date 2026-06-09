#!/usr/bin/env node

const fs = require("fs");
const path = require("path");
const readline = require("readline");
const { spawnSync } = require("child_process");

function parseArgs(argv) {
  const args = {
    url: null,
    authOnly: false,
    headless: false,
    loginPrompt: true,
    saveJob: true,
    timeoutMs: 120000,
    loginWaitMs: 300000,
  };

  for (let i = 0; i < argv.length; i += 1) {
    const item = argv[i];
    if (item === "--url") {
      args.url = argv[++i];
    } else if (item === "--auth-only") {
      args.authOnly = true;
    } else if (item === "--headless") {
      args.headless = true;
    } else if (item === "--no-login-prompt") {
      args.loginPrompt = false;
    } else if (item === "--no-save-job") {
      args.saveJob = false;
    } else if (item === "--timeout-ms") {
      args.timeoutMs = Number(argv[++i]);
    } else if (item === "--login-wait-ms") {
      args.loginWaitMs = Number(argv[++i]);
    } else if (item === "--help" || item === "-h") {
      printHelp();
      process.exit(0);
    } else {
      throw new Error(`Argumento desconhecido: ${item}`);
    }
  }

  if (!args.url && args.authOnly) {
    args.url = "https://www.linkedin.com/jobs/";
  }
  if (!args.url) {
    throw new Error("Informe a URL com --url.");
  }
  if (!Number.isFinite(args.timeoutMs) || args.timeoutMs < 10000) {
    throw new Error("--timeout-ms deve ser um número >= 10000.");
  }
  if (!Number.isFinite(args.loginWaitMs) || args.loginWaitMs < 30000) {
    throw new Error("--login-wait-ms deve ser um número >= 30000.");
  }
  return args;
}

function printHelp() {
  console.log(`Uso:
  npm run linkedin:extract -- --url "<url-da-vaga>"

Opções:
  --auth-only             Abre/valida sessão manual e sai sem extrair vaga.
  --headless              Tenta sem janela visível; se login faltar, abre login manual quando DISPLAY existir.
  --no-login-prompt       Não abre navegador visível para login manual; falha se a sessão não estiver autenticada.
  --no-save-job           Não chama scripts/save_job_description.py.
  --timeout-ms <ms>       Timeout total de navegação. Padrão: 120000.
  --login-wait-ms <ms>    Tempo para aguardar login manual via noVNC. Padrão: 300000.
`);
}

function validateLinkedInJobUrl(rawUrl) {
  let parsed;
  try {
    parsed = new URL(rawUrl);
  } catch {
    throw new Error("URL inválida.");
  }

  const host = parsed.hostname.replace(/^www\./, "");
  const isLinkedIn = host === "linkedin.com" || host.endsWith(".linkedin.com");
  const looksLikeJob = /\/jobs\//.test(parsed.pathname) || /\/job\//.test(parsed.pathname);
  if (!isLinkedIn || !looksLikeJob) {
    throw new Error("A URL precisa ser uma página de vaga do LinkedIn.");
  }
  return parsed.toString();
}

function slugify(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 80) || "linkedin_vaga";
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

function firstMatch(text, patterns) {
  for (const pattern of patterns) {
    const match = text.match(pattern);
    if (match && match[1]) {
      const value = cleanText(match[1]);
      if (value) return value;
    }
  }
  return "";
}

async function promptEnter(message) {
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  await new Promise((resolve) => {
    rl.question(message, () => resolve());
  });
  rl.close();
}

async function textFromFirst(page, selectors) {
  for (const selector of selectors) {
    const locator = page.locator(selector).first();
    try {
      if (await locator.count()) {
        const text = cleanText(await locator.innerText({ timeout: 5000 }));
        if (text) return text;
      }
    } catch {
      // Try the next selector.
    }
  }
  return "";
}

async function clickExpandableButtons(page) {
  const labels = [
    "See more",
    "Show more",
    "Ver mais",
    "Mostrar mais",
    "Exibir mais",
    "Ler mais",
  ];

  for (const label of labels) {
    try {
      const button = page.getByRole("button", { name: new RegExp(label, "i") }).first();
      if (await button.count()) {
        await button.click({ timeout: 2500 });
        await page.waitForTimeout(700);
      }
    } catch {
      // LinkedIn changes markup frequently; missing expand buttons are acceptable.
    }
  }
}

async function hasLoginWall(page) {
  const url = page.url();
  if (/\/login|checkpoint|authwall|uas\/login/i.test(url)) return true;
  const body = cleanText(await page.locator("body").innerText({ timeout: 10000 }).catch(() => ""));
  return /Sign in|Entrar|Join LinkedIn|Cadastre-se|Security verification|verificação de segurança/i.test(body)
    && !/About the job|Sobre a vaga|Descrição da vaga|Responsabilidades/i.test(body);
}

async function extractJob(page) {
  await clickExpandableButtons(page);

  const title = await textFromFirst(page, [
    ".job-details-jobs-unified-top-card__job-title",
    ".top-card-layout__title",
    "h1",
  ]);

  const company = await textFromFirst(page, [
    ".job-details-jobs-unified-top-card__company-name a",
    ".job-details-jobs-unified-top-card__company-name",
    ".topcard__org-name-link",
    ".top-card-layout__card a",
  ]);

  const location = await textFromFirst(page, [
    ".job-details-jobs-unified-top-card__primary-description-container",
    ".job-details-jobs-unified-top-card__bullet",
    ".topcard__flavor--bullet",
  ]);

  let description = await textFromFirst(page, [
    ".jobs-description__content .jobs-box__html-content",
    ".jobs-description-content__text",
    ".jobs-description__content",
    "#job-details",
    ".description__text",
  ]);

  if (!description || description.length < 300) {
    const bodyText = cleanText(await page.locator("body").innerText({ timeout: 10000 }).catch(() => ""));
    const marker = bodyText.search(/About the job|Sobre a vaga|Descrição da vaga|Responsabilidades|Requirements|Requisitos/i);
    if (marker >= 0) {
      description = cleanText(bodyText.slice(marker));
    }
  }

  const inferred = inferTitleAndCompany(title, company, description);
  description = trimLinkedInNoise(description);
  const inferredLocation = inferLocation(location, description);

  return {
    title: inferred.title || "Cargo LinkedIn",
    company: inferred.company || "Empresa LinkedIn",
    location: inferredLocation,
    description,
  };
}

function inferTitleAndCompany(title, company, description) {
  const normalizedDescription = cleanText(description);
  const genericTitle = !title || title === "Cargo LinkedIn";
  const genericCompany = !company || company === "Empresa LinkedIn";
  const result = {
    title: genericTitle ? "" : cleanText(title),
    company: genericCompany ? "" : cleanText(company),
  };
  if (!isPlausibleLabel(result.title, 120)) result.title = "";
  if (!isPlausibleLabel(result.company, 80)) result.company = "";

  const lines = normalizedDescription
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);

  const meaningful = lines.filter((line) => !/^(Sobre a vaga|About the job|Descrição da vaga)$/i.test(line));
  const firstLine = meaningful[0] || "";
  if (!result.title) {
    result.title = firstMatch(normalizedDescription, [
      /\bPosition:\s*([^\n]+)/i,
      /\bVeja nossa oportunidade para\s+([^\n.!]+)/i,
      /\bOportunidade para\s+([^\n.!]+)/i,
      /\bVaga para\s+([^\n.!]+)/i,
      /\bOpportunity for\s+([^\n.!]+)/i,
      /\bOpening for\s+([^\n.!]+)/i,
      /\bWe are looking for an?\s+([A-Z][^.\n,;]+?)(?:\s+with|\s+who|,|\.|\n)/i,
      /\bWe are hiring an?\s+([A-Z][^.\n,;]+?)(?:\s+with|\s+who|,|\.|\n)/i,
      /\bseeking an?\s+(?:standout\s+)?([A-Z][^.\n,;]+?)(?:\s+to\s+|\s+who|,|\.|\n)/i,
      /\bAs\s+([^,\n]+(?:,\s*[^,\n]+)?),\s+you\s+will\b/i,
    ]);
  }
  if (!result.title) {
    const roleLine = meaningful.find((line) => isPlausibleLabel(line, 120) && /\b(gerente|manager|director|head|coordinator|coordenador|analyst|analista|specialist|especialista|engineer|engenheiro)\b/i.test(line));
    if (roleLine) result.title = roleLine;
  }

  const dashMatch = firstLine.match(/^(.+?)\s+[-–—]\s+(.+)$/);
  if (dashMatch) {
    if (!result.title) result.title = dashMatch[1].trim();
    if (!result.company) result.company = dashMatch[2].trim();
  } else if (!result.title && firstLine && firstLine.length <= 120) {
    result.title = firstLine;
  }
  if (!isPlausibleLabel(result.title, 120)) result.title = "";
  if (!isPlausibleLabel(result.company, 80)) result.company = "";

  if (!result.company) {
    result.company = firstMatch(normalizedDescription, [
      /\bJunte-se [^\n]*?\b(?:na|no)\s+([A-Z][A-Za-zÀ-ÿ0-9&.\- ]{1,60})(?:[!,.]|\s|$)/i,
      /\bJoin [^\n]*?\bat\s+([A-Z][A-Za-z0-9&.\- ]{1,60})(?:[!,.]|\s|$)/i,
      /(?:^|\n)Na\s+([A-Z][A-Za-zÀ-ÿ0-9&.\- ]{1,60})(?:,|\s)/,
      /(?:^|\n)No\s+([A-Z][A-Za-zÀ-ÿ0-9&.\- ]{1,60})(?:,|\s)/,
      /\bAbout\s+([A-Z][A-Za-z0-9&.\s-]{1,60})\n/,
      /\b([A-Z][A-Za-zÀ-ÿ0-9&.\- ]{1,60})\s+no Brasil\b/,
      /\b([A-Z][A-Za-zÀ-ÿ0-9&.\- ]{1,60})\s+combina os mundos\b/i,
      /\bWho we are\s+([A-Z][A-Za-z0-9&.\- ]{2,40})\s+is\b/i,
      /(?:^|\n)([A-Z][A-Za-z0-9&.\- ]{2,40})\s+is\s+(?:a|an|the)\b/,
      /\bCompany Description\b[\s\S]{0,400}?\b([A-Z][A-Za-z0-9&.\- ]{2,40})\s+is\b/,
      /(?:^|\s)(?:a|o|na|no)\s+([A-Z][A-Za-zÀ-ÿ0-9&.\- ]{2,40})\s+(?:é|e)(?:\s|,|\.)/,
    ]);
  }
  if (!isPlausibleLabel(result.company, 80)) result.company = "";

  if (!result.company && /\bAt Monks\b|\bAbout Monks\b/i.test(description)) {
    result.company = "Monks";
  }

  if (!isPlausibleLabel(result.title, 120)) result.title = "";
  if (!isPlausibleLabel(result.company, 80)) result.company = "";

  return result;
}

function inferLocation(location, description) {
  const current = cleanText(location);
  if (current) return current;

  const normalizedDescription = cleanText(description);
  const inferred = firstMatch(normalizedDescription, [
    /\bLocal de trabalho\s*[–:-]\s*([^\n]+)/i,
    /\bLocation\s*[–:-]\s*([^\n]+)/i,
    /\bModelo de trabalho\s*[–:-]\s*([^\n]+)/i,
  ]);
  return inferred || "";
}

function isPlausibleLabel(value, maxLength) {
  const text = cleanText(value);
  if (!text || text.length > maxLength) return false;
  if (/^(the role|the job|the position|a vaga|sobre a vaga|descrição da vaga|descricao da vaga)$/i.test(text)) return false;
  if (/^(mexico|méxico|brazil|brasil|chile|peru|colombia|costa rica|sao paulo|são paulo)$/i.test(text)) return false;
  if (/^(cargo linkedin|empresa linkedin)$/i.test(text)) return false;
  if (/[:;]/.test(text) && text.split(/\s+/).length > 6) return false;
  if (text.split(/\s+/).length > 14) return false;
  if (/[.!?]\s/.test(text)) return false;
  return true;
}

function trimLinkedInNoise(description) {
  let text = cleanText(description);
  const cutMarkers = [
    "\nAtive um alerta para vagas semelhantes",
    "\nVeja como sua candidatura se compara",
    "\nPessoas que clicaram em Candidate-se",
    "\nEstatísticas exclusivas",
    "\nMais vagas",
    "\nProcurando um talento?",
  ];

  let cutAt = -1;
  for (const marker of cutMarkers) {
    const index = text.indexOf(marker);
    if (index >= 0 && (cutAt < 0 || index < cutAt)) {
      cutAt = index;
    }
  }
  if (cutAt >= 0) {
    text = text.slice(0, cutAt);
  }
  return cleanText(text);
}

function writeArtifacts(job, sourceUrl) {
  const root = process.cwd();
  const inboxDir = path.join(root, "inbox", "job_descriptions");
  const stateDir = path.join(root, ".career-state");
  fs.mkdirSync(inboxDir, { recursive: true });
  fs.mkdirSync(stateDir, { recursive: true });

  const companySlug = slugify(job.company);
  const titleSlug = slugify(job.title);
  const stamp = new Date().toISOString().replace(/[-:]/g, "").slice(0, 15);
  const outputPath = path.join(inboxDir, `linkedin_${companySlug}_${titleSlug}_${stamp}.md`);

  const markdown = [
    `# ${job.title}`,
    "",
    `Empresa: ${job.company}`,
    job.location ? `Localização: ${job.location}` : null,
    `Fonte: ${sourceUrl}`,
    `Extraído em: ${new Date().toISOString()}`,
    "",
    "## Descrição da vaga",
    "",
    job.description,
    "",
  ].filter((line) => line !== null).join("\n");

  fs.writeFileSync(outputPath, markdown, "utf8");

  const statePath = path.join(stateDir, "linkedin_job_extract.json");
  const state = {
    source_url: sourceUrl,
    company: job.company,
    role: job.title,
    location: job.location,
    output_path: path.relative(root, outputPath),
    extracted_at: new Date().toISOString(),
    description_chars: job.description.length,
  };
  fs.writeFileSync(statePath, `${JSON.stringify(state, null, 2)}\n`, "utf8");

  return { outputPath, statePath, state };
}

function saveCanonicalJob(job, outputPath) {
  const result = spawnSync("python3", [
    "scripts/save_job_description.py",
    "--company",
    job.company,
    "--role",
    job.title,
    "--text-file",
    outputPath,
  ], {
    cwd: process.cwd(),
    encoding: "utf8",
  });

  if (result.status !== 0) {
    const details = [result.stdout, result.stderr].filter(Boolean).join("\n").trim();
    throw new Error(`Falha ao registrar vaga no fluxo canônico.\n${details}`);
  }
  return cleanText(result.stdout);
}

function canOpenHeadfulBrowser() {
  if (process.platform === "linux") {
    return Boolean(process.env.DISPLAY || process.env.WAYLAND_DISPLAY);
  }
  return true;
}

function loadBrowserGatewayEnv() {
  if (process.platform !== "linux") {
    return null;
  }

  const envPath = path.join(process.cwd(), ".career-state", "browser-gateway", "env");
  if (!fs.existsSync(envPath)) {
    return null;
  }

  const loaded = {};
  const lines = fs.readFileSync(envPath, "utf8").split(/\r?\n/);
  for (const line of lines) {
    const match = line.match(/^([A-Z0-9_]+)=(.*)$/);
    if (match) {
      loaded[match[1]] = match[2];
    }
  }

  if (process.env.DISPLAY || process.env.WAYLAND_DISPLAY) {
    return Object.keys(loaded).length ? loaded : null;
  }

  if (loaded.DISPLAY) {
    process.env.DISPLAY = loaded.DISPLAY;
  }
  return loaded;
}

async function launchContext(chromium, userDataDir, headless) {
  return chromium.launchPersistentContext(userDataDir, {
    headless,
    viewport: { width: 1366, height: 900 },
    locale: "pt-BR",
  });
}

async function openJobPage(context, url, timeoutMs) {
  const page = context.pages()[0] || await context.newPage();
  page.setDefaultTimeout(20000);
  await page.goto(url, { waitUntil: "domcontentloaded", timeout: timeoutMs });
  await page.waitForTimeout(2000);
  return page;
}

async function waitForManualLogin(page, url, args) {
  const deadline = Date.now() + args.loginWaitMs;
  while (Date.now() < deadline) {
    await page.waitForTimeout(3000);
    if (!(await hasLoginWall(page))) {
      try {
        if (page.url() !== url) {
          await page.goto(url, { waitUntil: "domcontentloaded", timeout: args.timeoutMs });
          await page.waitForTimeout(2000);
        }
      } catch {
        // If navigation back to the job fails, keep the authenticated page and let the caller decide.
      }
      return true;
    }
  }
  return false;
}

async function ensureLoggedInPage(chromium, userDataDir, url, args) {
  const gatewayEnv = loadBrowserGatewayEnv();
  let context = await launchContext(chromium, userDataDir, args.headless);
  let page = await openJobPage(context, url, args.timeoutMs);

  if (!(await hasLoginWall(page))) {
    return { context, page };
  }

  if (!args.loginPrompt) {
    await context.close();
    throw new Error("LinkedIn exige login e --no-login-prompt foi usado.");
  }

  if (!canOpenHeadfulBrowser()) {
    await context.close();
    throw new Error("LinkedIn exige login, mas não há DISPLAY/WAYLAND_DISPLAY para abrir navegador visível. Rode `npm run linkedin:browser:start` e acesse o noVNC antes de repetir.");
  }

  if (args.headless) {
    await context.close();
    if (gatewayEnv && gatewayEnv.NOVNC_URL) {
      console.log(`Login manual necessário. Gateway noVNC detectado: ${gatewayEnv.NOVNC_URL}`);
    }
    context = await launchContext(chromium, userDataDir, false);
    page = await openJobPage(context, url, args.timeoutMs);
  }

  if (await hasLoginWall(page)) {
    const loginTarget = gatewayEnv && gatewayEnv.NOVNC_URL
      ? `acesse ${gatewayEnv.NOVNC_URL} para ver o navegador`
      : "faça login no navegador aberto";
    console.log(`LinkedIn exige login. ${loginTarget}; vou aguardar até ${Math.round(args.loginWaitMs / 1000)}s.`);
    const loggedIn = await waitForManualLogin(page, url, args);
    if (!loggedIn && process.stdin.isTTY) {
      await promptEnter("Pressione Enter depois que a página da vaga estiver visível...");
      await page.goto(url, { waitUntil: "domcontentloaded", timeout: args.timeoutMs });
      await page.waitForTimeout(2000);
    }
  }

  if (await hasLoginWall(page)) {
    await context.close();
    throw new Error("Login/verificação do LinkedIn não foi concluído ou a página continua bloqueada.");
  }

  return { context, page };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const url = validateLinkedInJobUrl(args.url);

  let chromium;
  try {
    ({ chromium } = require("playwright"));
  } catch {
    throw new Error("Dependência ausente: instale com `npm install` antes de usar esta skill.");
  }

  const userDataDir = path.join(process.cwd(), ".career-state", "browser", "linkedin");
  fs.mkdirSync(userDataDir, { recursive: true });

  const { context, page } = await ensureLoggedInPage(chromium, userDataDir, url, args);

  try {
    if (args.authOnly) {
      console.log(JSON.stringify({
        ok: true,
        authenticated: true,
        user_data_dir: path.relative(process.cwd(), userDataDir),
        current_url: page.url(),
      }, null, 2));
      return;
    }

    const job = await extractJob(page);
    job.description = cleanText(job.description);

    if (!job.description || job.description.length < 300) {
      throw new Error("Não foi possível extrair uma descrição substantiva da vaga.");
    }
    if (/Sign in|Entrar|Join LinkedIn|Cadastre-se|Security verification|verificação de segurança/i.test(job.description.slice(0, 1000))) {
      throw new Error("O texto extraído parece ser login/verificação, não a descrição da vaga.");
    }

    const { outputPath, state } = writeArtifacts(job, url);
    let saveOutput = "";
    if (args.saveJob) {
      saveOutput = saveCanonicalJob(job, outputPath);
    }

    console.log(JSON.stringify({
      ok: true,
      company: job.company,
      role: job.title,
      location: job.location,
      description_chars: job.description.length,
      output_path: state.output_path,
      canonical_save_executed: args.saveJob,
      canonical_save_output: saveOutput,
    }, null, 2));
  } finally {
    await context.close();
  }
}

main().catch((error) => {
  console.error(JSON.stringify({
    ok: false,
    error: error.message,
  }, null, 2));
  process.exit(1);
});
