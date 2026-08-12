const fs = require("fs");
const docx = require("docx");
const {
  Document, Packer, Paragraph, TextRun, ExternalHyperlink,
  TabStopType, TabStopPosition, AlignmentType, LevelFormat,
  BorderStyle, Numbering, HeadingLevel
} = docx;

// half-points — NUNCA n * 20
const pt = n => n * 2;

// Seção com borda inferior
function secao(text) {
  return new Paragraph({
    children: [new TextRun({ text, size: pt(12), font: "Arial" })],
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "000000", space: 1 } },
    spacing: { before: pt(6), after: pt(3) }
  });
}

// Espaçador
function espaco(ptSize = 6) {
  return new Paragraph({
    children: [new TextRun({ text: "", size: pt(ptSize), font: "Arial" })],
    spacing: { after: 0 }
  });
}

// Cargo + empresa com período alinhado à direita
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

// Bullet com array de runs [{text, bold}]
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

// Link externo para o cabeçalho
function linkParagraph(label, url) {
  return new Paragraph({
    children: [
      new ExternalHyperlink({
        children: [new TextRun({ text: label, style: "Hyperlink", size: pt(9), font: "Arial" })],
        link: url
      })
    ],
    spacing: { after: 0 }
  });
}

const doc = new Document({
  styles: {
    default: { document: { run: { font: "Arial", size: pt(9) } } },
    paragraphStyles: [
      { id: "Normal", name: "Normal", quickFormat: true,
        run: { font: "Arial", size: pt(9) },
        paragraph: { spacing: { after: 0 } } },
      { id: "ListParagraph", name: "List Paragraph", basedOn: "Normal", quickFormat: true,
        run: { font: "Arial", size: pt(9) },
        paragraph: { spacing: { after: 0 } } }
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
      // === HEADER ===
      new Paragraph({
        children: [new TextRun({ text: "Felipe Armel Dias da Silva", bold: true, size: pt(12), font: "Arial" })],
        spacing: { after: 0 }
      }),
      linkParagraph("linkedin.com/in/felipearmel", "https://linkedin.com/in/felipearmel"),
      new Paragraph({
        children: [new TextRun({ text: "São Paulo, SP", size: pt(9), font: "Arial" })],
        spacing: { after: 0 }
      }),
      linkParagraph("(11) 98674-8218", "https://wa.me/5511986748218"),
      linkParagraph("armelfelipe@gmail.com", "mailto:armelfelipe@gmail.com"),
      espaco(6),

      // === RESUMO ===
      secao("Summary"),
      espaco(3),
      new Paragraph({
        children: [
          new TextRun({ text: "Engineering background with nearly 20 years building and scaling operations — logistics, support, and customer success — across startups and large-scale marketplaces. At iFood, cut logistics cost by 3% YoY as Director of Operations (budget: R$300MM/year). At wehandle, raised CSAT from 85% to 92% and reduced cost per ticket by 13% as Head of Operations. Combines data-driven decisions, process improvement, and P&L discipline. Seeking a Director of Client Operations role.", size: pt(9), font: "Arial" })
        ],
        spacing: { after: 0 }
      }),
      espaco(8),

      // === EXPERIÊNCIA ===
      secao("Experience"),
      espaco(3),

      // --- WeHandle ---
      cargoParagraph("Head of Operations", "wehandle", "May 2024 – Feb 2026"),
      bullet([
        { text: "Led client operations and support with a team of 30, providing support team leadership and real-time performance monitoring across SLA (95%), CSAT, AHT, and cost per ticket in a B2B SaaS environment." }
      ]),
      bullet([
        { text: "Drove process improvement through root cause analysis, client segmentation (+17% CSAT), omnichannel expansion (WhatsApp cutting cost per contact from R$1.04 to R$0.56), AI-humanized chatbot deployment, and two platform migrations to Zendesk." }
      ]),
      bullet([
        { text: "Raised CSAT from 85% to 92%, reduced AHT from 20 to 8 minutes, and cut cost per ticket from R$4.14 to R$3.61 (", bold: false },
        { text: "−13%", bold: true },
        { text: "), directly improving gross margin by ", bold: false },
        { text: "15%", bold: true },
        { text: ".", bold: false }
      ]),
      espaco(6),

      // --- iFood Diretor ---
      cargoParagraph("Director of Operations", "iFood", "Apr 2022 – Mar 2024"),
      bullet([
        { text: "Managed logistics operations P&L with ~240 people across Field Operations, Payments, and New Business, overseeing a ", bold: false },
        { text: "R$300MM/year", bold: true },
        { text: " OPEX budget.", bold: false }
      ]),
      bullet([
        { text: "Led executive S&OP with C-level stakeholders, integrating marketing, promotions, weather, fleet capacity, and geographic expansion into a single planning process with trade-off scenarios between cost and service level." }
      ]),
      bullet([
        { text: "Expanded logistics coverage from 400 to 800 cities, reduced comparable logistics cost by ", bold: false },
        { text: "3% YoY", bold: true },
        { text: ", and cut fleet unavailability from 5% to ", bold: false },
        { text: "0.5%", bold: true },
        { text: " in top 6 cities.", bold: false }
      ]),
      espaco(6),

      // --- iFood Head ---
      cargoParagraph("Head of Operations", "iFood", "Nov 2018 – Mar 2022"),
      bullet([
        { text: "Led liveOps, regional operations, pricing, data modeling, and fleet planning with a cross-functional team of 28, reporting directly to the VP of Operations." }
      ]),
      bullet([
        { text: "Built a service-level simulator and real-time Grafana dashboards correlating logistics saturation with delivery time and driver earnings to optimize fleet capacity decisions." }
      ]),
      bullet([
        { text: "Delivered ", bold: false },
        { text: "R$70M/year", bold: true },
        { text: " in savings through fleet capacity optimization, cut MPOS distribution cost by ", bold: false },
        { text: "80%", bold: true },
        { text: " (lead time 14 → 2 days), and reduced delivery cancellations in Mexico by ", bold: false },
        { text: "60%", bold: true },
        { text: " through radius adjustments.", bold: false }
      ]),
      espaco(6),

      // --- VivaReal ---
      cargoParagraph("Commercial Planning and Operations Manager", "VivaReal", "May 2015 – Dec 2017"),
      bullet([
        { text: "Architected the Customer Success area from scratch — designed processes, defined onboarding journeys, and hired leadership; CS operation scaled to ", bold: false },
        { text: "91 people", bold: true },
        { text: " under others' management.", bold: false }
      ]),
      bullet([
        { text: "Restructured the SDR inbound pipeline and built cross-functional stakeholder management with Product and CFO, prioritizing roadmap items for Salesforce and integrations." }
      ]),
      bullet([
        { text: "Raised inbound SDR conversion from 18% to 50%, cut sales cost by ", bold: false },
        { text: "40%", bold: true },
        { text: ", recovered R$1M in receivables, and reached ", bold: false },
        { text: "NPS 80%", bold: true },
        { text: " with CSAT above ", bold: false },
        { text: "92%", bold: true },
        { text: ".", bold: false }
      ]),
      espaco(8),

      // === FORMAÇÃO ===
      secao("Education"),
      espaco(3),
      new Paragraph({
        children: [new TextRun({ text: "Specialization Certificate in Corporate Strategies — BSP Business School São Paulo (2017)", size: pt(9), font: "Arial" })],
        numbering: { reference: "bullets", level: 0 },
        spacing: { after: pt(2) }
      }),
      new Paragraph({
        children: [new TextRun({ text: "Bachelor's Degree in Chemical Engineering — Faculdades Oswaldo Cruz (2014)", size: pt(9), font: "Arial" })],
        numbering: { reference: "bullets", level: 0 },
        spacing: { after: pt(2) }
      }),
      new Paragraph({
        children: [new TextRun({ text: "Executive Leadership — Fundação Dom Cabral (2021)", size: pt(9), font: "Arial" })],
        numbering: { reference: "bullets", level: 0 },
        spacing: { after: pt(2) }
      }),
      new Paragraph({
        children: [new TextRun({ text: "Six Sigma Green Belt — Setec Consulting (2020)", size: pt(9), font: "Arial" })],
        numbering: { reference: "bullets", level: 0 },
        spacing: { after: pt(2) }
      }),
      espaco(8),

      // === STACK TÉCNICA ===
      secao("Technical Stack"),
      espaco(3),
      new Paragraph({
        children: [new TextRun({ text: "Excel/VBA · SQL · Python · Databricks · Grafana · Salesforce · Zendesk · Power BI · Tableau · Metabase", size: pt(9), font: "Arial" })],
        spacing: { after: 0 }
      }),
      espaco(8),

      // === IDIOMAS ===
      secao("Languages"),
      espaco(3),
      new Paragraph({
        children: [new TextRun({ text: "Portuguese — Native", size: pt(9), font: "Arial" })],
        numbering: { reference: "bullets", level: 0 },
        spacing: { after: pt(2) }
      }),
      new Paragraph({
        children: [new TextRun({ text: "English — Advanced", size: pt(9), font: "Arial" })],
        numbering: { reference: "bullets", level: 0 },
        spacing: { after: pt(2) }
      })
    ]
  }]
});

Packer.toBuffer(doc).then(buffer => {
  const outPath = "outputs/_tmp/cv_director_of_client_operations_wellhub_en.docx";
  fs.writeFileSync(outPath, buffer);
  console.log("ok");
});