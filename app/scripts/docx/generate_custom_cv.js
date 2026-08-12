const fs = require("fs");
const path = require("path");
const { spawnSync } = require("child_process");
const {
  AlignmentType,
  BorderStyle,
  Document,
  ExternalHyperlink,
  LevelFormat,
  Packer,
  Paragraph,
  TabStopPosition,
  TabStopType,
  TextRun,
} = require("docx");

const pt = n => n * 2;

let currentLang = "pt-BR";

// Bolds "de X para Y" (pt) / "from X to Y" (en) result transitions.
function boldResultTransitions(text) {
  // number: optional R$ prefix, digits with optional decimal separator (pt: comma, en: dot)
  const num = "(?:R\\$\\s?)?\\d+(?:[.,]\\d+)*%?";
  const pattern = currentLang === "en"
    ? new RegExp(`(from\\s+${num}\\s+to\\s+${num})`, "gi")
    : new RegExp(`(de\\s+${num}\\s+para\\s+${num})`, "gi");
  return String(text).replace(pattern, "**$1**");
}

function cliOption(name) {
  const index = process.argv.indexOf(name);
  return index >= 0 ? process.argv[index + 1] : undefined;
}

const workspace = process.env.CAREER_WORKSPACE || process.cwd();
const outputDir = cliOption("--output-dir") || process.env.CAREER_OUTPUTS || path.join(workspace, "outputs");
const cvContentPath = cliOption("--content") || process.env.CAREER_CV_CONTENT || path.join(workspace, ".career-state", "cv_content.json");
const outputNameOverride = cliOption("--output-name") || process.env.CAREER_OUTPUT_NAME;
const applicationId = cliOption("--application-id") || process.env.CAREER_APPLICATION_ID || "";

function textRuns(text, options = {}) {
  return String(text)
    .split(/(\*\*[^*]+\*\*)/g)
    .filter(Boolean)
    .map(part => {
      const markdownBold = part.startsWith("**") && part.endsWith("**");
      return new TextRun({
        text: markdownBold ? part.slice(2, -2) : part,
        size: pt(options.size || 9),
        bold: markdownBold || !!options.bold,
        font: "Arial",
      });
    });
}

function secao(text) {
  return new Paragraph({
    children: [new TextRun({ text, size: pt(12), font: "Arial" })],
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "000000", space: 1 } },
    spacing: { before: pt(6), after: pt(3) },
  });
}

function espaco(p = 6) {
  return new Paragraph({
    children: [new TextRun({ text: "", size: pt(p), font: "Arial" })],
    spacing: { after: 0 },
  });
}

function cargoParagraph(cargo, empresa, periodo) {
  return [
    new Paragraph({
      children: [new TextRun({ text: `${cargo} - ${empresa}`, bold: true, size: pt(9), font: "Arial" })],
      spacing: { after: 0 },
    }),
    new Paragraph({
      children: [new TextRun({ text: formatPeriod(periodo), size: pt(9), font: "Arial" })],
      spacing: { after: 0 },
    }),
  ];
}

// Converts "May 2024 - Feb 2026" -> "May 2024 to Feb 2026" (en) / "a" (pt).
function formatPeriod(periodo) {
  const sep = currentLang === "en" ? "to" : "a";
  return String(periodo || "").replace(/\s*-\s*/g, ` ${sep} `);
}

function bullet(items) {
  const runs = [];
  for (const item of items) {
    if (typeof item === "string") {
      runs.push(...textRuns(boldResultTransitions(item)));
    } else if (item.text) {
      runs.push(...textRuns(boldResultTransitions(item.text), { bold: item.bold }));
    } else if (item.prefixo) {
      runs.push(new TextRun({ text: item.prefixo, size: pt(9), font: "Arial" }));
      if (item.enfoque) {
        runs.push(new TextRun({ text: item.enfoque, size: pt(9), font: "Arial", bold: true }));
      }
      if (item.sufixo) {
        runs.push(new TextRun({ text: item.sufixo, size: pt(9), font: "Arial" }));
      }
    }
  }
  return new Paragraph({
    numbering: { reference: "bullets", level: 0 },
    children: runs,
    spacing: { after: pt(2) },
  });
}

