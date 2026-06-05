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
  const outputName = process.argv[2] || "felipe_armel_cv_operations_performance_manager_wellhub_en.docx";
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
      config: [
        {
          reference: "bullets",
          levels: [
            {
              level: 0,
              format: LevelFormat.BULLET,
              text: "\u2022",
              alignment: AlignmentType.LEFT,
              style: { paragraph: { indent: { left: 360, hanging: 180 } } },
            },
          ],
        },
      ],
    },
    sections: [
      {
        properties: {
          page: {
            margin: { top: 720, right: 504, bottom: 720, left: 504 },
          },
        },
        children: [
          // --- HEADER ---
          paragraph("Felipe Armel Dias da Silva", { bold: true, size: 12 }),
          hyperlink("linkedin.com/in/felipearmel", "https://linkedin.com/in/felipearmel"),
          paragraph("São Paulo, SP"),
          hyperlink("wa.me/5511986748218", "https://wa.me/5511986748218"),
          hyperlink("armelfelipe@gmail.com", "mailto:armelfelipe@gmail.com"),
          espaco(4),

          // --- SUMMARY ---
          secao("Summary"),
          espaco(3),
          paragraph("Senior Operations Executive with 20+ years translating operational metrics into high-impact action plans that drive NPS, CSAT, and client retention. As Director of Operations at iFood, managed a R$300M/year logistics budget and led 240 people across a hyper-growth operation scaling from 400 to 800 cities. As Head of Operations at wehandle, drove AI-first business transformation achieving 13% cost reduction and CSAT improvement from 85% to 92%. Architected the Customer Success area at VivaReal from zero to 91 people. Built the S&OP function at Trifil from scratch. Experience spanning Operations Performance Management, Business Transformation, Dashboard Creation and Analytics, SLA governance, cross-functional collaboration, Incident and Risk Monitoring frameworks between Customer Success, Product, and CX, and data-driven decision-making. Seeks an Operations Performance Manager role where strategic metrics, team capacity, and operational excellence meet scalable client impact."),
          espaco(8),

          // --- EXPERIÊNCIA ---
          secao("Experience"),
          espaco(3),

          // Wehandle
          cargoParagraph("Head of Operations", "wehandle", "May 2024 – Feb 2026"),
          bullet([{ text: "Led a 30-person customer support operation, defining SLAs (", bold: false }, { text: "95%", bold: true }, { text: "), CSAT and TME metrics, and managing team capacity during peak periods — translating operational metrics into action plans that directly improved client satisfaction and retention across the Brazilian portfolio." }]),
          bullet([{ text: "Drove a business transformation agenda with two platform migrations toward an AI-first model, deploying chatbot automation and WhatsApp channels — reducing cost per contact from R$4.14 to R$3.61 (", bold: false }, { text: "13%", bold: true }, { text: ") — while creating end-to-end frameworks to monitor incidents, risks, and process bottlenecks proactively." }]),
          bullet([{ text: "Achieved CSAT improvement from ", bold: false }, { text: "85% to 92%", bold: true }, { text: ", reduced Mean Time to Engagement from 20 to 8 minutes, and lowered contact rate by ", bold: false }, { text: "8%", bold: true }, { text: " through strategic client segmentation and insights directed to the Product team, serving as the senior escalation point for critical cases." }]),
          espaco(6),

          // iFood Diretor
          cargoParagraph("Director of Operations", "iFood", "Apr 2022 – Mar 2024"),
          bullet([{ text: "Led a 240-person team across Field Operations, Payments, and New Business, managing a P&L with a ", bold: false }, { text: "R$300M/year", bold: true }, { text: " logistics budget — serving as the strategic bridge between Operations, Customer Success, Product, and CX to align operational execution with business strategy." }]),
          bullet([{ text: "Oversaw the creation of real-time dashboards (Grafana, Tableau, Databricks) correlating logistics saturation, delivery SLA, and costs — providing the executive leadership team with clear visibility into operational health, trends, and trade-offs between service level and EBITDA." }]),
          bullet([{ text: "Expanded logistics service coverage from ", bold: false }, { text: "400 to 800 cities", bold: true }, { text: ", reduced fleet unavailability from 5% to ", bold: false }, { text: "1%", bold: true }, { text: " nationally, and increased order consolidation rate from 12% to ", bold: false }, { text: "25%", bold: true }, { text: ", reaching operational breakeven through data-driven capacity planning and structured root cause analysis." }]),
          espaco(6),

          // VivaReal
          cargoParagraph("Commercial Planning and Operations Manager", "VivaReal", "May 2015 – Dec 2017"),
          bullet([{ text: "Architected the Customer Success area from the ground up — designed onboarding flows, process workflows, and hired the leadership team; the area scaled to ", bold: false }, { text: "91 people", bold: true }, { text: " and became the operational backbone for client retention and satisfaction in the Brazilian market." }]),
          bullet([{ text: "Acted as a strategic interface with Product, CFO, and Commercial teams, building automated dashboards (SQL, Excel) and influencing the product roadmap based on the Voice of the Customer (VoC) to drive structural process improvements." }]),
          bullet([{ text: "Delivered an ", bold: false }, { text: "NPS of 80%", bold: true }, { text: ", CSAT above ", bold: false }, { text: "92%", bold: true }, { text: ", and monthly churn below ", bold: false }, { text: "3%", bold: true }, { text: " by implementing data-driven customer segmentation and rigorous SLA governance across the entire client lifecycle." }]),
          espaco(6),

          // iFood Head
          cargoParagraph("Head of Operations", "iFood", "Nov 2018 – Mar 2022"),
          bullet([{ text: "Built and led a 28-person team spanning LiveOps, regional operations, pricing, data modeling, and fleet planning in a hyper-growth environment — from ", bold: false }, { text: "800K to 30M", bold: true }, { text: " monthly orders across 800 cities." }]),
          bullet([{ text: "Implemented an operations monitoring tower in Mexico reducing cancellations by ", bold: false }, { text: "60%", bold: true }, { text: ", created real-time Grafana dashboards to correlate logistics saturation with SLA, and established AI-driven tools and automated reporting for operational decision-making." }]),
          bullet([{ text: "Developed a simulation model that maintained service levels under control while generating ", bold: false }, { text: "R$70M/year", bold: true }, { text: " in savings, balancing fleet capacity, pricing elasticity, and delivery radius through data-driven trade-off analysis." }]),
          espaco(6),

          // Trifil
          cargoParagraph("S&OP Coordinator", "Trifil (Scalina)", "Jan 2010 – Sep 2014"),
          bullet([{ text: "Built the S&OP function from scratch — managing ", bold: false }, { text: "40K SKUs", bold: true }, { text: " across two brands and all distribution channels, coordinating the monthly executive S&OP rhythm with demand, supply, cost, and scenario analysis for C-level decision-making." }]),
          bullet([{ text: "Drove business transformation through structured root cause analysis for the Entrega Certa project, defining KPIs for OTIF, fill rate, and production accuracy — codifying lessons learned into structural process improvements." }]),
          bullet([{ text: "Reduced ", bold: false }, { text: "R$8M", bold: true }, { text: " in General Manufacturing Expenses from the P&L through continuous workflow refinement and cross-functional collaboration between commercial, production, and procurement teams." }]),
          espaco(8),

          // --- EDUCATION ---
          secao("Education"),
          espaco(3),
          bullet([{ text: "Specialization Certificate in Corporate Strategies — BSP Business School São Paulo (2017)" }]),
          bullet([{ text: "Chemical Engineering — Faculdades Oswaldo Cruz (2014)" }]),
          espaco(8),

          // --- TECH STACK ---
          secao("Technical Skills"),
          espaco(3),
          paragraph("Python · SQL · Tableau · Grafana · Databricks · AI Tools (Chatbot, IA) · ClickUp · Excel/VBA · Google Suite · Dashboard Creation"),
          espaco(8),

          // --- LANGUAGES ---
          secao("Languages"),
          espaco(3),
          bullet([{ text: "Portuguese — Native" }]),
          bullet([{ text: "English — Advanced" }]),
        ],
      },
    ],
  });

  const buffer = await Packer.toBuffer(doc);
  const outPath = path.join(outputDir, outputName);
  fs.writeFileSync(outPath, buffer);
  console.log(`CV generated: ${outPath}`);
  return outPath;
}

main().catch(err => {
  console.error(err.message);
  process.exit(1);
});
