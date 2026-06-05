const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, ExternalHyperlink,
  TabStopType, TabStopPosition, LevelFormat, AlignmentType, BorderStyle,
} = require("docx");

const pt = n => n * 2;

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
    link: url,
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
      // Header
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

      espaco(6),

      // Summary
      secao("Summary"),
      espaco(3),
      new Paragraph({
        children: [new TextRun({
          text: "Chemical engineer with an MBA in Corporate Strategy and 20+ years of experience leading operations, supply chain, and customer success across tech marketplaces (iFood), SaaS (WeHandle), proptech (VivaReal), and industrial manufacturing (Trifil). Expertise in last mile capacity planning, S&OP, strategic sourcing, and data-driven operational cost optimization with budgets of R$300MM+. Built capacity planning frameworks, proprietary simulation tools, and cross-functional planning processes that balanced cost, service level, and scalability. Seeking a Capacity Planning Manager role to lead OTR capacity planning in a high-volume logistics environment.",
          size: pt(9), font: "Arial"
        })],
        spacing: { after: 0 }
      }),

      espaco(8),

      // Experience
      secao("Experience"),
      espaco(3),

      // --- wehandle ---
      cargoParagraph("Head of Operations", "wehandle", "May 2024 – Feb 2026"),
      bullet([
        { text: "Led the customer support operation and CX team of ~30 people, restructuring processes and implementing AI-powered automation that directly impacted " },
        { text: "gross margin by 15%", bold: true },
        { text: "." }
      ]),
      bullet([
        { text: "Implemented AI chatbot and WhatsApp channel (reducing cost per contact from R$1.04 to R$0.56), migrated platforms to Zendesk, and integrated operations data with the company datalake via API for real-time dashboards and capacity tracking." }
      ]),
      bullet([
        { text: "Reduced average handling time from 20 to 8 minutes, raised CSAT from 85% to 92%, achieved " },
        { text: "95% SLA on tickets", bold: true },
        { text: ", and cut contact rate by 8% through product-driven insights." }
      ]),

      espaco(6),

      // --- iFood Director ---
      cargoParagraph("Director of Operations", "iFood", "Apr 2022 – Mar 2024"),
      bullet([
        { text: "Led last mile capacity planning and logistics operations with ~240 people and a " },
        { text: "R$300MM/year OPEX budget", bold: true },
        { text: ", defining capacity targets per channel (online, cloud, dedicated) at strategic and tactical levels across short, mid, and long-term horizons." }
      ]),
      bullet([
        { text: "Structured monthly executive S&OP connecting demand, supply, cost, and service level scenarios; modeled capacity planning with Python, SQL, and Databricks; created Grafana dashboards for real-time volume vs capacity tracking and gap mitigation." }
      ]),
      bullet([
        { text: "Expanded geographic coverage from 400 to 800 cities, reduced comparable logistics cost by 3% YoY, increased batched deliveries from 12% to 25%, and cut fleet unavailability from " },
        { text: "5% to 1%", bold: true },
        { text: " (top 6 cities: 5.4% to 0.5%)." }
      ]),

      espaco(6),

      // --- iFood Head ---
      cargoParagraph("Head of Operations", "iFood", "Nov 2018 – Mar 2022"),
      bullet([
        { text: "Built last mile capacity planning from scratch, managing a 28-person team across liveOps, fleet planning, pricing, and data modeling; defined share of delivery channels based on cost, productivity, and availability." }
      ]),
      bullet([
        { text: "Created a proprietary service level simulator using SQL, Python, Databricks, and Tableau, enabling productivity-based capacity modeling and route radius optimization by city and channel." }
      ]),
      bullet([
        { text: "Generated " },
        { text: "R$70M/year in savings", bold: true },
        { text: " through the capacity simulator, reduced Mexico cancellations by 60% via route optimization, and cut MPOS distribution cost by 80% with lead time reduced from 14 to 2 days." }
      ]),

      espaco(6),

      // --- VivaReal ---
      cargoParagraph("Commercial Planning and Operations Manager", "VivaReal", "May 2015 – Dec 2017"),
      bullet([
        { text: "Managed commercial planning, SDR operations, and customer onboarding for a proptech marketplace, leading 33 people with 5 direct reports across quality, SDR, and property listing teams." }
      ]),
      bullet([
        { text: "Structured the customer success area from scratch — designed processes, defined onboarding journeys, and hired leadership — scaling the operation to " },
        { text: "91 people", bold: true },
        { text: " under management." }
      ]),
      bullet([
        { text: "Increased SDR inbound conversion from 18% to 50% (reducing sales cost by 40%), kept churn below 3%/month, and achieved " },
        { text: "80% NPS and 92% CSAT", bold: true },
        { text: "." }
      ]),

      espaco(6),

      // --- Trifil S&OP ---
      cargoParagraph("S&OP Coordinator", "Trifil (Scalina)", "Jan 2010 – Sep 2014"),
      bullet([
        { text: "Created the S&OP area from scratch and sustained it for 4 years, managing " },
        { text: "40K SKUs", bold: true },
        { text: " across two brands and all distribution channels, with corporate MRP and production capacity analysis." }
      ]),
      bullet([
        { text: "Implemented process improvement with PDCA, KPIs, and action plans across the entire production plant; built an MRP/S&OP scenario simulator in Excel VBA for capacity and inventory planning." }
      ]),
      bullet([
        { text: "Reduced GGF (general manufacturing expenses) by " },
        { text: "R$8M from P&L", bold: true },
        { text: " optimizing energy, gas, maintenance, and packaging — achieving R$4.6M above the annual target." }
      ]),

      espaco(6),

      // --- Trifil Materials ---
      cargoParagraph("Materials Planning Coordinator", "Trifil (Scalina)", "Nov 2007 – Dec 2008"),
      bullet([
        { text: "Led materials planning for " },
        { text: "150K+ SKUs", bold: true },
        { text: ", managing procurement of trims, packaging, and yarns across domestic and international supply chains." }
      ]),
      bullet([
        { text: "Implemented Strategic Sourcing methodology with automated systems in Excel/VBA for inventory allocation and supplier performance tracking." }
      ]),
      bullet([
        { text: "Reduced purchasing costs by 27%, cut stock-out rates by 40%, and improved inventory turnover from 8 to " },
        { text: "6 months", bold: true },
        { text: "." }
      ]),

      espaco(8),

      // Education
      secao("Education"),
      espaco(3),
      new Paragraph({
        children: [new TextRun({ text: "Specialization Certificate in Corporate Strategies — BSP Business School São Paulo (2017)", size: pt(9), font: "Arial" })],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [new TextRun({ text: "Chemical Engineering — Faculdades Oswaldo Cruz (2014)", size: pt(9), font: "Arial" })],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [new TextRun({ text: "Six Sigma Green Belt — Setec Consulting (2020)", size: pt(9), font: "Arial" })],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [new TextRun({ text: "ILEad Leadership Program — Fundação Dom Cabral (2021)", size: pt(9), font: "Arial" })],
        spacing: { after: 0 }
      }),

      espaco(8),

      // Technical Stack
      secao("Technical Stack"),
      espaco(3),
      new Paragraph({
        children: [new TextRun({ text: "SQL · Python · Data Analytics · Databricks · PySpark · Grafana · Tableau · Power BI · Excel/VBA · Zendesk · Salesforce", size: pt(9), font: "Arial" })],
        spacing: { after: 0 }
      }),

      espaco(8),

      // Languages
      secao("Languages"),
      espaco(3),
      bullet([{ text: "Portuguese — Native" }]),
      bullet([{ text: "English — Advanced" }]),
    ]
  }]
});

Packer.toBuffer(doc).then(buffer => {
  const outPath = "/Users/mac/llm server/projetos/candidaturas/outputs/_tmp/cv_capacity_planning_manager_en.docx";
  fs.writeFileSync(outPath, buffer);
  console.log("ok");
});
