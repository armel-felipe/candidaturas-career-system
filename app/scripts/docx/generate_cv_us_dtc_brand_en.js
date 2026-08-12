const { Document, Packer, Paragraph, TextRun, ExternalHyperlink, TabStopType, TabStopPosition, AlignmentType, BorderStyle, LevelFormat } = require('docx');
const fs = require('fs');
const path = require('path');

const pt = n => n * 2; // half-points

const workspace = process.env.CAREER_WORKSPACE || process.cwd();
const outputDir = process.env.CAREER_OUTPUTS || path.join(workspace, "outputs");

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

function paragraph(text, options = {}) {
  return new Paragraph({
    children: [new TextRun({ text, size: pt(options.size || 9), bold: !!options.bold, font: "Arial" })],
    spacing: { after: 0 }
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
    spacing: { after: 0 }
  });
}

const doc = new Document({
  creator: "Felipe Armel",
  title: "Felipe Armel - Head of Business Operations - US DTC Brand",
  description: "CV for Head of Business Operations at US DTC Brand (via Paired)",
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
  styles: {
    default: {
      document: { run: { font: "Arial", size: pt(9) } }
    },
    paragraphStyles: [
      { id: "Normal", name: "Normal", quickFormat: true,
        run: { font: "Arial", size: pt(9) },
        paragraph: { spacing: { after: 0 } } },
      { id: "ListParagraph", name: "List Paragraph", basedOn: "Normal", quickFormat: true,
        run: { font: "Arial", size: pt(9) },
        paragraph: { spacing: { after: 0 } } }
    ]
  },
  sections: [{
    properties: {
      page: { margin: { top: 720, right: 504, bottom: 720, left: 504 } }
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
      paragraph("Senior Operations Executive with 20+ years driving operational structure, customer support excellence, and scalable processes across digital marketplaces and DTC environments. As Head of Operations at wehandle, rebuilt customer support from the ground up — AI-first automation, WhatsApp channels, platform migrations — delivering CSAT from 85% to 92%, 95% SLA, and 13% cost reduction. As Director of Operations at iFood, managed a R$300M/year logistics budget leading 240 people across 800 cities (30M monthly orders). Architected the Customer Success area at VivaReal from zero to 91 people with NPS of 80%. Built S&OP from scratch at Trifil. Strengths in fixing messy systems, defining SLA governance, building dashboards, reducing ticket volume through root cause analysis, and acting as the operational bridge between support, product, and leadership."),
      espaco(8),

      // --- EXPERIENCE ---
      secao("Experience"),
      espaco(3),

      // WeHandle
      cargoParagraph("Head of Operations", "wehandle", "May 2024 – Feb 2026"),
      bullet([{ text: "Rebuilt customer support operation from scratch: led 30-person team through two platform migrations toward an AI-first model, deploying chatbot automation and WhatsApp channels — reducing cost per contact by ", bold: false }, { text: "13%", bold: true }, { text: " (R$4.14 to R$3.61) and improving CSAT from ", bold: false }, { text: "85% to 92%", bold: true }, { text: " with ", bold: false }, { text: "95% SLA", bold: true }, { text: "." }]),
      bullet([{ text: "Reduced ticket volume by ", bold: false }, { text: "8%", bold: true }, { text: " through structured root cause analysis and insights directed to the Product team, creating a CX board (ClickUp) that cut backlog by ", bold: false }, { text: "60%", bold: true }, { text: " and raised execution SLA from 67% to ", bold: false }, { text: "85%", bold: true }, { text: "." }]),
      bullet([{ text: "Connected three support platforms (Movidesk, CloudHumans, Zendesk) via API to the company datalake — delivering real-time dashboards 3 months ahead of the centralized data team without dependency on other departments." }]),
      espaco(6),

      // iFood Diretor
      cargoParagraph("Director of Operations", "iFood", "Apr 2022 – Mar 2024"),
      bullet([{ text: "Led 240-person team across Field Operations, Payments, and New Business, managing a P&L with a ", bold: false }, { text: "R$300M/year", bold: true }, { text: " logistics budget — driving operational efficiency that reduced comparable costs by 3% YoY while maintaining SLA stability at scale." }]),
      bullet([{ text: "Expanded logistics service coverage from ", bold: false }, { text: "400 to 800 cities", bold: true }, { text: ", reduced fleet unavailability from 5% to 1% nationally, and increased order consolidation from 12% to ", bold: false }, { text: "25%", bold: true }, { text: " — reaching operational breakeven through data-driven capacity planning." }]),
      bullet([{ text: "Conducted monthly executive S&OP rhythm connecting marketing, promotions, fleet availability, and operations into a single planning process — translating risks and opportunities into short-term executive directives with clear trade-offs between cost and service level." }]),
      espaco(6),

      // iFood Head
      cargoParagraph("Head of Operations", "iFood", "Nov 2018 – Mar 2022"),
      bullet([{ text: "Built and led 28-person team spanning LiveOps, pricing, data modeling, and fleet planning — scaling from ", bold: false }, { text: "800K to 30M", bold: true }, { text: " monthly orders across 800 cities in a hyper-growth environment." }]),
      bullet([{ text: "Developed a service level simulation model that maintained operational stability while generating ", bold: false }, { text: "R$70M/year", bold: true }, { text: " in savings, combining fleet capacity planning, pricing elasticity testing, and real-time Grafana dashboards to correlate logistics saturation with delivery SLA." }]),
      bullet([{ text: "Implemented an operations monitoring tower in Mexico reducing cancellations by ", bold: false }, { text: "60%", bold: true }, { text: ", and established automated reporting tools for operational decision-making across pricing, fleet, and supply." }]),
      espaco(6),

      // VivaReal
      cargoParagraph("Commercial Planning and Operations Manager", "VivaReal", "May 2015 – Dec 2017"),
      bullet([{ text: "Architected the Customer Success area from the ground up — designed onboarding flows, process workflows, and hired leadership; the area scaled to ", bold: false }, { text: "91 people", bold: true }, { text: " and achieved ", bold: false }, { text: "NPS of 80%", bold: true }, { text: ", CSAT above ", bold: false }, { text: "92%", bold: true }, { text: ", and monthly churn below ", bold: false }, { text: "3%", bold: true }, { text: "." }]),
      bullet([{ text: "Acted as operational bridge between Product, CFO, and Commercial teams — building SQL-based dashboards and automated Excel reporting that reduced report generation time from 4 hours to 14 minutes for daily commercial decisions." }]),
      bullet([{ text: "Transformed SDR lead conversion from 18% to ", bold: false }, { text: "50%", bold: true }, { text: ", reducing cost of sales by 40% through data-driven lead timing analysis and structured qualification processes." }]),
      espaco(6),

      // Trifil
      cargoParagraph("S&OP Coordinator", "Trifil (Scalina)", "Jan 2010 – Sep 2014"),
      bullet([{ text: "Built the S&OP function from scratch — managing ", bold: false }, { text: "40K SKUs", bold: true }, { text: " across two brands and all distribution channels, with monthly executive S&OP rhythm connecting demand, supply, cost, and scenario analysis for C-level decision-making." }]),
      bullet([{ text: "Drove process optimization through the Entrega Certa project, defining KPIs (OTIF, fill rate, production accuracy) and reducing General Manufacturing Expenses by ", bold: false }, { text: "R$8M", bold: true }, { text: " from the P&L through structured root cause analysis and cross-functional workflow refinement." }]),
      bullet([{ text: "Managed Strategic Sourcing for 150K+ SKUs, reducing procurement costs by 27% and stockouts by 40%, while improving inventory turnover from 8 to 6 months." }]),
      espaco(8),

      // --- EDUCATION ---
      secao("Education"),
      espaco(3),
      bullet([{ text: "Specialization Certificate in Corporate Strategies — BSP Business School São Paulo (2017)" }]),
      bullet([{ text: "Chemical Engineering — Faculdades Oswaldo Cruz (2014)" }]),
      espaco(8),

      // --- Technical Skills ---
      secao("Technical Skills"),
      espaco(3),
      paragraph("Python · SQL · Databricks · Grafana · Tableau · Power BI · Excel/VBA · Zendesk · Salesforce · ClickUp · ERP Infor LN"),
      espaco(8),

      // --- Competencies ---
      secao("Competencies"),
      espaco(3),
      paragraph("Customer Support Management · SLA Definition and Governance · Process Automation · Ticket Volume Reduction · SOP Documentation · Dashboard and Reporting · Remote Team Management · Operational Scalability · Shopify Backend Workflows · DTC E-commerce Operations · Fulfillment Operations · Supplier Coordination · Escalation Management · Cross-functional Leadership · Data-driven Decision Making"),
      espaco(8),

      // --- LANGUAGES ---
      secao("Languages"),
      espaco(3),
      bullet([{ text: "Portuguese — Native" }]),
      bullet([{ text: "English — Advanced" }]),
    ]
  }]
});

const outputName = process.argv[2] || "felipe_armel_cv_us_dtc_brand_en.docx";
const outputPath = path.join(outputDir, outputName);
fs.mkdirSync(outputDir, { recursive: true });

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync(outputPath, buffer);
  console.log("OK:" + outputPath);
}).catch(err => {
  console.error("ERROR:" + err.message);
  process.exit(1);
});
