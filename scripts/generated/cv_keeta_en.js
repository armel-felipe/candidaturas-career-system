const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, Numbering, LevelFormat,
  AlignmentType, TabStopType, TabStopPosition, BorderStyle,
  ExternalHyperlink,
} = require("docx");

// ─── helpers ───
const pt = n => n * 2; // half-points — NUNCA n * 20

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
  const children = runs.map(r =>
    new TextRun({ text: r.text, bold: r.bold || false, size: pt(9), font: "Arial" })
  );
  return new Paragraph({
    numbering: { reference: "bullets", level: 0 },
    children,
    spacing: { after: pt(2) },
  });
}

function link(text, url) {
  return new ExternalHyperlink({
    children: [new TextRun({ text, style: "Hyperlink", size: pt(9), font: "Arial" })],
    link: url,
  });
}

// ─── numbering ───
const numbering = {
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
};

// ─── document ───
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
  numbering,
  sections: [
    {
      properties: {
        page: {
          margin: { top: 720, right: 504, bottom: 720, left: 504 },
        },
      },
      children: [
        // ── Header ──
        new Paragraph({
          children: [new TextRun({ text: "Felipe Armel Dias da Silva", bold: true, size: pt(12), font: "Arial" })],
          spacing: { after: 0 },
        }),
        new Paragraph({
          children: [link("linkedin.com/in/felipearmel", "https://linkedin.com/in/felipearmel")],
          spacing: { after: 0 },
        }),
        new Paragraph({
          children: [new TextRun({ text: "São Paulo, SP", size: pt(9), font: "Arial" })],
          spacing: { after: 0 },
        }),
        new Paragraph({
          children: [link("(11) 98674-8218", "https://wa.me/5511986748218")],
          spacing: { after: 0 },
        }),
        new Paragraph({
          children: [link("armelfelipe@gmail.com", "mailto:armelfelipe@gmail.com")],
          spacing: { after: pt(4) },
        }),

        // ── Professional Summary ──
        secao("Professional Summary"),
        new Paragraph({
          children: [
            new TextRun({
              text: "Operations executive with 5+ years in food delivery marketplace operations. As Director of Operations at iFood, managed R$300M/year logistics budget across 800 cities and 30M monthly orders. Built LiveOps and incentive systems from scratch, delivered R$70M/year in savings. Created the S&OP area at Trifil, leading planning for 40K SKUs across all channels. Currently Head of Operations at wehandle, reducing cost per ticket by 13% and scaling AI-first customer service. Engineer and MBA, hands-on with SQL, Python and Databricks. Seeking a User Operations role in a high-growth international marketplace.",
              size: pt(9),
              font: "Arial",
            }),
          ],
          spacing: { after: 0 },
        }),

        espaco(8),

        // ── Experience ──
        secao("Experience"),

        // WeHandle
        espaco(3),
        cargoParagraph("Head of Operations", "wehandle", "Mai 2024 – Fev 2026"),
        bullet([
          { text: "Led customer operations and CX teams of ", bold: false },
          { text: "30", bold: true },
          { text: " people, managing end-to-end service delivery across Movidesk, CloudHumans and Zendesk platforms with a focus on AI-first scalability.", bold: false },
        ]),
        bullet([
          { text: "Drove two platform migrations to enable AI-first scalability, integrating support data to the company datalake via API and building real-time dashboards with Metabase and Python.", bold: false },
        ]),
        bullet([
          { text: "Reduced cost per ticket from R$4.14 to R$3.61 (", bold: false },
          { text: "−13%", bold: true },
          { text: "), improved CSAT from 85% to 92%, and achieved 95% SLA adherence.", bold: false },
        ]),

        espaco(6),

        // iFood — Director
        cargoParagraph("Director of Operations", "iFood", "Abr 2022 – Mar 2024"),
        bullet([
          { text: "Led marketplace logistics operations with ~", bold: false },
          { text: "240", bold: true },
          { text: " people and a R$300M/year budget, covering ", bold: false },
          { text: "800", bold: true },
          { text: " cities and ", bold: false },
          { text: "30M", bold: true },
          { text: " monthly orders across Brazil.", bold: false },
        ]),
        bullet([
          { text: "Structured executive S&OP governance integrating demand, supply, fleet capacity and P&L scenarios, using Python, SQL, Databricks and Tableau for cross-functional decision-making.", bold: false },
        ]),
        bullet([
          { text: "Reduced comparable logistics cost by ", bold: false },
          { text: "3% YoY", bold: true },
          { text: ", expanded fleet coverage from 400 to 800 cities, and increased order batching from 12% to 25% reaching operational breakeven.", bold: false },
        ]),

        espaco(6),

        // iFood — Head
        cargoParagraph("Head of Operations", "iFood", "Nov 2018 – Mar 2022"),
        bullet([
          { text: "Built the LiveOps area from scratch with real-time monitoring (Grafana), dynamic fleet pricing, and incentive management across ", bold: false },
          { text: "352", bold: true },
          { text: " cities.", bold: false },
        ]),
        bullet([
          { text: "Designed and ran A/B tests on driver incentive models (zone promotions, gamification, elasticity pricing) using SQL, Python and Databricks.", bold: false },
        ]),
        bullet([
          { text: "Delivered ", bold: false },
          { text: "R$70M/year", bold: true },
          { text: " savings with a proprietary service-level simulator and reduced MPOS distribution lead time from 14 to 2 days (", bold: false },
          { text: "−85%", bold: true },
          { text: ").", bold: false },
        ]),

        espaco(6),

        // Renault
        cargoParagraph("Customer Success Manager", "Renault do Brasil", "Jan 2018 – Out 2018"),
        bullet([
          { text: "Led the transition from an outsourced BPO (40 agents) to an in-house 8-person team, redesigning the lead contact flow and qualification methodology.", bold: false },
        ]),
        bullet([
          { text: "Integrated dialer systems and real-time SLA governance, using Excel/VBA and Power BI for performance intelligence.", bold: false },
        ]),
        bullet([
          { text: "Increased lead-to-sale conversion from ", bold: false },
          { text: "24% to 46%", bold: true },
          { text: " with data-driven funnel management.", bold: false },
        ]),

        espaco(6),

        // VivaReal
        cargoParagraph("Commercial Planning and Operations Manager", "VivaReal", "Mai 2015 – Dez 2017"),
        bullet([
          { text: "Architected the Customer Success area from scratch: designed processes, onboarding rules, SDR pipeline and KPIs; area scaled to ", bold: false },
          { text: "91", bold: true },
          { text: " people under dedicated leadership.", bold: false },
        ]),
        bullet([
          { text: "Improved SDR inbound conversion from ", bold: false },
          { text: "18% to 50%", bold: true },
          { text: " while reducing cost of sales by 40%, achieving sub-3% monthly churn and ", bold: false },
          { text: "80%", bold: true },
          { text: " NPS.", bold: false },
        ]),
        bullet([
          { text: "Managed pricing strategy and commission policies with direct interface to CFO, and recovered ", bold: false },
          { text: "R$1M", bold: true },
          { text: " in revenue through delinquency campaigns.", bold: false },
        ]),

        espaco(6),

        // Trifil
        cargoParagraph("S&OP Coordinator", "Trifil (Scalina)", "Jan 2010 – Set 2014"),
        bullet([
          { text: "Built the S&OP area from scratch, sustaining end-to-end planning rituals for ", bold: false },
          { text: "4 years", bold: true },
          { text: " across ", bold: false },
          { text: "40K", bold: true },
          { text: " SKUs, two brands and all distribution channels.", bold: false },
        ]),
        bullet([
          { text: "Managed corporate MRP, capacity analysis, safety stock policies and strategic sourcing of 150K+ SKUs, reducing stockouts by ", bold: false },
          { text: "40%", bold: true },
          { text: " and purchase costs by ", bold: false },
          { text: "27%", bold: true },
          { text: ".", bold: false },
        ]),
        bullet([
          { text: "Reduced General Manufacturing Expenses by ", bold: false },
          { text: "R$8M", bold: true },
          { text: " (P&L impact) through energy, gas and packaging optimization.", bold: false },
        ]),

        espaco(8),

        // ── Education ──
        secao("Education"),
        espaco(3),
        cargoParagraph("Specialization Certificate in Corporate Strategies — BSP Business School São Paulo", "", "2017"),
        bullet([{ text: "MBA Corporate Strategy", bold: false }]),
        cargoParagraph("Chemical Engineer — Faculdades Oswaldo Cruz", "", "2014"),
        bullet([{ text: "Bachelor's Degree in Chemical Engineering", bold: false }]),
        cargoParagraph("Chemical Technician — SENAI Mario Amato", "", "1997"),
        bullet([{ text: "Technical degree in Chemistry", bold: false }]),

        espaco(8),

        // ── Tech Stack ──
        secao("Tech Stack"),
        espaco(3),
        new Paragraph({
          children: [new TextRun({ text: "SQL · Python · Databricks · Tableau · Grafana · Metabase · Power BI · Excel/VBA", size: pt(9), font: "Arial" })],
          spacing: { after: 0 },
        }),

        espaco(8),

        // ── Languages ──
        secao("Languages"),
        espaco(3),
        bullet([{ text: "Portuguese — Native", bold: false }]),
        bullet([{ text: "English — Advanced", bold: false }]),
      ],
    },
  ],
});

// ─── output ───
const outputPath = path.resolve("outputs/_tmp/cv_user_operations_manager_keeta_en.docx");
Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync(outputPath, buffer);
  console.log("ok");
  console.log("Output:", outputPath);
});