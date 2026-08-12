const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, ExternalHyperlink,
  TabStopType, TabStopPosition, LevelFormat, AlignmentType,
  BorderStyle, Numbering
} = require("docx");

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
      espaco(8),

      // Summary
      secao("Summary"),
      espaco(3),
      new Paragraph({
        children: [new TextRun({
          text: "Operations executive with 15+ years spanning marketplace logistics, customer experience, and product operations. At iFood, as Director of Operations, managed a R$300MM annual OPEX budget and expanded logistics coverage from 400 to 800 cities. As Head of Operations, generated R$70M/year in savings through a proprietary service level simulator. At WeHandle, led two platform migrations to an AI-first model, reducing cost per contact by 13%. At VivaReal, architected the CS area from scratch, scaling to 91 people. Specialization Certificate in Corporate Strategies — BSP Business School São Paulo. Seeking a Global Product Operations Manager position.",
          size: pt(9), font: "Arial"
        })],
        spacing: { after: 0 }
      }),
      espaco(8),

      // Experience
      secao("Experience"),
      espaco(3),

      // WeHandle
      cargoParagraph("Head of Operations", "WeHandle", "May 2024 – Feb 2026"),
      bullet([
        { text: "Led customer support operations and platform migration to an AI-first model, managing a team of 30 people across support, CX, and backoffice. Applied business process design to standardize workflows across two platform migrations." }
      ]),
      bullet([
        { text: "Led two platform migrations (Movidesk → CloudHumans → Zendesk), implemented WhatsApp channel replacing phone, and built real-time dashboards via API integration using Python and SQL. Drove system adoption through sales enablement and training development." }
      ]),
      bullet([
        { text: "Reduced cost per contact from R$", bold: false },
        { text: "4.14", bold: true },
        { text: " to R$", bold: false },
        { text: "3.61", bold: true },
        { text: " (−13%), improved CSAT from 85% to ", bold: false },
        { text: "92%", bold: true },
        { text: ", and reduced AHT from 20 to 8 minutes.", bold: false }
      ]),
      espaco(6),

      // iFood Director
      cargoParagraph("Director of Operations", "iFood", "Apr 2022 – Mar 2024"),
      bullet([
        { text: "Managed logistics operations with a team of ~240 people and an annual OPEX budget of R$", bold: false },
        { text: "300MM", bold: true },
        { text: ", covering FieldOps, Payments, and New Business. Led cross-functional collaboration across engineering, product, and marketing teams.", bold: false }
      ]),
      bullet([
        { text: "Led the monthly S&OP executive rhythm consolidating demand, supply, logistics cost, and scenarios for C-level; applied data analytics with Python, SQL, and Databricks." }
      ]),
      bullet([
        { text: "Expanded coverage from 400 to ", bold: false },
        { text: "800", bold: true },
        { text: " cities, reduced comparable logistics cost by 3% YoY, and increased batched orders from 12% to ", bold: false },
        { text: "25%", bold: true },
        { text: ".", bold: false }
      ]),
      espaco(6),

      // iFood Head
      cargoParagraph("Head of Operations", "iFood", "Nov 2018 – Mar 2022"),
      bullet([
        { text: "Led a 28-person team across liveOps, pricing, fleet planning, and data modeling for the logistics marketplace." }
      ]),
      bullet([
        { text: "Built a real-time service level simulator in Python/SQL, defined MPOS eligibility criteria covering fraud and qualification risk, and created Grafana dashboards for live operations." }
      ]),
      bullet([
        { text: "Generated R$", bold: false },
        { text: "70M", bold: true },
        { text: "/year in savings through the simulator, reduced MPOS delivery lead time from 14 to 2 days (−85%), and cut Mexico cancellations by ", bold: false },
        { text: "60%", bold: true },
        { text: " through delivery radius optimization.", bold: false }
      ]),
      espaco(6),

      // VivaReal
      cargoParagraph("Commercial Planning and Operations Manager", "VivaReal", "May 2015 – Dec 2017"),
      bullet([
        { text: "Led commercial planning, SDR operations, and customer success architecture for Brazil's leading real estate marketplace." }
      ]),
      bullet([
        { text: "Architected the CS area from scratch — designed processes, defined onboarding journey, and hired leadership — scaling to ", bold: false },
        { text: "91", bold: true },
        { text: " people.", bold: false }
      ]),
      bullet([
        { text: "Increased SDR inbound conversion from 18% to ", bold: false },
        { text: "50%", bold: true },
        { text: ", reduced sales cost by 40%, and achieved NPS of ", bold: false },
        { text: "80%", bold: true },
        { text: " with CSAT above 92%.", bold: false }
      ]),
      espaco(6),

      // Trifil
      cargoParagraph("S&OP Coordinator", "Trifil (Scalina)", "Jan 2010 – Sep 2014"),
      bullet([
        { text: "Created the S&OP area from scratch and managed 40K SKUs across two brands and all distribution channels." }
      ]),
      bullet([
        { text: "Implemented Strategic Sourcing across 150K+ SKUs and led the GGF cost reduction project with PDCA methodology." }
      ]),
      bullet([
        { text: "Reduced GGF by R$", bold: false },
        { text: "8M", bold: true },
        { text: " from the P&L, cut purchasing costs by 27%, and improved inventory turnover from 8 to 6 months.", bold: false }
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
        children: [new TextRun({ text: "Leadership for Leaders of Leaders — Fundação Dom Cabral (2021)", size: pt(9), font: "Arial" })],
        spacing: { after: 0 }
      }),
      espaco(8),

      // Technical Stack
      secao("Technical Stack"),
      espaco(3),
      new Paragraph({
        children: [new TextRun({ text: "SQL · Python · Databricks · Tableau · Power BI · Grafana · Metabase · Zendesk · Salesforce · ERP Infor LN", size: pt(9), font: "Arial" })],
        spacing: { after: 0 }
      }),
      espaco(8),

      // Languages
      secao("Languages"),
      espaco(3),
      bullet([{ text: "Portuguese — Native" }]),
      bullet([{ text: "English — Advanced" }])
    ]
  }]
});

Packer.toBuffer(doc).then(buffer => {
  const workspace = path.resolve(__dirname, "..", "..");
  const outPath = path.join(workspace, "outputs", "_tmp", "cv_global_product_operations_manager_bytedance_brazil_en.docx");
  fs.writeFileSync(outPath, buffer);
  console.log("ok");
});