function paragraph(text, options = {}) {
  return new Paragraph({
    children: textRuns(boldResultTransitions(text), options),
    spacing: { after: 0 },
  });
}

function hyperlink(text, url) {
  return new Paragraph({
    children: [
      new ExternalHyperlink({
        link: url,
        children: [new TextRun({ text, style: "Hyperlink", size: pt(9), font: "Arial" })],
      }),
    ],
    spacing: { after: 0 },
  });
}

const L10N = {
  "pt-BR": {
    summary: "Resumo",
    experience: "Experiência",
    education: "Formação",
    stack: "Stack técnica",
    languages: "Idiomas",
  },
  "en": {
    summary: "Summary",
    experience: "Experience",
    education: "Education",
    stack: "Technical Stack",
    languages: "Languages",
  },
};

function assertNonEmptyString(value, field) {
  if (typeof value !== "string" || !value.trim()) {
    throw new Error(`cv_content.${field} must be a non-empty string`);
  }
}

function assertNonEmptyArray(value, field) {
  if (!Array.isArray(value) || value.length === 0 || value.some(item => !String(item || "").trim())) {
    throw new Error(`cv_content.${field} must be a non-empty list`);
  }
}

function experienceEndKey(period) {
  const value = String(period || "").trim();
  if (/\b(present|current|atual)\b/i.test(value)) return Number.MAX_SAFE_INTEGER;
  const months = { jan: 1, janeiro: 1, january: 1, feb: 2, fev: 2, fevereiro: 2, mar: 3, march: 3, março: 3, apr: 4, abr: 4, april: 4, may: 5, maio: 5, jun: 6, junho: 6, june: 6, jul: 7, julho: 7, july: 7, aug: 8, ago: 8, agosto: 8, september: 9, set: 9, setembro: 9, sep: 9, oct: 10, out: 10, outubro: 10, nov: 11, novembro: 11, dec: 12, dez: 12, dezembro: 12 };
  const matches = [...value.toLowerCase().matchAll(/([a-zç]+)\/?\s*(\d{4})/g)];
  const last = matches.at(-1);
  if (!last || !months[last[1]]) throw new Error(`Unable to parse experience period: ${value}`);
  return Number(last[2]) * 12 + months[last[1]];
}

function assertReverseChronological(experiences, periodField) {
  const keys = experiences.map(exp => experienceEndKey(exp && exp[periodField]));
  for (let index = 1; index < keys.length; index += 1) {
    if (keys[index] > keys[index - 1]) throw new Error("cv_content experiences must be in reverse chronological order");
  }
}

