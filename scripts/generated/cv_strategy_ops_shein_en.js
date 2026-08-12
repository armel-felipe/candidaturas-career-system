const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, ExternalHyperlink,
  TabStopType, TabStopPosition, BorderStyle, LevelFormat, AlignmentType,
} = require("docx");

const pt = n => n * 2;

// ---- AUX FUNCTIONS ----

function secao(text) {
  return new Paragraph({
    children: [new TextRun({ text, size: pt(12), font: "Arial" })],
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "000000", space: 1 } },
    spacing: { before: pt(6), after: pt(3) }
  });
}

function espaco(ptSize) {
  return new Paragraph({
    children: [new TextRun({ text: "", size: pt(ptSize), font: "Arial" })],
    spacing: { after: 0 }
  });
}

function cargoParagraph(cargo, empresa, periodo) {
  return new Paragraph({
    tabStops: [{ type: TabStopType.RIGHT, position: TabStopPosition.MAX }],
    children: [
      new TextRun({ text: `${cargo} \u2014 ${empresa}`, bold: true, size: pt(9), font: "Arial" }),
      new TextRun({ text: "\t" + periodo, size: pt(9), font: "Arial" })
    ],
    spacing: { after: 0 }
  });
}

function bullet(runs) {
  const children = runs.map(r =>
    new TextRun({ text: r.text, bold: r.bold || false, size: pt(9), font: "Arial" })
  );
  return new Paragraph({
    numbering: { reference: "bullets", level: 0 },
    children,
    spacing: { after: pt(2) }
  });
}

function link(text, url) {
  return new ExternalHyperlink({
    children: [new TextRun({ text, style: "Hyperlink", size: pt(9), font: "Arial" })],
    link: url
  });
}

// ---- HEADER ----

const headerPar = (children) =>
  new Paragraph({
    children,
    spacing: { after: 0 }
  });

const headerData = [
  [new TextRun({ text: "Felipe Armel Dias da Silva", bold: true, size: pt(12), font: "Arial" })],
  [link("linkedin.com/in/felipearmel", "https://linkedin.com/in/felipearmel")],
  [new TextRun({ text: "S\u00e3o Paulo, SP", size: pt(9), font: "Arial" })],
  [link("(11) 98674-8218", "https://wa.me/5511986748218")],
  [link("armelfelipe@gmail.com", "mailto:armelfelipe@gmail.com")],
];

const headerPars = headerData.map(ch => headerPar(ch));

// ---- RESUMO ----

const resumoText = [
  new TextRun({ text: "Chemical engineer and executive with ", size: pt(9), font: "Arial" }),
  new TextRun({ text: "15+ years", bold: true, size: pt(9), font: "Arial" }),
  new TextRun({ text: " in strategy, operations, and P&L management across digital marketplaces (iFood), tech startups (WeHandle), and industrial supply chains. Led ", size: pt(9), font: "Arial" }),
  new TextRun({ text: "R$300MM/year OPEX", bold: true, size: pt(9), font: "Arial" }),
  new TextRun({ text: " budgets, scaled operations from ", size: pt(9), font: "Arial" }),
  new TextRun({ text: "800K to 30M monthly orders", bold: true, size: pt(9), font: "Arial" }),
  new TextRun({ text: ", and drove cross-functional transformation in high-ambiguity environments. Seeking a Strategy Operations Management role where analytical rigor, executive communication, and operational leadership drive results.", size: pt(9), font: "Arial" }),
];

const resumoPar = new Paragraph({
  children: resumoText,
  spacing: { after: 0 }
});

// ---- EXPERIÊNCIAS ----

// WeHandle
const wehHandle = [
  bullet([
    { text: "Led the support operations of a 30-person team through two platform migrations toward an AI-first model, orchestrating cross-functional alignment and ", bold: false },
    { text: "change management", bold: false },
    { text: " to scale service delivery.", bold: false }
  ]),
  bullet([
    { text: "Structured CX area with ClickUp backlog governance, reducing execution backlog by ", bold: false },
    { text: "60%", bold: true },
    { text: "; implemented WhatsApp channel replacing phone contacts, cutting cost per ticket from R$1.04 to R$0.56.", bold: false }
  ]),
  bullet([
    { text: "Reduced average handling time from 20 to 8 minutes, raised CSAT from 85% to ", bold: false },
    { text: "92%", bold: true },
    { text: ", secured SLA at 95% of tickets, and improved gross margin by 15%.", bold: false }
  ]),
];

