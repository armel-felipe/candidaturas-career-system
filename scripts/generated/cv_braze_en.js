const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, ExternalHyperlink,
  TabStopType, TabStopPosition, LevelFormat, AlignmentType,
  BorderStyle, Header, Footer, PageReference, NumberFormat
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
      // Header
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

      // Summary
      secao("Summary"),
      espaco(3),
      new Paragraph({
        children: [
          new TextRun({
            text: "Engineer with an MBA Corporate Strategy from BSP. At iFood, as Director of Operations, I managed a P&L of ",
            size: pt(9), font: "Arial"
          }),
          new TextRun({ text: "R$300M/year", bold: true, size: pt(9), font: "Arial" }),
          new TextRun({ text: " and a team of ", size: pt(9), font: "Arial" }),
          new TextRun({ text: "240", bold: true, size: pt(9), font: "Arial" }),
          new TextRun({ text: ". As Head of Operations, I built the simulator that saved ", size: pt(9), font: "Arial" }),
          new TextRun({ text: "R$70M/year", bold: true, size: pt(9), font: "Arial" }),
          new TextRun({ text: ". At WeHandle, I built CX from scratch with AI and omnichannel — cutting cost per contact by ", size: pt(9), font: "Arial" }),
          new TextRun({ text: "13%", bold: true, size: pt(9), font: "Arial" }),
          new TextRun({ text: ". My career bridges operations and technology, consistently building scalable systems from the ground up. I seek a position as Director of Business Operations.", size: pt(9), font: "Arial" })
        ],
        spacing: { after: 0 }
      }),
      espaco(8),

      // Experience
      secao("Experience"),
      espaco(3),

      // WeHandle
      cargoParagraph("Head of Operations", "WeHandle", "May 2024 – Feb 2026"),
      bullet([
        { text: "Built the Customer Success and CX operation from scratch — zero structure going in — leading a team of " },
        { text: "30", bold: true },
        { text: " and transitioning from reactive phone-based service to an AI-first, tech-enabled model aligned with GTM Strategy for omnichannel automation." }
      ]),
      bullet([
        { text: "Led two full platform migrations, integrated data via APIs to bypass data team bottlenecks, and deployed chatbot + AI-humanized service targeting 25% productivity gains across all channels." }
      ]),
      bullet([
        { text: "Reduced total cost per contact from R$4.14 to " },
        { text: "R$3.61 (−13%)", bold: true },
        { text: ", cut average handling time from 20 to 8 minutes, raised CSAT from 85% to 92%, and achieved 95% SLA." }
      ]),
      espaco(6),

      // iFood Diretor
      cargoParagraph("Director of Operations", "iFood", "Apr 2022 – Mar 2024"),
      bullet([
        { text: "Directed logistics operations with a P&L of " },
        { text: "R$300M/year", bold: true },
        { text: " and a team of ~" }, { text: "240", bold: true }, { text: " across FieldOps, Payments, and New Business — leading monthly S&OP executive rhythm for Cross-functional Alignment with C-level governance to drive Operational Efficiency across the entire commercial lifecycle." }
      ]),
      bullet([
        { text: "Drove operational strategy through capacity planning per city, data modeling (Python, SQL, Databricks), fleet optimization, simulation-based Playbook Development, and decision-making for cost vs. service-level trade-offs." }
      ]),
      bullet([
        { text: "Expanded coverage from " },
        { text: "400 to 800 cities", bold: true },
        { text: ", reduced comparable logistics cost by 3% YoY (operational efficiency at scale), achieved 25% bundled deliveries (from 12%), and cut fleet downtime from 5% to 0.5% in top 6 cities." }
      ]),
      espaco(6),

      // iFood Head
      cargoParagraph("Head of Operations", "iFood", "Nov 2018 – Mar 2022"),
      bullet([
        { text: "Headed liveOps, fleet planning, pricing, and data modeling — a team of 28 — building the operational intelligence that powered logistics for " },
        { text: "30M monthly orders", bold: true },
        { text: " across Brazil and Mexico." }
      ]),
      bullet([
        { text: "Created real-time monitoring dashboards in Grafana, built a proprietary service-level simulator, and established fleet capacity planning with city-level balancing." }
      ]),
      bullet([
        { text: "Generated " },
        { text: "R$70M/year", bold: true },
        { text: " in savings through the simulator, reduced MPOS distribution cost by 80% and lead time from 14 to 2 days, and cut Mexico cancellations by 60%." }
      ]),
      espaco(6),

      // Renault
      cargoParagraph("Customer Success Manager", "Renault", "Jan 2018 – Oct 2018"),
      bullet([
        { text: "Managed end-to-end customer success, transitioning from a BPO model to an in-house structure — 8 people replacing 40 outsourced staff — presenting ROI analysis that secured VP approval in two meetings." }
      ]),
      bullet([
        { text: "Redesigned the digital lead contact flow, programmed autodialers for performance, and implemented real-time SLA governance using Excel, VBA, and Power BI for data intelligence." }
      ]),
      bullet([
        { text: "Raised lead-to-sale conversion from " },
        { text: "24% to 46%", bold: true },
        { text: ", stabilized commercial execution with real-time SLA tracking, and built a scalable in-house model with higher quality control." }
      ]),
      espaco(6),

      // VivaReal
      cargoParagraph("Commercial Planning and Operations Manager", "VivaReal", "May 2015 – Dec 2017"),
      bullet([
        { text: "Oversaw commercial planning, SDR pipeline, and operations for a SaaS proptech — managing 33 people across Quality, SDR, and listings — and acted as " },
        { text: "architect of the CS area", bold: true },
        { text: ", which scaled to 91 people." }
      ]),
      bullet([
        { text: "Structured the SDR lead distribution process with data-driven engagement timing (optimal contact at 3 days), used SQL and automated dashboards for daily intelligence, and led Playbook Development for pricing and go-to-market playbooks aligning cross-functional workstreams across the full commercial lifecycle." }
      ]),
      bullet([
        { text: "Increased inbound SDR conversion from " },
        { text: "18% to 50%", bold: true },
        { text: " (−40% sales cost), drove CSAT above 92% and NPS to 80%, reduced churn below 3%/month, and recovered R$1M in revenue campaigns." }
      ]),
      espaco(6),

      // Trifil
      cargoParagraph("Analyst / Coordinator (multiple roles)", "Trifil (Scalina)", "Jan 2006 – Sep 2014"),
      bullet([
        { text: "Held progressive roles across Shipping, Materials, Commercial Intelligence, and S&OP — creating the S&OP area from scratch and sustaining the governance rhythm for 4 years across " },
        { text: "40K SKUs", bold: true },
        { text: " and two brands." }
      ]),
      bullet([
        { text: "Implemented Strategic Sourcing across 150K+ SKUs, developed inventory allocation algorithms (VBA), and built simulation models for MRP and S&OP — using ERP LN, WMS, and KPIs." }
      ]),
      bullet([
        { text: "Reduced purchasing cost by 27%, cut stock-outs by 40%, improved inventory turnover from 8 to 6 months, decreased GGF by " },
        { text: "R$8M", bold: true },
        { text: ", and grew revenue from R$80M to R$120M/year through allocation optimization." }
      ]),
      espaco(8),

      // Education
      secao("Education"),
      espaco(3),
      new Paragraph({
        children: [new TextRun({ text: "Specialization Certificate in Corporate Strategies — BSP Business School São Paulo (2016–2017)", size: pt(9), font: "Arial" })],
        spacing: { after: pt(2) }
      }),
      new Paragraph({
        children: [new TextRun({ text: "Engineering degree in Chemical Engineering — Faculdades Oswaldo Cruz (2014)", size: pt(9), font: "Arial" })],
        spacing: { after: pt(2) }
      }),
      new Paragraph({
        children: [new TextRun({ text: "Six Sigma Green Belt — Setec Consulting (2020)", size: pt(9), font: "Arial" })],
        spacing: { after: 0 }
      }),
      espaco(8),

      // Technical Stack
      secao("Technical Stack"),
      espaco(3),
      new Paragraph({
        children: [new TextRun({ text: "Python · SQL · Databricks · Grafana · Zendesk · Salesforce · Power BI · Tableau · ERP Infor LN · WMS", size: pt(9), font: "Arial" })],
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

const outputPath = "outputs/_tmp/cv_braze_en.docx";
Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync(outputPath, buffer);
  console.log("ok");
});
