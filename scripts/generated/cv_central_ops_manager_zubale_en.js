const fs = require("fs");
const docx = require("docx");
const { Document, Packer, Paragraph, TextRun, ExternalHyperlink, BorderStyle, TabStopType, TabStopPosition, AlignmentType, LevelFormat, HeaderFooter, Footer } = docx;

// Half-points: 9pt = 18, 12pt = 24
const pt = n => n * 2;

function secao(text) {
  return new Paragraph({
    children: [new TextRun({ text, size: pt(12), font: "Arial" })],
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "000000", space: 1 } },
    spacing: { before: pt(6), after: pt(3) }
  });
}

function espaco(ptSize = 6) {
  return new Paragraph({
    children: [new TextRun({ text: "", size: pt(ptSize), font: "Arial" })],
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

function link(text, url) {
  return new ExternalHyperlink({
    children: [new TextRun({ text, style: "Hyperlink", size: pt(9), font: "Arial" })],
    link: url
  });
}

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
      // === HEADER ===
      new Paragraph({
        children: [new TextRun({ text: "Felipe Armel Dias da Silva", bold: true, size: pt(12), font: "Arial" })],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [link("linkedin.com/in/felipearmel", "https://linkedin.com/in/felipearmel")],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [new TextRun({ text: "São Paulo, SP", size: pt(9), font: "Arial" })],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [link("(11) 98674-8218", "https://wa.me/5511986748218")],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [link("armelfelipe@gmail.com", "mailto:armelfelipe@gmail.com")],
        spacing: { after: 0 }
      }),

      espaco(8),

      // === SUMMARY ===
      secao("Summary"),
      new Paragraph({
        children: [new TextRun({
          text: "Operations executive with 27+ years combining hands-on technical execution and senior leadership across marketplace logistics, CX, and supply chain. As Director at iFood, managed a R$300MM budget and 240-person team, expanding coverage to 800 cities and building a proprietary simulator driving R$70M/year in savings. As Head at wehandle, personally integrated 3 platforms via REST APIs, reducing cost-per-ticket by 13% and raising CSAT to 92%. Seeking a Central Ops Manager role at the intersection of data integration, automation, and team leadership.",
          size: pt(9), font: "Arial"
        })],
        spacing: { after: 0 }
      }),

      espaco(8),

      // === EXPERIÊNCIA ===
      secao("Experience"),

      // 1 — wehandle
      espaco(3),
      cargoParagraph("Head of Operations", "wehandle", "May 2024 – Feb 2026"),
      bullet([
        { text: "Led customer operations and CX while personally integrating data from ", bold: false },
        { text: "3 platform APIs", bold: true },
        { text: " (Movidesk, CloudHumans, Zendesk) ahead of the data team — wrote the integrations myself.", bold: false }
      ]),
      bullet([
        { text: "Developed REST API integrations, implemented AI-driven chatbot automation and WhatsApp channel, used Python and SQL for real-time operational analytics.", bold: false }
      ]),
      bullet([
        { text: "Reduced cost-per-ticket from R$4.14 to R$3.61 (", bold: false },
        { text: "−13%", bold: true },
        { text: "), raised CSAT from 85% to 92%, cut average handling time from 20min to 8min (", bold: false },
        { text: "−60%", bold: true },
        { text: "), and improved gross margin by 15%.", bold: false }
      ]),

      espaco(6),

      // 2 — iFood Director
      cargoParagraph("Director of Operations", "iFood", "Apr 2022 – Mar 2024"),
      bullet([
        { text: "Managed logistics operations with ", bold: false },
        { text: "~240 people", bold: true },
        { text: " and a ", bold: false },
        { text: "R$300MM annual budget", bold: true },
        { text: " across FieldOps, Payments, and New Business — full P&L accountability with weekly variance reading.", bold: false }
      ]),
      bullet([
        { text: "Led monthly executive S&OP with Python, SQL, and Databricks modeling; developed forecasting models and managed trade-offs between cost and SLA through rolling forecast and scenario analysis.", bold: false }
      ]),
      bullet([
        { text: "Expanded coverage from 400 to 800 cities, reduced comparable logistics cost by ", bold: false },
        { text: "3% YoY", bold: true },
        { text: ", maintained SLA across ", bold: false },
        { text: "30M monthly orders", bold: true },
        { text: ".", bold: false }
      ]),

      espaco(6),

      // 3 — iFood Head
      cargoParagraph("Head of Operations", "iFood", "Nov 2018 – Mar 2022"),
      bullet([
        { text: "Led liveOps, pricing, data modeling, and fleet planning with a ", bold: false },
        { text: "28-person team", bold: true },
        { text: ", defining business rules for a marketplace logistics network.", bold: false }
      ]),
      bullet([
        { text: "Built real-time metrics in Grafana, developed a proprietary simulator in Python and SQL on Databricks, designed dynamic pricing and incentive models by zone.", bold: false }
      ]),
      bullet([
        { text: "Generated ", bold: false },
        { text: "R$70M/year in savings", bold: true },
        { text: " through the simulator, reduced Mexico cancellations by 60%, distributed MPOS to 352 cities with zero financial loss.", bold: false }
      ]),

      espaco(6),

      // 4 — Renault
      cargoParagraph("Customer Success Manager", "Renault do Brasil", "Jan 2018 – Oct 2018"),
      bullet([
        { text: "Led the migration of a BPO operation (40 agents) to an in-house structure with ", bold: false },
        { text: "8 people", bold: true },
        { text: ", approved the ROI case in 2 executive meetings.", bold: false }
      ]),
      bullet([
        { text: "Applied SQL, Power BI, and Excel/VBA for data intelligence, implemented SLA governance, and configured dialers personally.", bold: false }
      ]),
      bullet([
        { text: "Increased lead conversion from 24% to ", bold: false },
        { text: "46%", bold: true },
        { text: " and stabilized the operation within two days.", bold: false }
      ]),

      espaco(6),

      // 5 — VivaReal
      cargoParagraph("Commercial Planning and Operations Manager", "VivaReal", "May 2015 – Dec 2017"),
      bullet([
        { text: "Led commercial planning, operations, and CS architecture with ", bold: false },
        { text: "33 people", bold: true },
        { text: " across Quality, SDR, and property listings — architected the CS area from scratch.", bold: false }
      ]),
      bullet([
        { text: "Used SQL for automated dashboards, designed onboarding flows and customer journey governance, integrated Salesforce with operational pipelines.", bold: false }
      ]),
      bullet([
        { text: "Increased SDR inbound conversion from 18% to ", bold: false },
        { text: "50%", bold: true },
        { text: ", reached ", bold: false },
        { text: "NPS of 80%", bold: true },
        { text: " and CSAT above 92%, reduced sales cost by 40%.", bold: false }
      ]),

      espaco(8),

      // === EDUCATION ===
      secao("Education"),
      bullet([
        { text: "Specialization Certificate in Corporate Strategies — BSP Business School São Paulo (2017)", bold: false }
      ]),
      bullet([
        { text: "Chemical Engineer — Faculdades Oswaldo Cruz (2014)", bold: false }
      ]),
      bullet([
        { text: "Six Sigma Green Belt — Setec Consulting (2020)", bold: false }
      ]),

      espaco(8),

      // === TECHNICAL SKILLS ===
      secao("Technical Skills"),
      new Paragraph({
        children: [new TextRun({
          text: "SQL · Python · Databricks · Grafana · BigQuery · n8n · REST APIs · Power BI · Tableau · Metabase · Google Cloud Platform · Salesforce · Zendesk · Advanced Excel/VBA",
          size: pt(9), font: "Arial"
        })],
        spacing: { after: 0 }
      }),

      espaco(8),

      // === LANGUAGES ===
      secao("Languages"),
      bullet([{ text: "Portuguese — Native", bold: false }]),
      bullet([{ text: "English — Advanced", bold: false }])
    ]
  }]
});

Packer.toBuffer(doc).then(buffer => {
  const outPath = "outputs/_tmp/cv_central_ops_manager_zubale_en.docx";
  fs.writeFileSync(outPath, buffer);
  console.log("ok");
});