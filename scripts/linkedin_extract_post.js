#!/usr/bin/env node

const fs = require("fs");
const path = require("path");
const { spawnSync } = require("child_process");

function parseArgs(argv) {
  const args = {
    url: null,
    company: null,
    role: null,
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
    } else if (item === "--company") {
      args.company = argv[++i];
    } else if (item === "--role") {
      args.role = argv[++i];
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
  npm run linkedin:post:extract -- --url "<url-da-postagem>" --company "<empresa>" --role "<cargo>"

Opções:
  --company <nome>        Empresa da vaga quando a postagem não tiver link de vaga.
  --role <cargo>          Cargo da vaga quando a postagem não tiver link de vaga.
  --headless              Tenta sem janela visível.
  --no-login-prompt       Falha se a sessão LinkedIn não estiver autenticada.
  --no-save-job           Não chama scripts/save_job_description.py.
  --timeout-ms <ms>       Timeout total de navegação. Padrão: 120000.
  --login-wait-ms <ms>    Tempo para aguardar login manual. Padrão: 300000.
`);
}

function validateLinkedInPostUrl(rawUrl) {
  let parsed;
  try {
    parsed = new URL(rawUrl);
  } catch {
    throw new Error("URL inválida.");
  }

  const host = parsed.hostname.replace(/^www\./, "");
  const isLinkedIn = host === "linkedin.com" || host.endsWith(".linkedin.com");
  const looksLikePost = [
    /\/feed\/update\//,
    /\/posts\//,
    /\/pulse\//,
    /\/in\/[^/]+\/recent-activity\//,
  ].some((pattern) => pattern.test(parsed.pathname));

  if (!isLinkedIn || !looksLikePost) {
    throw new Error("A URL precisa ser uma postagem do LinkedIn.");
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
    .slice(0, 80) || "linkedin_post";
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

async function hasLoginWall(page) {
  const url = page.url();
  if (/\/login|checkpoint|authwall|uas\/login/i.test(url)) return true;
  const body = cleanText(await page.locator("body").innerText({ timeout: 10000 }).catch(() => ""));
  return /Sign in|Entrar|Join LinkedIn|Cadastre-se|Security verification|verificação de segurança/i.test(body)
    && !/Like|Comentar|Compartilhar|Reações|Comments|Reposts/i.test(body);
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
    for (const role of ["button", "link"]) {
      try {
        const locator = page.getByRole(role, { name: new RegExp(label, "i") }).first();
        if (await locator.count()) {
          await locator.click({ timeout: 2500 });
          await page.waitForTimeout(700);
        }
      } catch {
        // LinkedIn markup changes frequently; missing expand controls are acceptable.
      }
    }
  }
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

async function extractLinks(page) {
  const links = await page.locator("a[href]").evaluateAll((anchors) => (
    anchors.map((anchor) => ({
      href: anchor.href,
      text: (anchor.innerText || anchor.textContent || "").trim(),
    }))
  )).catch(() => []);

  const seen = new Set();
  return links
    .map((item) => ({
      href: normalizeLinkedInRedirect(item.href),
      text: cleanText(item.text),
    }))
    .filter((item) => {
      if (!item.href || seen.has(item.href)) return false;
      seen.add(item.href);
      return true;
    });
}

function normalizeLinkedInRedirect(rawHref) {
  if (!rawHref) return "";
  try {
    const parsed = new URL(rawHref);
    const target = parsed.searchParams.get("url");
    if (/linkedin\.com\/safety\/go\?/i.test(parsed.href) && target) {
      return decodeURIComponent(target);
    }
    return parsed.toString();
  } catch {
    return rawHref;
  }
}

function findJobLink(links) {
  const found = links.find((item) => {
    try {
      const parsed = new URL(item.href);
      const host = parsed.hostname.replace(/^www\./, "");
      return (host === "linkedin.com" || host.endsWith(".linkedin.com"))
        && (/\/jobs\//.test(parsed.pathname) || /\/job\//.test(parsed.pathname));
    } catch {
      return false;
    }
  });
  return found ? found.href : "";
}

async function extractPost(page) {
  await clickExpandableButtons(page);
  await page.waitForTimeout(1000);

  const author = await textFromFirst(page, [
    ".update-components-actor__name",
    ".feed-shared-actor__name",
    ".update-components-actor__title",
    "main h1",
  ]);

  let postText = await textFromFirst(page, [
    ".update-components-text",
    ".feed-shared-update-v2__description",
    ".feed-shared-inline-show-more-text",
    ".break-words",
    "article",
    "main",
  ]);

  if (!postText || postText.length < 120) {
    postText = cleanText(await page.locator("body").innerText({ timeout: 10000 }).catch(() => ""));
  }

  return {
    author,
    text: trimPostNoise(postText),
    links: await extractLinks(page),
  };
}

function trimPostNoise(text) {
  let value = cleanText(text);
  const cutMarkers = [
    "\nReações",
    "\nComentários",
    "\nCompartilhe",
    "\nLike",
    "\nComment",
    "\nRepost",
    "\nSend",
  ];
  let cutAt = -1;
  for (const marker of cutMarkers) {
    const index = value.indexOf(marker);
    if (index >= 0 && (cutAt < 0 || index < cutAt)) {
      cutAt = index;
    }
  }
  if (cutAt >= 0) {
    value = value.slice(0, cutAt);
  }
  return cleanText(value);
}

function writePostArtifact(post, sourceUrl) {
  const root = process.cwd();
  const outputDir = path.join(root, "inbox", "linkedin_posts");
  fs.mkdirSync(outputDir, { recursive: true });

  const stamp = new Date().toISOString().replace(/[-:]/g, "").slice(0, 15);
  const authorSlug = slugify(post.author || "autor");
  const outputPath = path.join(outputDir, `linkedin_post_${authorSlug}_${stamp}.md`);
  const linkLines = post.links.map((item) => `- ${item.text ? `${item.text}: ` : ""}${item.href}`);

  const markdown = [
    "# LinkedIn post",
    "",
    post.author ? `Autor: ${post.author}` : null,
    `Fonte: ${sourceUrl}`,
    `Extraído em: ${new Date().toISOString()}`,
    "",
    "## Texto",
    "",
    post.text,
    "",
    "## Links",
    "",
    linkLines.length ? linkLines.join("\n") : "- nenhum link capturado",
    "",
  ].filter((line) => line !== null).join("\n");

  fs.writeFileSync(outputPath, markdown, "utf8");
  return outputPath;
}

function writeJobFromPost(post, args, sourceUrl) {
  const company = cleanText(args.company || "");
  const role = cleanText(args.role || "");
  if (!company || !role) {
    throw new Error("Postagem sem link de vaga detectado. Informe --company e --role para salvar a descrição com segurança.");
  }

  const root = process.cwd();
  const inboxDir = path.join(root, "inbox", "job_descriptions");
  fs.mkdirSync(inboxDir, { recursive: true });
  const stamp = new Date().toISOString().replace(/[-:]/g, "").slice(0, 15);
  const outputPath = path.join(inboxDir, `linkedin_post_${slugify(company)}_${slugify(role)}_${stamp}.md`);

  const markdown = [
    `# ${role}`,
    "",
    `Empresa: ${company}`,
    `Fonte: ${sourceUrl}`,
    `Origem: postagem LinkedIn`,
    `Extraído em: ${new Date().toISOString()}`,
    "",
    "## Descrição da vaga",
    "",
    post.text,
    "",
  ].join("\n");

  fs.writeFileSync(outputPath, markdown, "utf8");
  return {
    outputPath,
    job: {
      company,
      role,
      description: post.text,
    },
  };
}