async function main() {
  const cv = JSON.parse(fs.readFileSync(cvContentPath, "utf-8"));
  const lang = cv && cv.metadata && cv.metadata.language;
  if (lang !== "pt-BR" && lang !== "en") {
    throw new Error("cv_content.metadata.language must be 'pt-BR' or 'en'");
  }
  currentLang = lang;
  const l10n = L10N[lang];
  const candidate = cv.candidate;
  if (!candidate || typeof candidate !== "object") {
    throw new Error("cv_content.candidate is required");
  }
  for (const field of ["name", "location", "linkedin", "phone", "email"]) {
    assertNonEmptyString(candidate[field], `candidate.${field}`);
  }
  if (applicationId && cv?.metadata?.application_id && cv.metadata.application_id !== applicationId) {
    throw new Error("cv_content.metadata.application_id does not match the requested application");
  }
  const outputName = outputNameOverride || cv.output_name;
  if (!outputName) {
    throw new Error("cv content must declare an explicit output filename");
  }
  if (path.basename(outputName) !== outputName) {
    throw new Error("output name must be a single filename");
  }
  fs.mkdirSync(outputDir, { recursive: true });

  const summaryField = lang === "en" ? "summary" : "resumo";
  const experiencesField = lang === "en" ? "experiences" : "experiencias";
  const educationField = lang === "en" ? "education" : "formacao";
  const languagesField = lang === "en" ? "languages" : "idiomas";
  assertNonEmptyString(cv[summaryField], summaryField);
  assertNonEmptyArray(cv[experiencesField], experiencesField);
  assertNonEmptyArray(cv[educationField], educationField);
  assertNonEmptyString(cv.stack, "stack");
  assertNonEmptyArray(cv[languagesField], languagesField);
  assertReverseChronological(cv[experiencesField], lang === "en" ? "period" : "periodo");

  const children = [];

  // Header
  children.push(paragraph(candidate.name, { size: 12, bold: true }));
  children.push(hyperlink(candidate.linkedin, `https://${candidate.linkedin}`));
  children.push(paragraph(candidate.location));
  children.push(hyperlink(candidate.phone, candidate.phone.startsWith("+") ? `tel:${candidate.phone.replace(/[^+0-9]/g, "")}` : candidate.phone));
  children.push(hyperlink(candidate.email, `mailto:${candidate.email}`));
  children.push(espaco(8));

  // Resumo / Summary
  children.push(secao(l10n.summary));
  children.push(paragraph(cv[summaryField]));
  children.push(espaco(8));

  // Experiência / Experience
  children.push(secao(l10n.experience));
  for (const exp of cv[experiencesField]) {
    children.push(espaco(3));
    children.push(...cargoParagraph(lang === "en" ? exp.role : exp.cargo, lang === "en" ? exp.company : exp.empresa, lang === "en" ? exp.period : exp.periodo));
    for (const b of exp.bullets) {
      if (typeof b === "string") {
        children.push(bullet([{ text: b }]));
      } else if (b.prefixo) {
        children.push(bullet([b]));
      } else if (b.text) {
        children.push(bullet([{ text: b.text }]));
      }
    }
  }

  children.push(espaco(8));

  // Formação / Education
  children.push(secao(l10n.education));
  for (const f of cv[educationField]) {
    children.push(bullet([{ text: f }]));
  }
  children.push(espaco(8));

  // Stack técnica / Technical Stack
  children.push(secao(l10n.stack));
  children.push(paragraph(cv.stack));
  children.push(espaco(8));

  // Idiomas / Languages
  children.push(secao(l10n.languages));
  for (const idioma of cv[languagesField]) {
    children.push(bullet([{ text: idioma }]));
  }

  const doc = new Document({
    styles: {
      default: { document: { run: { font: "Arial", size: pt(9) } } },
      paragraphStyles: [
        { id: "Normal", name: "Normal", quickFormat: true, run: { font: "Arial", size: pt(9) }, paragraph: { spacing: { after: 0 } } },
        { id: "ListParagraph", name: "List Paragraph", basedOn: "Normal", quickFormat: true, run: { font: "Arial", size: pt(9) }, paragraph: { spacing: { after: 0 } } },
      ],
    },
    numbering: {
      config: [{
        reference: "bullets",
        levels: [{
          level: 0,
          format: LevelFormat.BULLET,
          text: "\u2022",
          alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 360, hanging: 180 } } },
        }],
      }],
    },
    sections: [{
      properties: {
        page: {
          margin: { top: 720, right: 504, bottom: 720, left: 504 },
        },
      },
      children,
    }],
  });

  const buffer = await Packer.toBuffer(doc);
  const outputPath = path.join(outputDir, outputName);
  fs.writeFileSync(outputPath, buffer);

  const themeScript = path.join(workspace, "scripts", "docx", "inject_arial_theme.py");
  const pythonCmd = process.env.PYTHON || path.join(workspace, "scripts", "python.sh");
  const themeResult = spawnSync(pythonCmd, [themeScript, outputPath], { stdio: "inherit" });
  if (themeResult.status !== 0) {
    throw new Error(`Arial theme injection failed for ${outputPath}`);
  }
  console.log(outputPath);
}

main().catch(error => {
  console.error(error);
  process.exit(1);
});
