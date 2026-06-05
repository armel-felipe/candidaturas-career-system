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

const pt = n => n * 2; // half-points. Never use n * 20 here.

const workspace = process.cwd();
const tempDir = path.join(workspace, "outputs", "_tmp");
const outputPath = path.join(tempDir, "cv_mindrift_temp.docx");

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
      new TextRun({ text: `${cargo} - ${empresa}`, bold: true, size: pt(9), font: "Arial" }),
      new TextRun({ text: "\t" + periodo, size: pt(9), font: "Arial" }),
    ],
    spacing: { after: 0 },
  });
}

function bullet(runs) {
  const children = runs.map(r =>
    new TextRun({ text: r.text, bold: r.bold || false, size: pt(9), font: "Arial" })
  );
  return new Paragraph({
    numbering: { reference: "bullets", level: 0 },
    children,
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

const children = [
  paragraph("Felipe Armel Dias da Silva", { size: 12, bold: true }),
  hyperlink("linkedin.com/in/felipearmel", "https://linkedin.com/in/felipearmel"),
  paragraph("São Paulo, SP"),
  hyperlink("(11) 98674-8218", "https://wa.me/5511986748218"),
  hyperlink("armelfelipe@gmail.com", "mailto:armelfelipe@gmail.com"),
  espaco(8),

  secao("Summary"),
  paragraph("Senior operations executive with Chemical Engineering background and hands-on Supply Chain Management, Procurement, Production Planning, MRP, BOM and ERP experience in manufacturing. At Trifil, reduced purchasing cost by 27% and stockouts by 40%. I seek freelance AI evaluation work in supply chain."),
  espaco(8),

  secao("Experience"),

  cargoParagraph("Head of Operations", "wehandle", "May/2024 - Feb/2026"),
  bullet([{ text: "Responsible for a 30-person customer support and CX operation, using AI Evaluation logic to assess automation outputs, product bugs and contact drivers across support workflows." }]),
  bullet([{ text: "Using 3 data sources integrated by API, SQL and Metabase to structure Data Validation routines and operational dashboards ahead of the central data team." }]),
  bullet([
    { text: "Delivered " },
    { text: "15%", bold: true },
    { text: " gross margin impact, reduced contact rate by 8%, improved CSAT from 85% to 92%, kept SLA at 95% of tickets and reduced AHT from 20 to 8 minutes." },
  ]),
  espaco(6),

  cargoParagraph("Head and Director of Operations", "iFood", "Nov/2018 - Mar/2024"),
  bullet([{ text: "Responsible for logistics operations, capacity planning, fleet supply, payments and new businesses, managing up to 240 people and R$300MM/year in logistics cost levers." }]),
  bullet([{ text: "Using SQL, Python and Databricks to model disruption scenarios, service level trade-offs and Mitigation Strategies across 800 cities and 30MM orders/month." }]),
  bullet([
    { text: "Delivered " },
    { text: "R$70MM/year", bold: true },
    { text: " saving with a service-level simulator, reduced fleet unavailability from 5% to 1%, expanded coverage from 400 to 800 cities and cut MPOS Lead Time from 14 to 2 days." },
  ]),
  espaco(6),

  cargoParagraph("Supply Chain, S&OP, Materials Planning and Dispatch Coordinator", "Scalina / Trifil", "Jan/2006 - Sep/2014"),
  bullet([{ text: "Responsible for Supply Chain Management, Procurement, Production Planning, MRP, Vendor Management, S&OP, inventory policies and dispatch operations across 40K SKUs and multiple channels." }]),
  bullet([{ text: "Using 3 levers - ERP Infor LN, Excel/VBA simulators and Strategic Sourcing - to manage purchase planning, safety stock, OTIF, fill rate and Inventory Management decisions." }]),
  bullet([
    { text: "Delivered " },
    { text: "27%", bold: true },
    { text: " purchasing cost reduction, 40% fewer stockouts, inventory accuracy from 85% to 98%, 35% productivity gain, 30% fewer losses and R$8MM GGF reduction." },
  ]),
  espaco(6),

  cargoParagraph("Production Supervisor - Weighing, Manufacturing and Raw Materials Warehouse", "Pierre Alexander Cosmetics", "Aug/2003 - Jul/2005"),
  bullet([{ text: "Responsible for Manufacturing Operations, raw material warehouse routines, production scheduling, BOM setup, electronic manufacturing orders and a 10-person production team." }]),
  bullet([{ text: "Using Totvs Logix ERP as 1 key-user platform for manufacturing routes, BOM, item master data, inventory controls and user training during the implementation." }]),
  bullet([
    { text: "Delivered " },
    { text: "13%", bold: true },
    { text: " productivity improvement in machine planning, reduced contamination losses by 20% and cut physical inventory time by 1 day with an Excel-based control system." },
  ]),
  espaco(8),

  secao("Education"),
  bullet([{ text: "ILEad Leadership Program for Leaders of Leaders - Fundação Dom Cabral (2021)." }]),
  bullet([{ text: "Six Sigma Green Belt - Setec Consulting (2020)." }]),
  bullet([{ text: "Problem Solving - Ventus Consulting (2020)." }]),
  bullet([{ text: "Specialization Certificate in Corporate Strategies — BSP Business School São Paulo (2017)." }]),
  bullet([{ text: "Chemical Engineering - Faculdades Oswaldo Cruz (2014)." }]),
  espaco(8),

  secao("Technical stack"),
  paragraph("ERP Infor LN - Totvs Logix - WMS - SQL - Python - PySpark - Databricks - Tableau - Metabase - Power BI - Excel/VBA"),
  espaco(8),

  secao("Languages"),
  paragraph("Portuguese - Native"),
  paragraph("English - Advanced"),
];

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
    children,
  }],
});

Packer.toBuffer(doc).then(buffer => {
  fs.mkdirSync(tempDir, { recursive: true });
  fs.writeFileSync(outputPath, buffer);
  console.log("ok");
}).catch(error => {
  console.error(error);
  process.exit(1);
});
