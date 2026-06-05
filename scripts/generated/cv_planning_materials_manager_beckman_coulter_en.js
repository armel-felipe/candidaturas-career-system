const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, ExternalHyperlink,
  TabStopType, TabStopPosition, AlignmentType,
  BorderStyle, LevelFormat, Numbering
} = require("docx");

const pt = n => n * 2;

const cabecalho = () => [
  new Paragraph({ children: [new TextRun({ text: "Felipe Armel Dias da Silva", bold: true, size: pt(12), font: "Arial" })], spacing: { after: 0 } }),
  new Paragraph({ children: [new ExternalHyperlink({ children: [new TextRun({ text: "linkedin.com/in/felipearmel", style: "Hyperlink", size: pt(9), font: "Arial" })], link: "https://linkedin.com/in/felipearmel" })], spacing: { after: 0 } }),
  new Paragraph({ children: [new TextRun({ text: "São Paulo, SP", size: pt(9), font: "Arial" })], spacing: { after: 0 } }),
  new Paragraph({ children: [new ExternalHyperlink({ children: [new TextRun({ text: "(11) 98674-8218", style: "Hyperlink", size: pt(9), font: "Arial" })], link: "https://wa.me/5511986748218" })], spacing: { after: 0 } }),
  new Paragraph({ children: [new ExternalHyperlink({ children: [new TextRun({ text: "armelfelipe@gmail.com", style: "Hyperlink", size: pt(9), font: "Arial" })], link: "mailto:armelfelipe@gmail.com" })], spacing: { after: 0 } })
];

function secao(text) {
  return new Paragraph({
    children: [new TextRun({ text, size: pt(12), font: "Arial" })],
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "000000", space: 1 } },
    spacing: { before: pt(6), after: pt(3) }
  });
}

