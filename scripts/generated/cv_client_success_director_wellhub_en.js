const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, ExternalHyperlink,
  TabStopType, TabStopPosition, LevelFormat, AlignmentType,
  BorderStyle
} = require("docx");

// half-points — NUNCA n * 20
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
        children: [
          new TextRun({ text: "Felipe Armel Dias da Silva", bold: true, size: pt(12), font: "Arial" })
        ],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [
          new ExternalHyperlink({
            link: "https://linkedin.com/in/felipearmel",
            children: [new TextRun({ text: "linkedin.com/in/felipearmel", size: pt(9), font: "Arial", style: "Hyperlink" })]
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
            link: "https://wa.me/5511986748218",
            children: [new TextRun({ text: "(11) 98674-8218", size: pt(9), font: "Arial", style: "Hyperlink" })]
          })
        ],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [
          new ExternalHyperlink({
            link: "mailto:armelfelipe@gmail.com",
            children: [new TextRun({ text: "armelfelipe@gmail.com", size: pt(9), font: "Arial", style: "Hyperlink" })]
          })
        ],
        spacing: { after: 0 }
      }),

      // === SUMMARY (≤480 chars) ===
      espaco(8),
      secao("Summary"),
      espaco(3),
      new Paragraph({
        children: [new TextRun({
          text: "Chemical Engineer with BSP Corporate Strategies specialization and +20 years bridging customer success and data-driven strategy across SaaS and enterprise B2B. Architected CS at VivaReal (91 people, NPS 80%, churn <3%). Served as CS Manager at Renault (conversion 24%→46%) and drove CX at WeHandle (CSAT 85%→92%, −13% cost). As iFood Director, managed R$300MM OPEX and led executive business reviews with C-level. Seeking Client Success Director role to build and scale enterprise CS teams.",
          size: pt(9), font: "Arial"
        })],
        spacing: { after: 0 }
      }),

      // === EXPERIENCE ===
      espaco(8),
      secao("Experience"),
      espaco(3),

      // WeHandle
      cargoParagraph("Head of Operations", "WeHandle", "May 2024 – Feb 2026"),
      bullet([
        { text: "Led the overall Customer Support and CX operations for a B2B SaaS platform, overseeing a 30-person team across support, quality, and CX functions, owning P&L impact and driving strategy from service delivery to product experience." }
      ]),
      bullet([
        { text: "Drove two platform migrations toward an AI-first architecture using Zendesk, chatbot automation, and humanized AI — connected support data directly to the company's datalake via API to enable real-time dashboards without waiting on the data engineering team." }
      ]),
      bullet([
        { text: "Raised CSAT from " },
        { text: "85% to 92%", bold: true },
        { text: ", achieved 95% SLA adherence, reduced average handle time from 20 to 8 minutes, cut total cost per ticket from R$4.14 to R$3.61 (" },
        { text: "−13%", bold: true },
        { text: "), and reduced product backlog by " },
        { text: "60%", bold: true },
        { text: " with a structured CX-to-product feedback loop — increasing execution SLA from 67% to 85%." }
      ]),
      espaco(6),

      // iFood Director
      cargoParagraph("Director of Operations", "iFood", "Apr 2022 – Mar 2024"),
      bullet([
        { text: "Managed the P&L for the delivery cost line with a R$300MM annual OPEX budget, leading a 240-person organization spanning Field Operations, Payment Methods, and New Business units with direct " },
        { text: "people management", bold: true },
        { text: " across multiple team leads — reporting to C-level stakeholders." }
      ]),
      bullet([
        { text: "Led the monthly executive " },
        { text: "Business Reviews", bold: true },
        { text: " (QBRs) consolidating Brazil-wide demand, supply, logistics cost, service level, and scenario analysis — delivering " },
        { text: "executive engagement", bold: true },
        { text: " by translating operational data into strategic ROI narratives for CFO and VP-level decision-making, including trade-offs between cost and service level under normal and critical scenarios." }
      ]),
      bullet([
        { text: "Reduced comparable logistics cost by " },
        { text: "3% YoY", bold: true },
        { text: ", expanded service coverage from " },
        { text: "400 to 800", bold: true },
        { text: " cities, lowered fleet unavailability from " },
        { text: "5% to 1%", bold: true },
        { text: " nationally (top 6 cities: 5.4% to 0.5%), and increased batched deliveries from " },
        { text: "12% to 25%", bold: true },
        { text: " — achieving logistical breakeven while protecting EBITDA targets." }
      ]),
      espaco(6),

      // iFood Head
      cargoParagraph("Head of Operations", "iFood", "Nov 2018 – Mar 2022"),
      bullet([
        { text: "Led a 28-person multidisciplinary team across LiveOps, Regional Operations, Pricing, Data Modeling, and Fleet Planning — building real-time monitoring infrastructure and data models that scaled the logistics operation from " },
        { text: "800K to 30M", bold: true },
        { text: " monthly orders." }
      ]),
      bullet([
        { text: "Built a service-level simulator using SQL, Python, and Databricks that saved " },
        { text: "R$70MM/year", bold: true },
        { text: " by optimizing fleet availability and delivery radius — created real-time Grafana dashboards correlating logistics saturation, NDS, and driver earnings for LiveOps decision-making." }
      ]),
      bullet([
        { text: "Reduced MPOS distribution cost by " },
        { text: "80%", bold: true },
        { text: " and delivery time from " },
        { text: "14 to 2 days", bold: true },
        { text: ", raised device availability from 70% to 97%, implemented the Mexico operations tower reducing cancellations by " },
        { text: "60%", bold: true },
        { text: ", and established fleet planning balance across cities with cloud fleet models." }
      ]),
      espaco(6),

      // Renault
      cargoParagraph("Customer Success Manager", "Renault do Brasil", "Jan 2018 – Oct 2018"),
      bullet([
        { text: "Managed the B2B-to-B2C customer journey for lead qualification and sales conversion, transitioning the operation from outsourced BPO model (40 people across 2 agencies) to an in-house 8-person team — rebuilding processes, SLA governance, and real-time operational controls from scratch." }
      ]),
      bullet([
        { text: "Redesigned the digital contact flow integrating CRM platforms, dialer systems, and BI tools — established data-driven lead qualification methodology and real-time SLA governance for response time and follow-up cadence." }
      ]),
      bullet([
        { text: "Increased lead-to-sales conversion from " },
        { text: "24% to 46%", bold: true },
        { text: " within months of the internalization — achieving the turnaround in two days through immediate data deployment, systematic funnel management, and automated dialing programmed from the team's own operational insights." }
      ]),
      espaco(6),

      // VivaReal
      cargoParagraph("Commercial Planning and Operations Manager", "VivaReal", "May 2015 – Dec 2017"),
      bullet([
        { text: "Architected the Customer Success area from the ground up — designed onboarding workflows, defined client journey stages, established NPS and CSAT measurement, and hired the leadership team that scaled the operation to " },
        { text: "91 people", bold: true },
        { text: " (never managed CS directly; served as its architect and process designer)." }
      ]),
      bullet([
        { text: "Drove end-to-end " },
        { text: "account management", bold: true },
        { text: " and " },
        { text: "revenue growth", bold: true },
        { text: ": built the SDR lead qualification process raising inbound conversion from " },
        { text: "18% to 50%", bold: true },
        { text: " (−40% sales cost), created a structured onboarding cadence, segmented the client base for tailored engagement, and implemented Salesforce for pipeline, pricing, payments, and automated renewals." }
      ]),
      bullet([
        { text: "Delivered measurable retention and revenue outcomes: reduced monthly churn " },
        { text: "below 3%", bold: true },
        { text: ", achieved " },
        { text: "NPS of 80%", bold: true },
        { text: " and " },
        { text: "CSAT above 92%", bold: true },
        { text: ", recovered " },
        { text: "R$1M", bold: true },
        { text: " in overdue accounts through a dedicated collections campaign, and delivered the 2018 strategic plan during the ZAP merger transition." }
      ]),

      // === EDUCATION ===
      espaco(8),
      secao("Education"),
      espaco(3),
      bullet([{ text: "Specialization Certificate in Corporate Strategies — BSP Business School São Paulo (2017)" }]),
      bullet([{ text: "Chemical Engineering — Faculdades Oswaldo Cruz (2014)" }]),
      bullet([{ text: "Six Sigma Green Belt — Setec Consulting (2020)" }]),

      // === TECH STACK ===
      espaco(8),
      secao("Technical Stack"),
      espaco(3),
      new Paragraph({
        children: [new TextRun({
          text: "SQL · Python · Databricks · Grafana · Salesforce · Zendesk · Power BI · Tableau · Metabase · CRM Platforms · AI Chatbot · Excel/VBA",
          size: pt(9), font: "Arial"
        })],
        spacing: { after: 0 }
      }),

      // === LANGUAGES ===
      espaco(8),
      secao("Languages"),
      espaco(3),
      bullet([{ text: "Portuguese — Native" }]),
      bullet([{ text: "English — Advanced" }])
    ]
  }]
});

const workspace = path.resolve(__dirname, "..", "..");
const outPath = path.join(workspace, "outputs", "_tmp", "cv_client_success_director_wellhub_en.docx");
Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync(outPath, buffer);
  console.log("ok");
});
