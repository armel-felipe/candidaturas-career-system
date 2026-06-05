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

const pt = n => n * 2; // half-points. Never use n * 20 here.

const workspace = process.env.CAREER_WORKSPACE || process.cwd();
const outputDir = process.env.CAREER_OUTPUTS || path.join(workspace, "outputs");
const contentPath = process.argv[2] || path.join(workspace, ".career-state", "general_cv_content.json");
const outputName = process.argv[3] || "felipe_armel_cv_geral_operacoes_supply_chain.docx";

function secao(text) {
  return new Paragraph({
    children: [new TextRun({ text, size: pt(12), font: "Arial" })],
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "000000", space: 1 } },
    spacing: { before: pt(6), after: pt(3) },
  });
}

function espaco(ptSize = 6) {
  return new Paragraph({
    children: [new TextRun({ text: "", size: pt(ptSize), font: "Arial" })],
    spacing: { after: 0 },
  });
}

function paragraph(text, options = {}) {
  return new Paragraph({
    children: [new TextRun({ text, size: pt(options.size || 9), bold: !!options.bold, font: "Arial" })],
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

function cargoParagraph(cargo, empresa, periodo) {
  return new Paragraph({
    tabStops: [{ type: TabStopType.RIGHT, position: TabStopPosition.MAX }],
    children: [
      new TextRun({ text: `${cargo} — ${empresa}`, bold: true, size: pt(9), font: "Arial" }),
      new TextRun({ text: "\t" + periodo, size: pt(9), font: "Arial" }),
    ],
    spacing: { after: 0 },
  });
}

function bullet(runs) {
  return new Paragraph({
    numbering: { reference: "bullets", level: 0 },
    children: runs.map(run => new TextRun({
      text: run.text,
      bold: !!run.bold,
      size: pt(9),
      font: "Arial",
    })),
    spacing: { after: pt(2) },
  });
}

function content() {
  if (!fs.existsSync(contentPath)) {
    throw new Error(`General CV content not found: ${contentPath}. Run general-cv:strategy and create .career-state/general_cv_content.json first.`);
  }
  return JSON.parse(fs.readFileSync(contentPath, "utf8"));
}

async function main() {
  const data = content();
  fs.mkdirSync(outputDir, { recursive: true });

  const children = [
    paragraph("Felipe Armel Dias da Silva", { size: 12, bold: true }),
    hyperlink("linkedin.com/in/felipearmel", "https://linkedin.com/in/felipearmel"),
    paragraph("São Paulo, SP"),
    hyperlink("(11) 98674-8218", "https://wa.me/5511986748218"),
    hyperlink("armelfelipe@gmail.com", "mailto:armelfelipe@gmail.com"),
    espaco(8),
    secao("Resumo"),
    paragraph(data.summary || ""),
    espaco(8),
    secao("Experiência"),
  ];

  for (const exp of data.experiences || []) {
    children.push(cargoParagraph(exp.role || "Cargo", exp.company || "Empresa", exp.period || "Período"));
    for (const item of exp.bullets || []) {
      children.push(bullet([{ text: item.text || "" }]));
    }
    children.push(espaco(6));
  }

  if (Array.isArray(data.education) && data.education.length) {
    children.push(secao("Formação"));
    for (const item of data.education) children.push(bullet([{ text: item }]));
    children.push(espaco(8));
  }
  if (Array.isArray(data.languages) && data.languages.length) {
    children.push(secao("Idiomas"));
    for (const item of data.languages) children.push(bullet([{ text: item }]));
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
    sections: [{ properties: { page: { margin: { top: 720, right: 504, bottom: 720, left: 504 } } }, children }],
  });

  const outputPath = path.join(outputDir, outputName);
  fs.writeFileSync(outputPath, await Packer.toBuffer(doc));
  const themeScript = path.join(workspace, "scripts", "docx", "inject_arial_theme.py");
  const themeResult = spawnSync(process.env.PYTHON || "python", [themeScript, outputPath], { stdio: "inherit" });
  if (themeResult.status !== 0) process.exit(themeResult.status || 1);
  console.log(outputPath);
}

main().catch(error => {
  console.error(error);
  process.exit(1);
});