function espaco(n) {
  return new Paragraph({
    children: [new TextRun({ text: "", size: pt(n), font: "Arial" })],
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
      { id: "Normal", name: "Normal", quickFormat: true, run: { font: "Arial", size: pt(9) }, paragraph: { spacing: { after: 0 } } },
      { id: "ListParagraph", name: "List Paragraph", basedOn: "Normal", quickFormat: true, run: { font: "Arial", size: pt(9) }, paragraph: { spacing: { after: 0 } } }
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
      ...cabecalho(),
      espaco(8),
      secao("Summary"),
      espaco(3),
      new Paragraph({
        children: [
      new TextRun({ text: "Supply chain executive with 25+ years across planning, operations, and regulated environments. At iFood, managed R$300MM/year OPEX and led executive S&OP; as Head, generated ", size: pt(9), font: "Arial" }),
      new TextRun({ text: "R$70M/year", bold: true, size: pt(9), font: "Arial" }),
      new TextRun({ text: " in savings. At Trifil, built S&OP from scratch, managed 40K SKUs, and reduced P&L costs by ", size: pt(9), font: "Arial" }),
      new TextRun({ text: "R$8M", bold: true, size: pt(9), font: "Arial" }),
      new TextRun({ text: ". Started in pharmaceutical GMP with ISO 9001 (0 NC). Seeking Planning & Materials Manager role in diagnostics.", size: pt(9), font: "Arial" })
        ],
        spacing: { after: 0 }
      }),
      espaco(8),
      secao("Experience"),
      espaco(3),

      cargoParagraph("Head of Operations", "WeHandle", "May 2024 – Feb 2026"),
      bullet([{ text: "Led the customer support operation with a team of 30 people, restructuring processes and impacting gross margin by ", bold: false }, { text: "15%", bold: true }, { text: " through financial simulations applied to revenue scenarios and operational cost levers." }]),
      bullet([{ text: "Drove two platform migrations to an AI-first model, implemented Zendesk, built API integrations for real-time data across three platforms, and launched WhatsApp as a primary channel." }]),
      bullet([{ text: "Reduced cost per ticket from R$4.14 to ", bold: false }, { text: "R$3.61 (−13%)", bold: true }, { text: ", increased CSAT from 85% to 92% through portfolio segmentation (+17%), and cut AHT from 20 to 8 minutes." }]),
      espaco(6),

      cargoParagraph("Director of Operations", "iFood", "Apr 2022 – Mar 2024"),
      bullet([{ text: "Managed logistics operations with a team of ~240 people and an annual OPEX budget of ", bold: false }, { text: "R$300MM/year", bold: true }, { text: ", leading monthly executive S&OP consolidating demand, supply, service level, and financial scenarios for C-level." }]),
      bullet([{ text: "Led integrated planning connecting marketing, promotions, weather, fleet availability, and geographic expansion into a single governance process, using Python, SQL, and Databricks for modeling." }]),
      bullet([{ text: "Expanded logistics coverage from 400 to ", bold: false }, { text: "800 cities", bold: true }, { text: ", reduced comparable logistics cost by 3% YoY, increased consolidated deliveries from 12% to 25%, and cut fleet unavailability in top 6 cities from 5% to 0.5%." }]),
      espaco(6),

      cargoParagraph("Head of Operations", "iFood", "Nov 2018 – Mar 2022"),
      bullet([{ text: "Led liveOps, pricing, data modeling, and fleet planning with a team of 28 people, defining city-level fleet balancing strategies to optimize SLA and cost across 800 cities." }]),
      bullet([{ text: "Built a proprietary service level simulator correlating logistics saturation, driver earnings, and delivery time, with real-time Grafana dashboards and geo-restriction tools by neighborhood." }]),
      bullet([{ text: "Generated ", bold: false }, { text: "R$70M/year", bold: true }, { text: " in savings through the simulator, reduced cancellations in Mexico by 60% by adjusting delivery radii, cut MPOS distribution lead time by 85% (14 to 2 days) and cost by 80%." }]),
      espaco(6),

      cargoParagraph("Customer Success Manager", "Renault", "Jan 2018 – Oct 2018"),
      bullet([{ text: "Restructured the CS operation from outsourced BPO to an internal team, migrating 40 outsourced positions to 8 internal professionals with higher efficiency and real-time SLA governance." }]),
      bullet([{ text: "Redesigned the digital customer contact flow, integrated CRM platforms with auto-dialers programmed in-house, and implemented ROI-based decision making for resource allocation." }]),
      bullet([{ text: "Increased lead conversion from 24% to ", bold: false }, { text: "46%", bold: true }, { text: " and secured project approval in 2 executive meetings by presenting a correctly calculated ROI." }]),
      espaco(6),

      cargoParagraph("Commercial Planning and Operations Manager", "VivaReal", "May 2015 – Dec 2017"),
      bullet([{ text: "Managed commercial planning, SDR, quality, and property onboarding with a team of 33 people and 5 direct reports, reporting to the CFO for P&L analysis and revenue scenarios. Architected the CS area from scratch — designed processes, defined onboarding cadence, and hired leadership that scaled to ", bold: false }, { text: "91 people", bold: true }, { text: " under other managers." }]),
      bullet([{ text: "Increased SDR inbound conversion from 18% to ", bold: false }, { text: "50%", bold: true }, { text: " (−40% sales cost), kept churn below 3%/month with CSAT above 92%, and recovered R$1M in delinquent receivables." }]),
      bullet([{ text: "Implemented Salesforce, digital telephony, and credit card payments, and delivered the 2018 strategic plan during the ZAP merger transition." }]),
      espaco(6),

      cargoParagraph("S&OP Coordinator", "Trifil", "Jan 2010 – Sep 2014"),
      bullet([{ text: "Built the S&OP area from scratch and sustained it for 4 years, managing ", bold: false }, { text: "40K SKUs", bold: true }, { text: " across two brands and all distribution channels, reporting OTD (On-Time Delivery), OTIF and fill rate KPIs directly to the CEO." }]),
      bullet([{ text: "Led integrated planning with corporate MRP, safety stock policies balancing service and liquidity, and an Excel VBA simulator for scenario evaluation; managed the Entrega Certa project with OTIF, fill rate, and production accuracy KPIs." }]),
      bullet([{ text: "Reduced GGF by ", bold: false }, { text: "R$8M", bold: true }, { text: " from the P&L (energy, gas, maintenance, packaging) — R$4.6M above target — while managing monthly finished goods inventory with financial trade-off decisions." }]),
      espaco(6),

      cargoParagraph("Commercial Intelligence Coordinator", "Trifil", "Jan 2009 – Dec 2009"),
      bullet([{ text: "Created the Commercial Intelligence area from scratch, structuring market data, commission tracking, and pricing support for the commercial director." }]),
      bullet([{ text: "Developed an automated Excel VBA system for order-level inventory allocation maximizing margin and revenue per order." }]),
      bullet([{ text: "Increased revenue from R$80M to ", bold: false }, { text: "R$120M/year", bold: true }, { text: " and reduced report generation time from 4 hours to 14 minutes." }]),
      espaco(6),

      cargoParagraph("Materials Planning Coordinator", "Trifil", "Nov 2007 – Dec 2008"),
      bullet([{ text: "Led materials planning for trims, packaging, and yarns, and dimensioned future production capacity with a 24-machine circular knitting equipment acquisition project." }]),
      bullet([{ text: "Implemented Strategic Sourcing across 150K+ SKUs, restructuring supplier base and negotiating cost optimization." }]),
      bullet([{ text: "Reduced purchasing costs by ", bold: false }, { text: "27%", bold: true }, { text: ", stockouts by 40%, and improved inventory turns from 8 to 6 months." }]),
      espaco(6),

      cargoParagraph("Distribution Center Coordinator", "Trifil", "Jan 2007 – Oct 2007"),
      bullet([{ text: "Managed the distribution center with picking, packing, and warehousing operations, implementing a visual replenishment system for the picking area." }]),
      bullet([{ text: "Deployed RF and Wi-Fi barcode scanners, bin location mapping, and cycle counting — unified separation and verification into a single operation." }]),
      bullet([{ text: "Improved inventory accuracy from 85% to ", bold: false }, { text: "98%", bold: true }, { text: ", increased workforce productivity by 35%, reduced losses by 30%, and cut custom order preparation time by 50%." }]),
      espaco(6),

      cargoParagraph("Processes and Systems Analyst", "Trifil", "Jan 2006 – Dec 2006"),
      bullet([{ text: "Implemented a Management by Objectives (GPD) system with PDCA, KPIs, and action plans across the entire production plant in Guarulhos, supporting all production managers." }]),
      bullet([{ text: "Led a dyeing automation project from supplier selection through economic feasibility analysis using DCF, NPV, and Payback." }]),
      bullet([{ text: "Reduced production costs by ", bold: false }, { text: "40%", bold: true }, { text: " with a real payback of 1.5 years (projected 3) and gained 12% efficiency improvement through a machine performance tracking system." }]),
      espaco(6),

      cargoParagraph("Production Operator", "Sanofi-Aventis", "Feb 1998 – Jun 2000"),
      bullet([{ text: "Started as an intern, took over the engineer's role in the second week and was permanently hired in 5 months (1-year program), operating in pharmaceutical production with automated compression machines and in-process quality control." }]),
      bullet([{ text: "Wrote ", bold: false }, { text: "180+ SOPs", bold: true }, { text: ", implemented productivity and efficiency controls for solid-dosage equipment, and participated in process and equipment validation with GMP compliance." }]),
      bullet([{ text: "Implemented preventive maintenance processes including equipment identification, tagging, and control records, ensuring fully organized production compliant with pharmaceutical standards." }]),

      espaco(8),
      secao("Technical Stack"),
      espaco(3),
      new Paragraph({
        children: [new TextRun({ text: "S&OP · MRP · Inventory Management · OTD (On-Time Delivery) · OTIF · Capacity Planning · Strategic Sourcing · Safety Stock · Python · SQL · Databricks · Grafana · Excel VBA · Zendesk · Salesforce · ERP (Infor LN, Totvs Logix) · Power BI · Tableau", size: pt(9), font: "Arial" })],
        spacing: { after: 0 }
      }),

      espaco(8),
      secao("Education"),
      espaco(3),
      new Paragraph({
        children: [new TextRun({ text: "Specialization Certificate in Corporate Strategies — BSP Business School São Paulo (2017)", size: pt(9), font: "Arial" })],
        spacing: { after: pt(2) }
      }),
      new Paragraph({
        children: [new TextRun({ text: "Chemical Engineering — Faculdades Oswaldo Cruz (2014)", size: pt(9), font: "Arial" })],
        spacing: { after: pt(2) }
      }),
      new Paragraph({
        children: [new TextRun({ text: "Six Sigma Green Belt — Setec Consulting (2020)", size: pt(9), font: "Arial" })],
        spacing: { after: pt(2) }
      }),
      new Paragraph({
        children: [new TextRun({ text: "Leadership for Leaders of Leaders — Fundação Dom Cabral (2021)", size: pt(9), font: "Arial" })],
        spacing: { after: 0 }
      }),

      espaco(8),
      secao("Languages"),
      espaco(3),
      bullet([{ text: "Portuguese — Native" }]),
      bullet([{ text: "English — Advanced" }])
    ]
  }]
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync("outputs/_tmp/cv_planning_materials_manager_beckman_coulter_en.docx", buffer);
  console.log("ok");
});