function saveCanonicalJob(job, outputPath) {
  const result = spawnSync("python3", [
    "scripts/save_job_description.py",
    "--company",
    job.company,
    "--role",
    job.role,
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

function delegateToJobExtractor(jobUrl, args) {
  const delegatedArgs = [
    "scripts/linkedin_extract_job.js",
    "--url",
    jobUrl,
    "--timeout-ms",
    String(args.timeoutMs),
  ];
  if (!args.loginPrompt) delegatedArgs.push("--no-login-prompt");
  if (args.headless) delegatedArgs.push("--headless");
  if (!args.saveJob) delegatedArgs.push("--no-save-job");

  const result = spawnSync("node", delegatedArgs, {
    cwd: process.cwd(),
    encoding: "utf8",
  });
  if (result.status !== 0) {
    const details = [result.stdout, result.stderr].filter(Boolean).join("\n").trim();
    throw new Error(`Falha ao extrair link de vaga encontrado na postagem.\n${details}`);
  }
  return cleanText(result.stdout);
}

function writeState(state) {
  const root = process.cwd();
  const stateDir = path.join(root, ".career-state");
  fs.mkdirSync(stateDir, { recursive: true });
  const statePath = path.join(stateDir, "linkedin_post_extract.json");
  fs.writeFileSync(statePath, `${JSON.stringify(state, null, 2)}\n`, "utf8");
  return statePath;
}

function canOpenHeadfulBrowser() {
  if (process.platform === "linux") {
    return Boolean(process.env.DISPLAY || process.env.WAYLAND_DISPLAY);
  }
  return true;
}

async function launchContext(chromium, userDataDir, headless) {
  return chromium.launchPersistentContext(userDataDir, {
    headless,
    viewport: { width: 1366, height: 900 },
    locale: "pt-BR",
  });
}

async function openPage(context, url, timeoutMs) {
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
      if (page.url() !== url) {
        await page.goto(url, { waitUntil: "domcontentloaded", timeout: args.timeoutMs }).catch(() => {});
        await page.waitForTimeout(2000);
      }
      return true;
    }
  }
  return false;
}

async function ensureLoggedInPage(chromium, userDataDir, url, args) {
  let context = await launchContext(chromium, userDataDir, args.headless);
  let page = await openPage(context, url, args.timeoutMs);

  if (!(await hasLoginWall(page))) {
    return { context, page };
  }

  if (!args.loginPrompt) {
    await context.close();
    throw new Error("LinkedIn exige login e --no-login-prompt foi usado.");
  }
  if (!canOpenHeadfulBrowser()) {
    await context.close();
    throw new Error("LinkedIn exige login, mas não há DISPLAY/WAYLAND_DISPLAY para abrir navegador visível.");
  }

  if (args.headless) {
    await context.close();
    context = await launchContext(chromium, userDataDir, false);
    page = await openPage(context, url, args.timeoutMs);
  }

  if (await hasLoginWall(page)) {
    console.log(`LinkedIn exige login. Faça login no navegador aberto; vou aguardar até ${Math.round(args.loginWaitMs / 1000)}s.`);
    await waitForManualLogin(page, url, args);
  }

  if (await hasLoginWall(page)) {
    await context.close();
    throw new Error("Login/verificação do LinkedIn não foi concluído ou a página continua bloqueada.");
  }
  return { context, page };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const url = validateLinkedInPostUrl(args.url);

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
    const post = await extractPost(page);
    if (!post.text || post.text.length < 120) {
      throw new Error("Não foi possível extrair texto substantivo da postagem.");
    }
    if (/Sign in|Entrar|Join LinkedIn|Cadastre-se|Security verification|verificação de segurança/i.test(post.text.slice(0, 1000))) {
      throw new Error("O texto extraído parece ser login/verificação, não a postagem.");
    }

    const postPath = writePostArtifact(post, url);
    const jobLink = findJobLink(post.links);
    let mode = "post_text";
    let jobOutputPath = "";
    let canonicalSaveOutput = "";
    let delegatedOutput = "";

    if (jobLink) {
      mode = "delegated_job_link";
      delegatedOutput = delegateToJobExtractor(jobLink, args);
    } else {
      const generated = writeJobFromPost(post, args, url);
      jobOutputPath = generated.outputPath;
      if (args.saveJob) {
        canonicalSaveOutput = saveCanonicalJob(generated.job, generated.outputPath);
      }
    }

    const state = {
      source_url: url,
      mode,
      author: post.author,
      post_output_path: path.relative(process.cwd(), postPath),
      job_link: jobLink || null,
      job_output_path: jobOutputPath ? path.relative(process.cwd(), jobOutputPath) : null,
      extracted_at: new Date().toISOString(),
      post_chars: post.text.length,
      links_count: post.links.length,
      canonical_save_executed: args.saveJob && !jobLink,
    };
    writeState(state);

    console.log(JSON.stringify({
      ok: true,
      ...state,
      delegated_job_extract_output: delegatedOutput,
      canonical_save_output: canonicalSaveOutput,
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
