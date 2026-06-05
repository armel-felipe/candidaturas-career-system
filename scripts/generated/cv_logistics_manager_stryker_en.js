const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, ExternalHyperlink,
  TabStopType, TabStopPosition, LevelFormat, AlignmentType,
  BorderStyle, PageSize
} = require("docx");

// half-points: NUNCA n * 20
const pt = n => n * 2;

const workspace = process.cwd();

// ---- helpers ----
function secao(text) {
  return new Paragraph({
    children: [new TextRun({ text, size: pt(12), font: "Arial" })],
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "000000", space: 1 } },
    spacing: { before: pt(6), after: pt(3) }
  });
}
function espaco(p = 6) {
  return new Paragraph({
    children: [new TextRun({ text: "", size: pt(p), font: "Arial" })],
    spacing: { after: 0 }
  });
}
function cargoParagraph(cargo, empresa, periodo) {
  return new Paragraph({
    tabStops: [{ type: TabStopType.RIGHT, position: TabStopPosition.MAX }],
    children: [
      new TextRun({ text: `${cargo} — ${empresa}`, bold: true, size: pt(9), font: "Arial" }),
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

// ---- numbering config ----
const numberingConfig = [{
  reference: "bullets",
  levels: [{
    level: 0, format: LevelFormat.BULLET, text: "\u2022",
    alignment: AlignmentType.LEFT,
    style: { paragraph: { indent: { left: 360, hanging: 180 } } }
  }]
}];

// ---- styles ----
const styles = {
  default: { document: { run: { font: "Arial", size: pt(9) } } },
  paragraphStyles: [
    { id: "Normal", name: "Normal", quickFormat: true,
      run: { font: "Arial", size: pt(9) },
      paragraph: { spacing: { after: 0 } } },
    { id: "ListParagraph", name: "List Paragraph", basedOn: "Normal", quickFormat: true,
      run: { font: "Arial", size: pt(9) },
      paragraph: { spacing: { after: 0 } } }
  ]
};

// ---- cabecalho ----
function cabecalho() {
  return [
    new Paragraph({
      children: [new TextRun({ text: "Felipe Armel Dias da Silva", bold: true, size: pt(12), font: "Arial" })],
      spacing: { after: 0 }
    }),
    new Paragraph({
      children: [new ExternalHyperlink({
        link: "https://linkedin.com/in/felipearmel",
        children: [new TextRun({ text: "linkedin.com/in/felipearmel", size: pt(9), font: "Arial", style: "Hyperlink" })]
      })],
      spacing: { after: 0 }
    }),
    new Paragraph({
      children: [new TextRun({ text: "São Paulo, SP", size: pt(9), font: "Arial" })],
      spacing: { after: 0 }
    }),
    new Paragraph({
      children: [new ExternalHyperlink({
        link: "https://wa.me/5511986748218",
        children: [new TextRun({ text: "(11) 98674-8218", size: pt(9), font: "Arial", style: "Hyperlink" })]
      })],
      spacing: { after: 0 }
    }),
    new Paragraph({
      children: [new ExternalHyperlink({
        link: "mailto:armelfelipe@gmail.com",
        children: [new TextRun({ text: "armelfelipe@gmail.com", size: pt(9), font: "Arial", style: "Hyperlink" })]
      })],
      spacing: { after: 0 }
    })
  ];
}

// ---- resumo ----
function resumo() {
  return new Paragraph({
    children: [
      new TextRun({
        text: "Chemical engineer with an MBA in Corporate Strategy and over 15 years of experience in logistics, supply chain, and continuous improvement. At iFood, as Director of Operations, managed a ",
        size: pt(9), font: "Arial"
      }),
      new TextRun({
        text: "R$300M",
        bold: true, size: pt(9), font: "Arial"
      }),
      new TextRun({
        text: " annual logistics budget and led capacity planning across 800 cities. At Trifil, drove warehouse inventory accuracy from ",
        size: pt(9), font: "Arial"
      }),
      new TextRun({
        text: "85% to 98%",
        bold: true, size: pt(9), font: "Arial"
      }),
      new TextRun({
        text: " through cycle counting and WMS implementation. Lean Six Sigma Green Belt with pharmaceutical compliance background. Seeking a Logistics Manager position.",
        size: pt(9), font: "Arial"
      })
    ],
    spacing: { after: 0 }
  });
}

// ---- experiencias ----
function experienciaWehandle() {
  return [
    cargoParagraph("Head of Operations", "wehandle", "May 2024 – Feb 2026"),
    bullet([
      { text: "Led the customer operations team of 30, overseeing support KPIs, cost structure, and multi-platform processes while restructuring operations that impacted ", bold: false },
      { text: "15%", bold: true },
      { text: " of gross margin.", bold: false }
    ]),
    bullet([
      { text: "Implemented AI-first automation, WhatsApp channel migration replacing phone contacts, and connected support data to the datalake via API for real-time performance dashboards.", bold: false }
    ]),
    bullet([
      { text: "Reduced cost per contact by ", bold: false },
      { text: "13%", bold: true },
      { text: " (R$4.14 to R$3.61), raised CSAT from 85% to ", bold: false },
      { text: "92%", bold: true },
      { text: ", and achieved ", bold: false },
      { text: "95%", bold: true },
      { text: " SLA adherence.", bold: false }
    ]),
    espaco(6)
  ];
}

function experienciaIfoodDiretor() {
  return [
    cargoParagraph("Director of Operations", "iFood", "Apr 2022 – Mar 2024"),
    bullet([
      { text: "Managed logistics operations with a team of ", bold: false },
      { text: "240", bold: true },
      { text: " people and an annual budget of ", bold: false },
      { text: "R$300M", bold: true },
      { text: ", leading executive S&OP with KPI Governance / Performance Review routines and focus on cost, service level, and coverage.", bold: false }
    ]),
    bullet([
      { text: "Drove capacity planning through data modeling (Python, SQL, Databricks), fleet availability optimization, and rolling forecast connecting marketing, promotions, and demand data.", bold: false }
    ]),
    bullet([
      { text: "Expanded coverage from 400 to ", bold: false },
      { text: "800", bold: true },
      { text: " cities, reduced comparable logistics cost by ", bold: false },
      { text: "3% YoY", bold: true },
      { text: ", and cut fleet unavailability from 5% to ", bold: false },
      { text: "0.5%", bold: true },
      { text: " in top 6 cities.", bold: false }
    ]),
    espaco(6)
  ];
}

function experienciaIfoodHead() {
  return [
    cargoParagraph("Head of Operations", "iFood", "Nov 2018 – Mar 2022"),
    bullet([
      { text: "Led a 28-person team across liveOps, regional operations, fleet planning, and pricing — structured 3PL Management governance and performance KPI framework.", bold: false }
    ]),
    bullet([
      { text: "Built a proprietary service level simulator balancing cost and availability, established MPOS distribution reducing delivery time from 14 to ", bold: false },
      { text: "2", bold: true },
      { text: " days, and defined partner contracts and SLA metrics.", bold: false }
    ]),
    bullet([
      { text: "Generated ", bold: false },
      { text: "R$70M", bold: true },
      { text: " annual savings through the simulator and reduced Mexico cancellation rates by ", bold: false },
      { text: "60%", bold: true },
      { text: " through delivery radius optimization.", bold: false }
    ]),
    espaco(6)
  ];
}

function experienciaVivaReal() {
  return [
    cargoParagraph("Commercial Planning and Operations Manager", "VivaReal", "May 2015 – Dec 2017"),
    bullet([
      { text: "Managed a 33-person team across planning, SDR, and quality — architected the CS area from scratch, which later scaled to ", bold: false },
      { text: "91", bold: true },
      { text: " people.", bold: false }
    ]),
    bullet([
      { text: "Applied SQL, Excel/VBA, and Power BI for performance dashboards; structured SDR lead qualification and inbound conversion processes.", bold: false }
    ]),
    bullet([
      { text: "Increased SDR conversion from 18% to ", bold: false },
      { text: "50%", bold: true },
      { text: ", reduced sales cost by ", bold: false },
      { text: "40%", bold: true },
      { text: ", and maintained churn below ", bold: false },
      { text: "3%", bold: true },
      { text: " monthly with NPS reaching 80%.", bold: false }
    ]),
    espaco(6)
  ];
}

function experienciaTrifil() {
  return [
    cargoParagraph("S&OP Coordinator | Warehouse and Distribution Coordinator", "Scalina (Trifil)", "Jan 2006 – Sep 2014"),
    bullet([
      { text: "Managed warehousing operations including picking, packing, inventory control, and cycle counting across a distribution center with ", bold: false },
      { text: "40K", bold: true },
      { text: " SKUs. Built the S&OP area from scratch and sustained it for 4 years.", bold: false }
    ]),
    bullet([
      { text: "Implemented WMS with RF collectors, address mapping, and cycle counting. Applied Lean Six Sigma and PDCA methodology, achieving ", bold: false },
      { text: "12%", bold: true },
      { text: " efficiency gains in dyeing machinery. Reduced ", bold: false },
      { text: "R$8M", bold: true },
      { text: " in GGF overhead.", bold: false }
    ]),
    bullet([
      { text: "Raised inventory accuracy from 85% to ", bold: false },
      { text: "98%", bold: true },
      { text: ", improved productivity by ", bold: false },
      { text: "35%", bold: true },
      { text: " through warehouse layout redesign, and reduced losses by ", bold: false },
      { text: "30%", bold: true },
      { text: ".", bold: false }
    ]),
    espaco(6)
  ];
}

// ---- formacao ----
function formacao() {
  return [
    bullet([{ text: "MBA Corporate Strategy — BSP Business School São Paulo (2017)", bold: false }]),
    bullet([{ text: "Chemical Engineering — Faculdades Oswaldo Cruz (2014)", bold: false }])
  ];
}

// ---- stack ----
function stack() {
  return new Paragraph({
    children: [new TextRun({ text: "Excel/VBA · SQL · Python · Databricks · Power BI · ERP Infor LN · WMS", size: pt(9), font: "Arial" })],
    spacing: { after: 0 }
  });
}

// ---- idiomas ----
function idiomas() {
  return [
    bullet([{ text: "Portuguese — Native", bold: false }]),
    bullet([{ text: "English — Advanced", bold: false }])
  ];
}

// ---- document ----
const doc = new Document({
  styles,
  numbering: { config: numberingConfig },
  sections: [{
    properties: {
      page: {
        margin: { top: 720, right: 504, bottom: 720, left: 504 },
        size: { width: 11906, height: 16838 }
      }
    },
    children: [
      ...cabecalho(),
      espaco(8),
      secao("Profile"),
      espaco(3),
      resumo(),
      espaco(8),
      secao("Experience"),
      espaco(3),
      ...experienciaWehandle(),
      ...experienciaIfoodDiretor(),
      ...experienciaIfoodHead(),
      ...experienciaVivaReal(),
      ...experienciaTrifil(),
      secao("Education"),
      espaco(3),
      ...formacao(),
      espaco(8),
      secao("Technical Stack"),
      espaco(3),
      stack(),
      espaco(8),
      secao("Languages"),
      espaco(3),
      ...idiomas()
    ]
  }]
});

Packer.toBuffer(doc).then(buffer => {
  const tmpPath = `${workspace}/outputs/_tmp/cv_logistics_manager_stryker_en.docx`;
  fs.writeFileSync(tmpPath, buffer);
  console.log("ok");
});
