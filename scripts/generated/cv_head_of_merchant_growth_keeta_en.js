const {
  Document, Packer, Paragraph, TextRun, ExternalHyperlink,
  TabStopType, TabStopPosition, AlignmentType,
  LevelFormat, BorderStyle
} = require("docx");
const fs = require("fs");

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
      new TextRun({ text: `${cargo} \u2014 ${empresa}`, bold: true, size: pt(9), font: "Arial" }),
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

// Cabeçalho
const headerParagraphs = [
  new Paragraph({
    children: [new TextRun({ text: "Felipe Armel Dias da Silva", bold: true, size: pt(12), font: "Arial" })],
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
    children: [new TextRun({ text: "S\u00e3o Paulo, SP", size: pt(9), font: "Arial" })],
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
];

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
      ...headerParagraphs,
      espaco(8),

      secao("Summary"),
      espaco(3),
      new Paragraph({
        children: [new TextRun({
          text: "Executive with 6+ years in food delivery platform operations and customer success at iFood, WeHandle, and VivaReal. Led operations of 240 people with R$300MM/year P&L, expanded coverage from 400 to 800 cities, and delivered R$70MM/year in cost savings through data-driven simulation. Built cross-functional growth strategies connecting marketing, operations, and product teams. Seeking a Head of Merchant Growth position to drive partner success through data, segmentation, and platform growth.",
          size: pt(9), font: "Arial"
        })],
        spacing: { after: 0 }
      }),
      espaco(8),

      secao("Experience"),
      espaco(3),

      // WeHandle — Head of Operations (mais recente)
      cargoParagraph("Head of Operations", "WeHandle", "May 2024 \u2013 Feb 2026"),
      espaco(3),
      bullet([
        { text: "Led the B2B customer operations team of 30 people, restructuring processes and defining portfolio segmentation strategy to drive client base growth and operational efficiency, impacting ", bold: false },
        { text: "15%", bold: true },
        { text: " of gross margin through operational improvements.", bold: false }
      ]),
      bullet([
        { text: "Developed client segmentation frameworks by performance and potential, integrated support data to the company's datalake via API, and implemented automation with chatbot and WhatsApp channels, using conversion analytics to identify optimization opportunities and improve merchant performance.", bold: false }
      ]),
      bullet([
        { text: "Increased ", bold: false },
        { text: "CSAT by 17%", bold: true },
        { text: " through portfolio segmentation, reduced cost per contact from R$4.14 to R$3.61, cut contact rate by ", bold: false },
        { text: "8%", bold: true },
        { text: ", and achieved 95% SLA across all tickets.", bold: false }
      ]),
      espaco(6),

      // iFood — Director of Operations
      cargoParagraph("Director of Operations", "iFood", "Apr 2022 \u2013 Mar 2024"),
      espaco(3),
      bullet([
        { text: "Managed operations of Latin America's largest food delivery platform leading ", bold: false },
        { text: "240 people", bold: true },
        { text: " with R$300MM/year P&L budget, expanded coverage from 400 to 800 cities, and led monthly executive S&OP with C-level enabling cross-functional collaboration across marketing, product, engineering, and operations.", bold: false }
      ]),
      bullet([
        { text: "Drove growth strategy through integrated S&OP linking promotions, fleet, and operations; data modeling with Python, SQL, and Databricks; and execution of cost-to-service trade-offs to protect EBITDA targets.", bold: false }
      ]),
      bullet([
        { text: "Expanded geographic coverage to ", bold: false },
        { text: "800 cities", bold: true },
        { text: ", reduced comparable logistics cost by 3% YoY, delivered R$70MM/year savings through a service-level simulator, and maintained SLA stability across ", bold: false },
        { text: "30M orders/month", bold: true },
        { text: ".", bold: false }
      ]),
      espaco(6),

      // iFood — Head of Operations
      cargoParagraph("Head of Operations", "iFood", "Nov 2018 \u2013 Mar 2022"),
      espaco(3),
      bullet([
        { text: "Built the liveOps and data modeling department from scratch with a team of 28, covering pricing, fleet planning, regional operations, and analytics for the food delivery marketplace.", bold: false }
      ]),
      bullet([
        { text: "Created real-time dashboards in Grafana, modeled data with SQL and Databricks, and developed a service-level simulator testing fleet, radius, and compensation scenarios for data-driven decision making.", bold: false }
      ]),
      bullet([
        { text: "Achieved R$70MM/year in savings with the simulator, expanded MPOS distribution availability from 70% to ", bold: false },
        { text: "97%", bold: true },
        { text: ", and reduced delivery lead time from 14 to 2 days.", bold: false }
      ]),
      espaco(6),

      // VivaReal
      cargoParagraph("Commercial Planning and Operations Manager", "VivaReal", "May 2015 \u2013 Dec 2017"),
      espaco(3),
      bullet([
        { text: "Led commercial planning, SDR, quality, and operations teams of 33 people with 5 direct reports; architected the Customer Success area that scaled to 91 people, designing onboarding processes and client journey segmentation.", bold: false }
      ]),
      bullet([
        { text: "Structured lead qualification and onboarding workflows using data, SQL, and dashboards; participated in strategic planning and the ZAP merger transition.", bold: false }
      ]),
      bullet([
        { text: "Increased inbound SDR conversion from ", bold: false },
        { text: "18% to 50%", bold: true },
        { text: ", reduced sales costs by 40%, and maintained churn below 3%/month with NPS of 80%.", bold: false }
      ]),
      espaco(8),

      secao("Education"),
      espaco(3),
      bullet([{ text: "Specialization Certificate in Corporate Strategies \u2014 BSP Business School S\u00e3o Paulo (2017)", bold: false }]),
      bullet([{ text: "Chemical Engineering \u2014 Faculdades Oswaldo Cruz (2014)", bold: false }]),
      bullet([{ text: "Six Sigma Green Belt \u2014 Setec Consulting (2020)", bold: false }]),
      bullet([{ text: "ILEad Leadership Program \u2014 Funda\u00e7\u00e3o Dom Cabral (2021)", bold: false }]),
      espaco(8),

      secao("Technical Stack"),
      espaco(3),
      new Paragraph({
        children: [new TextRun({ text: "SQL \u00b7 Python \u00b7 Databricks \u00b7 Grafana \u00b7 Excel/VBA \u00b7 Power BI \u00b7 Tableau \u00b7 Metabase \u00b7 Zendesk", size: pt(9), font: "Arial" })],
        spacing: { after: 0 }
      }),
      espaco(8),

      secao("Languages"),
      espaco(3),
      bullet([{ text: "Portuguese \u2014 Native", bold: false }]),
      bullet([{ text: "English \u2014 Advanced", bold: false }]),
    ]
  }]
});

Packer.toBuffer(doc).then(buffer => {
  const tmpPath = "outputs/_tmp/cv_head_of_merchant_growth_keeta_en.docx";
  fs.writeFileSync(tmpPath, buffer);
  console.log("ok");
});