// iFood Director
const ifoodDir = [
  bullet([
    { text: "Led logistics operations for Latin America\u2019s largest food delivery marketplace, managing ~240 people, ", bold: false },
    { text: "R$300MM/year OPEX", bold: true },
    { text: " budget, and the executive S&OP forum as a vehicle for ", bold: false },
    { text: "cross-functional leadership", bold: false },
    { text: " connecting demand, supply, fleet, and cost.", bold: false }
  ]),
  bullet([
    { text: "Drove integrated planning integrating marketing, weather, fleet availability, and geographic expansion into a single process, conducting cost vs. service level trade-offs to protect EBITDA — applying ", bold: false },
    { text: "data-driven decision making", bold: false },
    { text: " at executive level.", bold: false }
  ]),
  bullet([
    { text: "Delivered ", bold: false },
    { text: "operational excellence", bold: false },
    { text: " by expanding coverage from 400 to 800 cities, reducing comparable logistics cost by ", bold: false },
    { text: "3% YoY", bold: true },
    { text: ", cutting fleet unavailability from 5% to 1%, and increasing grouped deliveries from 12% to 25%.", bold: false }
  ]),
];

// iFood Head
const ifoodHead = [
  bullet([
    { text: "Built liveOps and fleet planning teams of 28, structuring real-time ", bold: false },
    { text: "KPI development and monitoring", bold: false },
    { text: " in Grafana correlating logistics saturation, delivery time, and courier earnings for executive reporting.", bold: false }
  ]),
  bullet([
    { text: "Developed a service-level simulator using Business Analytics (SQL, Python) for data-driven decision making, generating ", bold: false },
    { text: "R$70MM/year", bold: true },
    { text: " in fleet optimization savings while maintaining SLA.", bold: false }
  ]),
  bullet([
    { text: "Reduced MPOS distribution time from 14 to 2 days and distribution cost by ", bold: false },
    { text: "80%", bold: true },
    { text: ", scaling operations from 800K to 30M monthly orders across Brazil.", bold: false }
  ]),
];

// VivaReal
const vivaReal = [
  bullet([
    { text: "Architected the Customer Success area from scratch \u2014 designed onboarding journeys, recruited leadership, and oversaw a ", bold: false },
    { text: "91-person", bold: true },
    { text: " department; also led commercial planning and operations for a 33-person team.", bold: false }
  ]),
  bullet([
    { text: "Built SDR lead qualification process that raised inbound conversion from 18% to ", bold: false },
    { text: "50%", bold: true },
    { text: ", reducing sales cost by 40%; developed VBA-based inventory allocation system increasing revenue from R$80M to R$120M/year.", bold: false }
  ]),
  bullet([
    { text: "Drove strategic planning for the ZAP merger transition; achieved ", bold: false },
    { text: "NPS of 80%", bold: true },
    { text: ", CSAT above 92%, and churn below 3%/month.", bold: false }
  ]),
];

// Trifil
const trifil = [
  bullet([
    { text: "Created the S&OP area from scratch, managing ", bold: false },
    { text: "40K SKUs", bold: true },
    { text: " across two brands and all distribution channels; coordinated production planning, materials procurement, and outsourcing strategy.", bold: false }
  ]),
  bullet([
    { text: "Led ", bold: false },
    { text: "process optimization", bold: false },
    { text: " reducing manufacturing overhead (GGF) by ", bold: false },
    { text: "R$8M", bold: true },
    { text: " through energy, gas, maintenance, and packaging improvements; built VBA-based MRP simulator for scenario analysis and capacity planning.", bold: false }
  ]),
  bullet([
    { text: "Implemented Strategic Sourcing across 150K+ SKUs, cutting purchase costs by ", bold: false },
    { text: "27%", bold: true },
    { text: " and stock-outs by 40% while improving inventory turnover from 8 to 6 months.", bold: false }
  ]),
];

