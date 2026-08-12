const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, ExternalHyperlink,
  TabStopType, TabStopPosition, LevelFormat, AlignmentType,
  BorderStyle
} = require("docx");

// half-points: 9pt = 18, 12pt = 24
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

const doc = new Document({
  styles: {
    default: {
      document: { run: { font: "Arial", size: pt(9) } }
    },
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
            children: [new TextRun({ text: "linkedin.com/in/felipearmel", size: pt(9), font: "Arial", style: "Hyperlink" })],
            link: "https://linkedin.com/in/felipearmel"
          })
        ],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [new TextRun({ text: "São Paulo, SP", size: pt(9), font: "Arial" })],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [
          new ExternalHyperlink({
            children: [new TextRun({ text: "(11) 98674-8218", size: pt(9), font: "Arial", style: "Hyperlink" })],
            link: "https://wa.me/5511986748218"
          })
        ],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [
          new ExternalHyperlink({
            children: [new TextRun({ text: "armelfelipe@gmail.com", size: pt(9), font: "Arial", style: "Hyperlink" })],
            link: "mailto:armelfelipe@gmail.com"
          })
        ],
        spacing: { after: 0 }
      }),
      espaco(8),

      // === SUMMARY ===
      secao("Summary"),
      espaco(3),
      new Paragraph({
        children: [
          new TextRun({ text: "Operations executive with 8+ years in customer service and partner operations management, combining hands-on BPO management, CS performance metrics, and data-driven operational strategy. As Head of Operations at WeHandle, improved CSAT from 85% to 92%, reduced cost per ticket by 13%, and drove 15% gross margin impact. At iFood, managed a R$300M annual budget as Director of Operations, scaled logistics from 400 to 800 cities, and delivered R$70M/year in savings through a custom fleet service-level simulator. Architected the CS area at VivaReal from scratch, scaling it to 91 people with NPS reaching 80% and CSAT above 92%. Seeks a Partner Operations Manager role where operational rigor, partner accountability, and CX strategy drive measurable performance at scale.", size: pt(9), font: "Arial" })
        ],
        spacing: { after: 0 }
      }),
      espaco(8),

      // === EXPERIENCE ===
      secao("Experience"),
      espaco(3),

      // --- WeHandle ---
      cargoParagraph("Head of Operations", "WeHandle", "May 2024 – Feb 2026"),
      espaco(2),
      bullet([
        { text: "Led the customer service operations for a 30-person team, owning partner and service performance across CSAT, SLA, quality, productivity, and operational efficiency as direct KPIs reported to leadership.", bold: false }
      ]),
      bullet([
        { text: "Integrated data from three support platforms (Zendesk, CloudHumans, Movidesk) via API ahead of the company's data team, driving real-time performance analysis with SQL and Metabase, and implemented AI-powered automation and WhatsApp channel to scale the operation.", bold: false }
      ]),
      bullet([
        { text: "Improved CSAT from 85% to 92%, maintained SLA at 95% of tickets, reduced average handling time from 20 to 8 minutes, lowered cost per ticket by 13% (from R$4.14 to R$3.60), and drove ", bold: false },
        { text: "15% gross margin impact", bold: true },
        { text: " through strategic segmentation and operational optimization.", bold: false }
      ]),
      espaco(6),

      // --- iFood Director ---
      cargoParagraph("Director of Operations", "iFood", "Apr 2022 – Mar 2024"),
      espaco(2),
      bullet([
        { text: "Managed the full P&L for delivery costs with a R$300M annual budget, leading a team of ~240 people across FieldOps, Payments, and New Business while owning partner performance accountability against service metrics.", bold: false }
      ]),
      bullet([
        { text: "Conducted executive S&OP monthly sessions with C-level leadership, using SQL, Python, Databricks, and Tableau for data-driven storytelling, performance trend analysis, and scenario planning that translated strategy into actionable partner-level goals.", bold: false }
      ]),
      bullet([
        { text: "Reduced fleet unavailability from 5% to 1% (top 6 cities: 5.4% to 0.5%), expanded coverage from 400 to 800 cities, increased batched deliveries from 12% to 25%, reduced comparable logistics cost by 3% YoY, and delivered ", bold: false },
        { text: "R$70M/year in savings", bold: true },
        { text: " through a custom fleet service-level simulator with root cause analysis.", bold: false }
      ]),
      espaco(6),

      // --- iFood Head ---
      cargoParagraph("Head of Operations", "iFood", "Nov 2018 – Mar 2022"),
      espaco(2),
      bullet([
        { text: "Led a 28-person team covering liveOps, fleet planning, pricing, and data modeling, serving as the single point of contact representing operations across Delivery and cross-functional teams.", bold: false }
      ]),
      bullet([
        { text: "Built a fleet capacity planning simulator using Excel VBA that balanced supply and demand by city with real-time Grafana dashboards, and designed a MPOS distribution process combining eligibility criteria, fraud controls, and logistics optimization.", bold: false }
      ]),
      bullet([
        { text: "Reduced MPOS distribution cost by 80% and delivery time from 14 to 2 days, scaled MPOS availability from 70% to 97%, and decreased Mexico cancellation rates by 60% by adjusting delivery radius per neighborhood.", bold: false }
      ]),
      espaco(6),

      // --- Renault ---
      cargoParagraph("Customer Success Manager", "Renault do Brasil", "Jan 2018 – Oct 2018"),
      espaco(2),
      bullet([
        { text: "Managed the transition of two outsourced BPO operations (40 PAS) to an in-house model, creating a more scalable structure with greater control over quality, SLA, and operational efficiency.", bold: false }
      ]),
      bullet([
        { text: "Applied data analysis and reporting with Excel, VBA, and Power BI to generate sales intelligence, build action plans, program dialers based on performance capacity, and implement real-time SLA governance.", bold: false }
      ]),
      bullet([
        { text: "Increased lead conversion from 24% to 46% in two days by restructuring the sales funnel, and achieved the highest performance ever recorded in the operation through objective qualification methodology and structured process management.", bold: false }
      ]),
      espaco(6),

      // --- VivaReal ---
      cargoParagraph("Commercial Planning and Operations Manager", "VivaReal", "May 2015 – Dec 2017"),
      espaco(2),
      bullet([
        { text: "Architected the entire customer success area from scratch — designed onboarding journeys, customer support processes, and hired the leadership team that scaled the operation to 91 people with CSAT above 92% and NPS reaching 80%.", bold: false }
      ]),
      bullet([
        { text: "Managed CRM operations using Salesforce for pipeline, portfolio, and pricing, led SDR team that increased inbound conversion from 18% to 50%, and implemented digital telephony for post-sales support.", bold: false }
      ]),
      bullet([
        { text: "Reduced churn to below 3% per month across the used-property BU, recovered R$1M through collections campaigns, and reduced sales costs by 40% through optimized SDR lead qualification and routing processes.", bold: false }
      ]),
      espaco(8),

      // === EDUCATION ===
      secao("Education"),
      espaco(3),
      bullet([
        { text: "Specialization Certificate in Corporate Strategies — BSP Business School São Paulo (2017)", bold: false }
      ]),
      bullet([
        { text: "Bachelor's Degree in Chemical Engineering — Faculdades Oswaldo Cruz (2014)", bold: false }
      ]),
      bullet([
        { text: "Six Sigma Green Belt — Setec Consulting (2020)", bold: false }
      ]),
      bullet([
        { text: "ILEad Leadership Program — Fundação Dom Cabral (2021)", bold: false }
      ]),
      espaco(8),

      // === TECHNICAL STACK ===
      secao("Technical Stack"),
      espaco(3),
      new Paragraph({
        children: [
          new TextRun({ text: "SQL · Python · Tableau · Salesforce · Databricks · Grafana · Metabase · Zendesk · Excel/VBA · Power BI", size: pt(9), font: "Arial" })
        ],
        spacing: { after: 0 }
      }),
      espaco(8),

      // === LANGUAGES ===
      secao("Languages"),
      espaco(3),
      bullet([
        { text: "Portuguese — Native", bold: false }
      ]),
      bullet([
        { text: "English — Advanced", bold: false }
      ])
    ]
  }]
});

const OUTPUT_TMP = "outputs/_tmp/cv_partner_operations_manager_airbnb.docx";

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync(OUTPUT_TMP, buffer);
  console.log("ok");
});
