const fs = require("fs");
const path = require("path");
const docx = require("docx");
const {
  Document, Packer, Paragraph, TextRun, ExternalHyperlink,
  TabStopType, TabStopPosition, LevelFormat, AlignmentType,
  BorderStyle
} = docx;

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
        children: [
          new TextRun({ text: "Felipe Armel Dias da Silva", bold: true, size: pt(12), font: "Arial" })
        ],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [
          new ExternalHyperlink({
            children: [new TextRun({ text: "linkedin.com/in/felipearmel", style: "Hyperlink", size: pt(9), font: "Arial" })],
            link: "https://linkedin.com/in/felipearmel"
          })
        ],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [
          new TextRun({ text: "São Paulo, SP", size: pt(9), font: "Arial" })
        ],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [
          new ExternalHyperlink({
            children: [new TextRun({ text: "(11) 98674-8218", style: "Hyperlink", size: pt(9), font: "Arial" })],
            link: "https://wa.me/5511986748218"
          })
        ],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [
          new ExternalHyperlink({
            children: [new TextRun({ text: "armelfelipe@gmail.com", style: "Hyperlink", size: pt(9), font: "Arial" })],
            link: "mailto:armelfelipe@gmail.com"
          })
        ],
        spacing: { after: 0 }
      }),

      espaco(8),

      // === SUMMARY ===
      secao("Summary"),
      new Paragraph({
        children: [
          new TextRun({
            text: "Senior executive who built operations from scratch across three companies and scaled them at iFood. As Head of Operations at wehandle, reported directly to the CEO and built CX from the ground up, reducing cost per contact 13% and impacting gross margin 15%. As Director at iFood, owned R$300MM annual P&L with C-level interface through monthly S&OP executive management, leading 240 people. Built areas from zero where no infrastructure existed. Seeking a Chief of Staff role combining hands-on structure-building with strategic execution.",
            size: pt(9), font: "Arial"
          })
        ],
        spacing: { after: 0 }
      }),

      espaco(8),

      // === EXPERIENCE ===
      secao("Experience"),

      // --- wehandle ---
      cargoParagraph("Head of Operations", "wehandle", "May 2024 – Feb 2026"),
      bullet([
        { text: "Reported directly to the CEO and built the CX and support operation from scratch with full autonomy — ", bold: false },
        { text: "led a 30-person team", bold: true },
        { text: ", segmented customer portfolio by risk and value, created the CX area, and connected bug insights to product roadmap, reducing backlog 60%.", bold: false }
      ]),
      bullet([
        { text: "Integrated data from three support platforms via API ", bold: false },
        { text: "before the data team existed", bold: true },
        { text: ", implemented AI-automation and WhatsApp channel replacing phone, and maintained real-time dashboards with Python, SQL, and Metabase.", bold: false }
      ]),
      bullet([
        { text: "Reduced cost per contact from R$4.14 to R$3.61 (", bold: false },
        { text: "−13%", bold: true },
        { text: "), impacted ", bold: false },
        { text: "15% of gross margin", bold: true },
        { text: ", raised CSAT from 85% to 92%, kept SLA at 95%, and cut average handling time from 20 min to 8 min.", bold: false }
      ]),

      espaco(6),

      // --- iFood Director ---
      cargoParagraph("Director of Operations", "iFood", "Apr 2022 – Mar 2024"),
      bullet([
        { text: "Managed the logistics operations of Latin America's largest food marketplace with a ", bold: false },
        { text: "240-person team and R$300MM annual P&L", bold: true },
        { text: ", leading monthly S&OP executive meeting consolidating demand, fleet, cost, and service level to protect EBITDA targets — direct C-level interface.", bold: false }
      ]),
      bullet([
        { text: "Led S&OP governance connecting marketing, weather, fleet availability, geographic expansion, and supply into a single planning process; modeled feasibility scenarios with Python, SQL, and Databricks for decision-making.", bold: false }
      ]),
      bullet([
        { text: "Expanded coverage from 400 to ", bold: false },
        { text: "800 cities", bold: true },
        { text: ", reduced comparable logistics cost ", bold: false },
        { text: "3% YoY", bold: true },
        { text: ", maintained SLA stable at ", bold: false },
        { text: "30M orders/month", bold: true },
        { text: ", and increased order batching from 12% to 25%, reaching operational breakeven.", bold: false }
      ]),

      espaco(6),

      // --- iFood Head ---
      cargoParagraph("Head of Operations", "iFood", "Nov 2018 – Mar 2022"),
      bullet([
        { text: "Built and led the LiveOps, fleet planning, and pricing areas — ", bold: false },
        { text: "28 people", bold: true },
        { text: " — with direct interface to VP on real-time metrics, fleet balance, and incentive models.", bold: false }
      ]),
      bullet([
        { text: "Created a service level simulator in Excel/VBA enabling scenario analysis for fleet decisions and designed MPOS distribution rules covering fraud risk and courier qualification.", bold: false }
      ]),
      bullet([
        { text: "Delivered ", bold: false },
        { text: "R$70M/year in savings", bold: true },
        { text: " through the simulator, scaled MPOS to ", bold: false },
        { text: "352 cities with zero financial loss", bold: true },
        { text: ", reduced delivery time from 14 to 2 days, and kept MPOS availability at 97%.", bold: false }
      ]),

      espaco(6),

      // --- Renault ---
      cargoParagraph("Customer Success Manager", "Renault do Brasil", "Jan 2018 – Oct 2018"),
      bullet([
        { text: "Internalized customer service operations — migrated 40 professionals from 2 BPOs to an ", bold: false },
        { text: "8-person in-house team", bold: true },
        { text: " with higher B2B quality control and SLA governance.", bold: false }
      ]),
      bullet([
        { text: "Structured data-driven lead qualification with strict SDR funnel control, programmed dialers for performance optimization, and real-time SLA governance.", bold: false }
      ]),
      bullet([
        { text: "Increased lead", bold: false },
        { text: " conversion from 24% to 46%", bold: true },
        { text: " and stabilized the operation within two days using data and process redesign.", bold: false }
      ]),

      espaco(6),

      // --- VivaReal ---
      cargoParagraph("Commercial Planning and Operations Manager", "VivaReal", "May 2015 – Dec 2017"),
      bullet([
        { text: "Responsible for strategic planning, goal deployment, and commercial operations — ", bold: false },
        { text: "architected the CS area", bold: true },
        { text: " that scaled to ", bold: false },
        { text: "91 people", bold: true },
        { text: " with churn below 3%/month and NPS 80%.", bold: false }
      ]),
      bullet([
        { text: "Designed SDR inbound prospecting process with lead enrichment and intelligent routing; built onboarding playbook and CS procedures from scratch.", bold: false }
      ]),
      bullet([
        { text: "Increased inbound B2B conversion from 18% to ", bold: false },
        { text: "50%", bold: true },
        { text: ", reduced sales cost by ", bold: false },
        { text: "40%", bold: true },
        { text: ", and participated in the merger with ZAP delivering the 2018 strategic plan.", bold: false }
      ]),

      espaco(6),

      // --- Trifil (Scalina) ---
      cargoParagraph("S&OP Coordinator", "Scalina (Trifil)", "Jan 2010 – Sep 2014"),
      bullet([
        { text: "Created the S&OP area from scratch and sustained the rhythms for ", bold: false },
        { text: "4 years", bold: true },
        { text: ", managing ", bold: false },
        { text: "40K SKUs", bold: true },
        { text: " of finished goods across distributor, retail, key accounts, and franchise channels.", bold: false }
      ]),
      bullet([
        { text: "Built Excel/VBA simulators for MRP validation and scenario analysis, led Strategic Sourcing of 150K+ items, and conducted economic feasibility analysis for equipment acquisition (NPV, payback).", bold: false }
      ]),
      bullet([
        { text: "Reduced GGF by ", bold: false },
        { text: "R$8MM", bold: true },
        { text: ", cut purchasing costs by 27%, reduced stockouts by 40%, increased inventory turnover from 8 to 6 months, and delivered payback in 1.5 years vs 3 projected.", bold: false }
      ]),

      espaco(8),

      // === COMPETENCIES ===
      secao("Competencies"),
      new Paragraph({
        children: [
          new TextRun({
            text: "Building Operations from Scratch · P&L Management / Budget · C-Level Interface · Compliance / Regulatory Quality (ISO 9001) · Feasibility / ROI Projections (NPV, Payback) · B2B Prospecting / Sales Funnel · LGPD / Sensitive Data · Process Automation · Geographic Expansion · Institutional Relations · Data Analysis (SQL, Python) · Complex Projects / Deal Execution · Team Leadership · S&OP Governance",
            size: pt(9), font: "Arial"
          })
        ],
        spacing: { after: 0 }
      }),

      espaco(8),

      // === EDUCATION ===
      secao("Education"),
      new Paragraph({
        children: [
          new TextRun({ text: "Specialization Certificate in Corporate Strategies — BSP Business School São Paulo (2017)", size: pt(9), font: "Arial" })
        ],
        spacing: { after: pt(2) }
      }),
      new Paragraph({
        children: [
          new TextRun({ text: "Chemical Engineer — Faculdades Oswaldo Cruz (2014)", size: pt(9), font: "Arial" })
        ],
        spacing: { after: pt(2) }
      }),
      new Paragraph({
        children: [
          new TextRun({ text: "Chemical Technician — SENAI Mario Amato (1997)", size: pt(9), font: "Arial" })
        ],
        spacing: { after: 0 }
      }),

      espaco(8),

      // === TECHNICAL STACK ===
      secao("Technical Stack"),
      new Paragraph({
        children: [
          new TextRun({ text: "Python · SQL · Databricks · Grafana · Excel/VBA · Tableau · Metabase · Salesforce · Zendesk · ERP (Infor LN, BAAN IV, Totvs Logix) · Power BI", size: pt(9), font: "Arial" })
        ],
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
  const workspace = path.resolve(__dirname, "..", "..");
  const outPath = path.join(workspace, "outputs", "_tmp", "cv_chief_of_staff_dehaze_en.docx");
  fs.writeFileSync(outPath, buffer);
  console.log("ok");
});