// ---- FORMAÇÃO ----

const formacaoBullets = [
  bullet([{ text: "Specialization Certificate in Corporate Strategies \u2014 BSP Business School S\u00e3o Paulo (2017)", bold: false }]),
  bullet([{ text: "Chemical Engineering \u2014 Faculdades Oswaldo Cruz (2014)", bold: false }]),
  bullet([{ text: "Six Sigma Green Belt \u2014 Setec Consulting (2020)", bold: false }]),
  bullet([{ text: "Leadership for Leader of Leaders \u2014 Funda\u00e7\u00e3o Dom Cabral (2021)", bold: false }]),
];

// ---- STACK TÉCNICA ----

const stackText = "Python \u00b7 SQL \u00b7 PySpark \u00b7 Databricks \u00b7 Grafana \u00b7 Tableau \u00b7 Salesforce \u00b7 Zendesk \u00b7 Excel/VBA \u00b7 ERP Infor LN \u00b7 WMS";

const stackPar = new Paragraph({
  children: [new TextRun({ text: stackText, size: pt(9), font: "Arial" })],
  spacing: { after: 0 }
});

// ---- IDIOMAS ----

const idiomas = [
  bullet([{ text: "Portuguese \u2014 Native", bold: false }]),
  bullet([{ text: "English \u2014 Advanced", bold: false }]),
];

// ---- DOCUMENT ----

const doc = new Document({
  styles: {
    default: { document: { run: { font: "Arial", size: pt(9) } } },
    paragraphStyles: [
      {
        id: "Normal", name: "Normal", quickFormat: true,
        run: { font: "Arial", size: pt(9) },
        paragraph: { spacing: { after: 0 } }
      },
      {
        id: "ListParagraph", name: "List Paragraph", basedOn: "Normal", quickFormat: true,
        run: { font: "Arial", size: pt(9) },
        paragraph: { spacing: { after: 0 } }
      }
    ]
  },
  numbering: {
    config: [{
      reference: "bullets",
      levels: [{
        level: 0, format: LevelFormat.BULLET, text: "\u2022",
        alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 360, hanging: 180 } } }
      }]
    }]
  },
  sections: [{
    properties: {
      page: {
        margin: { top: 720, right: 504, bottom: 720, left: 504 }
      }
    },
    children: [
      // HEADER
      ...headerPars,
      espaco(8),

      // RESUMO
      secao("Summary"),
      espaco(3),
      resumoPar,
      espaco(8),

      // EXPERIÊNCIA
      secao("Experience"),
      espaco(3),

      // WeHandle
      cargoParagraph("Head of Operations", "wehandle", "Mai 2024 \u2013 Fev 2026"),
      ...wehHandle,
      espaco(6),

      // iFood Director
      cargoParagraph("Director of Operations", "iFood", "Abr 2022 \u2013 Mar 2024"),
      ...ifoodDir,
      espaco(6),

      // iFood Head
      cargoParagraph("Head of Operations", "iFood", "Nov 2018 \u2013 Mar 2022"),
      ...ifoodHead,
      espaco(6),

      // VivaReal
      cargoParagraph("Commercial Planning and Operations Manager", "VivaReal", "Mai 2015 \u2013 Dez 2017"),
      ...vivaReal,
      espaco(6),

      // Trifil
      cargoParagraph("S&OP | Supply Chain | Logistics Coordinator", "Trifil (Scalina)", "Jan 2006 \u2013 Set 2014"),
      ...trifil,
      espaco(8),

      // FORMAÇÃO
      secao("Education"),
      espaco(3),
      ...formacaoBullets,
      espaco(8),

      // STACK TÉCNICA
      secao("Technical Skills"),
      espaco(3),
      stackPar,
      espaco(8),

      // IDIOMAS
      secao("Languages"),
      espaco(3),
      ...idiomas,
    ]
  }]
});

// ---- OUTPUT ----
Packer.toBuffer(doc).then(buffer => {
  const outPath = "outputs/_tmp/cv_strategy_ops_shein_en.docx";
  fs.writeFileSync(outPath, buffer);
  console.log("ok");
}).catch(err => {
  console.error(err);
  process.exit(1);
});
