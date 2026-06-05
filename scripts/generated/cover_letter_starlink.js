const fs = require("fs");
const path = require("path");
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

function espaco(ptSize = 6) {
  return new Paragraph({
    children: [new TextRun({ text: "", size: pt(ptSize), font: "Arial" })],
    spacing: { after: 0 },
  });
}

function paragraph(text, options = {}) {
  return new Paragraph({
    children: [new TextRun({ text, size: pt(options.size || 11), bold: !!options.bold, font: "Arial" })],
    spacing: { after: pt(4) },
  });
}

function hyperlink(text, url) {
  return new Paragraph({
    children: [
      new ExternalHyperlink({
        link: url,
        children: [new TextRun({ text, style: "Hyperlink", size: pt(11), font: "Arial" })],
      }),
    ],
    spacing: { after: 0 },
  });
}

async function main() {
  const outputName = "felipe_armel_cover_letter_business_operations_manager_starlink.docx";
  fs.mkdirSync(path.join(outputDir, "_tmp"), { recursive: true });

  const doc = new Document({
    styles: {
      default: { document: { run: { font: "Arial", size: pt(11) } } },
      paragraphStyles: [
        {
          id: "Normal",
          name: "Normal",
          quickFormat: true,
          run: { font: "Arial", size: pt(11) },
          paragraph: { spacing: { after: 0 } },
        },
      ],
    },
    sections: [{
      properties: {
        page: {
          margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 },
        },
      },
      children: [
        // Header
        paragraph("Felipe Armel Dias da Silva", { size: 14, bold: true }),
        hyperlink("linkedin.com/in/felipearmel", "https://linkedin.com/in/felipearmel"),
        hyperlink("armelfelipe@gmail.com", "mailto:armelfelipe@gmail.com"),
        hyperlink("(11) 98674-8218", "https://wa.me/5511986748218"),
        espaco(12),

        // Date
        paragraph("S\u00e3o Paulo, May 2026"),
        espaco(12),

        // Salutation
        paragraph("Dear SpaceX team,"),
        espaco(6),

        // Paragraph 1 — Opening
        paragraph(
          "With 27 years of experience in operations, data analytics and cross-functional leadership \u2014 " +
          "having scaled iFood\u2019s logistics from 400 to 800 cities with a team of 240 people and a " +
          "R$300M annual budget \u2014 I am writing to express my interest in the Business Operations " +
          "Manager (Starlink Brazil Growth) position."
        ),
        espaco(6),

        // Paragraph 2 — Connection to company
        paragraph(
          "What draws me to SpaceX is the mission of building infrastructure that fundamentally changes " +
          "how people connect. Starlink\u2019s challenge in Brazil \u2014 driving subscriber growth across " +
          "channels, managing supply and demand, and using data to guide strategic decisions \u2014 resonates " +
          "directly with the work I have been doing throughout my career. The opportunity to combine analytics " +
          "with business planning and execution, embedded in daily operations, is exactly the kind of role " +
          "where I deliver my best results."
        ),
        espaco(6),

        // Paragraph 3 — Specific diferential
        paragraph(
          "My experience in data-driven operations management connects directly with the responsibilities " +
          "of this role. At iFood, as Director of Operations, I led S&OP executive meetings connecting " +
          "marketing, operations and finance, used Python, SQL and Databricks to model scenarios, and built " +
          "a simulator that generated R$70M/year in savings while maintaining service levels across a 30M " +
          "orders/month operation. I monitored KPIs spanning cost, service level, coverage and churn, and " +
          "made trade-off decisions under uncertainty \u2014 the same analytical discipline Starlink requires " +
          "for subscriber growth, churn, CLV and unit economics."
        ),
        espaco(6),

        // Paragraph 4 — Closing
        paragraph(
          "I would welcome the opportunity to discuss how my background in scaling operations, driving " +
          "data-informed decisions across functions, and building from the ground up can contribute to " +
          "Starlink\u2019s growth in Brazil."
        ),
        espaco(12),

        paragraph("Sincerely,"),
        espaco(6),
        paragraph("Felipe Armel Dias da Silva"),
      ],
    }],
  });

  const buffer = await Packer.toBuffer(doc);
  const tmpPath = path.join(outputDir, "_tmp", outputName);
  fs.writeFileSync(tmpPath, buffer);
  const themeScript = path.join(workspace, "scripts", "docx", "inject_arial_theme.py");
  const { spawnSync } = require("child_process");
  const themeResult = spawnSync("python3", [themeScript, tmpPath, path.join(outputDir, outputName)], { stdio: "inherit" });
  if (themeResult.status !== 0) {
    process.exit(themeResult.status || 1);
  }
  console.log(outputName);
}

main().catch(error => {
  console.error(error);
  process.exit(1);
});
