const fs = require("fs");
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

function section(text) {
  return new Paragraph({
    children: [new TextRun({ text, size: pt(12), font: "Arial" })],
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "000000", space: 1 } },
    spacing: { before: pt(6), after: pt(3) },
  });
}

function spacer(ptSize = 6) {
  return new Paragraph({
    children: [new TextRun({ text: "", size: pt(ptSize), font: "Arial" })],
    spacing: { after: 0 },
  });
}

function roleParagraph(role, company, period) {
  return new Paragraph({
    tabStops: [{ type: TabStopType.RIGHT, position: TabStopPosition.MAX }],
    children: [
      new TextRun({ text: `${role} — ${company}`, bold: true, size: pt(9), font: "Arial" }),
      new TextRun({ text: "\t" + period, size: pt(9), font: "Arial" }),
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
      page: { margin: { top: 720, right: 504, bottom: 720, left: 504 } },
    },
    children: [
      paragraph("Felipe Armel Dias da Silva", { size: 12, bold: true }),
      hyperlink("linkedin.com/in/felipearmel", "https://linkedin.com/in/felipearmel"),
      paragraph("Sao Paulo, SP"),
      hyperlink("(11) 98674-8218", "https://wa.me/5511986748218"),
      hyperlink("armelfelipe@gmail.com", "mailto:armelfelipe@gmail.com"),

      spacer(8),
      section("Summary"),
      paragraph("Senior operations and logistics executive with experience scaling service networks, managing cost-to-serve, logistics budgets and cross-functional execution in high-complexity environments. At iFood, as Operations Director, I expanded coverage from 400 to 800 cities. As Head of Operations, I delivered R$70MM/year in savings. I am seeking a Logistics Distribution Manager role."),

      spacer(8),
      section("Experience"),

      spacer(3),
      roleParagraph("Head of Operations", "wehandle", "May 2024 – Feb 2026"),
      bullet([{ text: "I was responsible for a 30-person Customer Service operation, strengthening SLA discipline, support governance and operational levers that influenced business margin." }]),
      bullet([{ text: "I applied Data-driven Decision Making through automation, WhatsApp flows, API integrations and SQL/Metabase dashboards to redesign support routines." }]),
      bullet([
        { text: "I reduced total support cost from " },
        { text: "R$4.14 to R$3.61 per service (-13%)", bold: true },
        { text: ", increased CSAT from 85 to 92 and supported a " },
        { text: "15% gross margin impact", bold: true },
        { text: "." },
      ]),

      spacer(6),
      roleParagraph("Operations Director", "iFood", "Apr 2022 – Mar 2024"),
      bullet([
        { text: "I was responsible for national Logistics Execution across a distributed team of about 240 people, balancing Service Levels, Cost-to-Serve and a " },
        { text: "R$300MM/year Logistics Budget", bold: true },
        { text: "." },
      ]),
      bullet([{ text: "I led S&OP, Stakeholder Management and scenario-based decision routines across operations, planning, finance and commercial interfaces." }]),
      bullet([
        { text: "I expanded geographic coverage from " },
        { text: "400 to 800 cities", bold: true },
        { text: ", reduced comparable logistics cost by " },
        { text: "3% YoY", bold: true },
        { text: " and increased grouped deliveries from " },
        { text: "12% to 25%", bold: true },
        { text: "." },
      ]),

      spacer(6),
      roleParagraph("Head of Operations", "iFood", "Nov 2018 – Mar 2022"),
      bullet([{ text: "I was responsible for live operations, regional operations, pricing, data and fleet planning teams, building a 28-person structure focused on service stability and execution control." }]),
      bullet([{ text: "I strengthened KPI Management with simulators, dashboards and operational performance routines using SQL, Databricks, Tableau and Grafana." }]),
      bullet([
        { text: "I generated " },
        { text: "R$70MM/year in savings", bold: true },
        { text: " while sustaining service performance through planning logic, productivity gains and stronger network decision support." },
      ]),

      spacer(6),
      roleParagraph("Commercial Planning and Operations Manager", "VivaReal", "May 2015 – Dec 2017"),
      bullet([{ text: "I was responsible for commercial planning and operations across quality, SDR and property registration routines, supporting marketplace growth with structured operating controls." }]),
      bullet([{ text: "I improved pipeline discipline with Salesforce routines, SQL-based dashboards and cross-functional operating rituals that increased visibility for leadership." }]),
      bullet([
        { text: "I increased inbound SDR conversion from 18% to " },
        { text: "50%", bold: true },
        { text: " and reduced cost of sales by " },
        { text: "40%", bold: true },
        { text: "." },
      ]),

      spacer(6),
      roleParagraph("S&OP Coordinator", "Scalina (Trifil)", "Jan 2010 – Sep 2014"),
      bullet([{ text: "I was responsible for S&OP routines across more than 40K SKUs, connecting demand, supply, production, channels and executive decision-making." }]),
      bullet([{ text: "I managed OTIF, Truck Fill Rate, service indicators, MRP, capacity planning and outsourcing plans to improve planning consistency." }]),
      bullet([
        { text: "I contributed to a " },
        { text: "R$8MM", bold: true },
        { text: " reduction in GGF through tighter operational planning, cost control and execution follow-up." },
      ]),

      spacer(6),
      roleParagraph("Dispatch Coordinator", "Scalina (Trifil)", "Jan 2007 – Oct 2007"),
      bullet([{ text: "I was responsible for dispatch-center routines across picking, packing, storage and shipment preparation in a high-volume warehouse environment." }]),
      bullet([{ text: "I drove Operational Excellence through WMS adoption, RF collectors, inventory rotation controls and layout redesign." }]),
      bullet([
        { text: "I increased inventory accuracy from 85% to " },
        { text: "98%", bold: true },
        { text: ", improved productivity by " },
        { text: "35%", bold: true },
        { text: " and reduced losses by " },
        { text: "30%", bold: true },
        { text: "." },
      ]),

      spacer(8),
      section("Education"),
      spacer(3),
      bullet([{ text: "Specialization Certificate in Corporate Strategies — BSP Business School Sao Paulo (2016–2017)" }]),
      bullet([{ text: "Six Sigma Green Belt — Setec Consulting (2020)" }]),
      bullet([{ text: "Chemical Engineering — Faculdades Oswaldo Cruz (2014)" }]),

      spacer(8),
      section("Technical Skills"),
      spacer(3),
      paragraph("SQL · Python · Databricks · Grafana · Tableau · Metabase · Excel/VBA · WMS · S&OP · Logistics Planning"),

      spacer(8),
      section("Languages"),
      spacer(3),
      bullet([{ text: "Portuguese — Native" }]),
      bullet([{ text: "English — Advanced" }]),
    ],
  }],
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync("outputs/_tmp/felipe_armel_cv_logistics_distribution_manager_chep_en.docx", buffer);
  console.log("ok");
});
