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
      bold: run.bold || false,
      size: pt(9),
      font: "Arial",
    })),
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
  const outputName = process.argv[2] || "felipe_armel_cv_template.docx";
  fs.mkdirSync(outputDir, { recursive: true });

  const doc = new Document({
    styles: {
      default: { document: { run: { font: "Arial", size: pt(9) } } },
      paragraphStyles: [
        {
          id: "Normal",
          name: "Normal",
          quickFormat: true,
          run: { font: "Arial", size: pt(9) },
          paragraph: { spacing: { after: 0 } },
        },
        {
          id: "ListParagraph",
          name: "List Paragraph",
          basedOn: "Normal",
          quickFormat: true,
          run: { font: "Arial", size: pt(9) },
          paragraph: { spacing: { after: 0 } },
        },
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
      children: [
        paragraph("Felipe Armel Dias da Silva", { size: 12, bold: true }),
        hyperlink("linkedin.com/in/felipearmel", "https://linkedin.com/in/felipearmel"),
        paragraph("São Paulo, SP"),
        hyperlink("(11) 98674-8218", "https://wa.me/5511986748218"),
        hyperlink("armelfelipe@gmail.com", "mailto:armelfelipe@gmail.com"),
        espaco(8),
        secao("Resumo"),
        paragraph("Template técnico local. Substituir este conteúdo pelo CV aprovado pelo output-reviewer antes da entrega."),
        espaco(8),
        secao("Experiência"),
        cargoParagraph("Cargo", "Empresa", "Período validado em autoconhecimento.md"),
        bullet([{ text: "Fui responsável por escopo validado na base, com número defensável." }]),
        bullet([{ text: "Utilizando até três competências diretamente ligadas ao resultado." }]),
        bullet([{ text: "Consegui resultado quantitativo validado contra perfil_restricoes.md." }]),
      ],
    }],
  });

  const buffer = await Packer.toBuffer(doc);
  const outputPath = path.join(outputDir, outputName);
  fs.writeFileSync(outputPath, buffer);
  const themeScript = path.join(workspace, "scripts", "docx", "inject_arial_theme.py");
  const themeResult = spawnSync(process.env.PYTHON || "python", [themeScript, outputPath], { stdio: "inherit" });
  if (themeResult.status !== 0) {
    process.exit(themeResult.status || 1);
  }
  console.log(outputPath);
}

main().catch(error => {
  console.error(error);
  process.exit(1);
});
