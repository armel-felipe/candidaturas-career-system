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

const workspace = process.env.CAREER_WORKSPACE || process.cwd();
const outputDir = process.env.CAREER_OUTPUTS || path.join(workspace, "outputs");
const cvContentPath = path.join(workspace, ".career-state", "cv_content.json");
const fitMapPath = path.join(workspace, ".career-state", "fit_map.json");

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
  return new Paragraph({
    tabStops: [{ type: TabStopType.RIGHT, position: TabStopPosition.MAX }],
    children: [
      new TextRun({ text: `${cargo} — ${empresa}`, bold: true, size: pt(9), font: "Arial" }),
      new TextRun({ text: "\t" + periodo, size: pt(9), font: "Arial" }),
    ],
    spacing: { after: 0 },
  });
}

function bullet(items) {
  const runs = [];
  for (const item of items) {
    if (typeof item === "string") {
      runs.push(new TextRun({ text: item, size: pt(9), font: "Arial" }));
    } else if (item.text) {
      runs.push(new TextRun({ text: item.text, size: pt(9), font: "Arial", bold: !!item.bold }));
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

async function main() {
  const cv = JSON.parse(fs.readFileSync(cvContentPath, "utf-8"));
  const outputName = cv.output_name || process.argv[2] || "felipe_armel_cv.docx";
  fs.mkdirSync(outputDir, { recursive: true });

  const children = [];

  // Header
  children.push(paragraph("Felipe Armel Dias da Silva", { size: 12, bold: true }));
  children.push(hyperlink("linkedin.com/in/felipearmel", "https://linkedin.com/in/felipearmel"));
  children.push(paragraph("São Paulo, SP"));
  children.push(hyperlink("(11) 98674-8218", "https://wa.me/5511986748218"));
  children.push(hyperlink("armelfelipe@gmail.com", "mailto:armelfelipe@gmail.com"));
  children.push(espaco(8));

  // Resumo
  children.push(secao("Resumo"));
  children.push(paragraph(cv.resumo));
  children.push(espaco(8));

  // Experiência
  children.push(secao("Experiência"));
  for (const exp of cv.experiencias) {
    children.push(espaco(3));
    children.push(cargoParagraph(exp.cargo, exp.empresa, exp.periodo));
    for (const b of exp.bullets) {
      if (typeof b === "string") {
        children.push(bullet([{ text: b }]));
      } else if (b.prefixo) {
        children.push(bullet([b]));
      }
    }
  }

  children.push(espaco(8));

  // Formação
  children.push(secao("Formação"));
  for (const f of cv.formacao) {
    children.push(bullet([{ text: f }]));
  }
  children.push(espaco(8));

  // Stack técnica
  children.push(secao("Stack técnica"));
  children.push(paragraph(cv.stack));
  children.push(espaco(8));

  // Idiomas
  children.push(secao("Idiomas"));
  for (const idioma of cv.idiomas) {
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
  const themeResult = spawnSync("/usr/bin/python3", [themeScript, outputPath], { stdio: "inherit" });
  if (themeResult.status !== 0) {
    console.error("Theme injection failed, continuing anyway");
  }
  console.log(outputPath);
}

main().catch(error => {
  console.error(error);
  process.exit(1);
});
