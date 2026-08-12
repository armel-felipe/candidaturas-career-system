const fs = require("fs");
const { Document, Packer, Paragraph, TextRun, BorderStyle, TabStopType, TabStopPosition, AlignmentType, LevelFormat, ExternalHyperlink } = require("docx");

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

function linkHyperlink(text, url) {
  return new ExternalHyperlink({
    children: [new TextRun({ text, size: pt(9), font: "Arial", style: "Hyperlink" })],
    link: url
  });
}

const doc = new Document({
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
  sections: [{
    properties: {
      page: {
        margin: { top: 720, right: 504, bottom: 720, left: 504 }
      }
    },
    children: [
      new Paragraph({
        children: [new TextRun({ text: "Felipe Armel Dias da Silva", bold: true, size: pt(12), font: "Arial" })],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [linkHyperlink("linkedin.com/in/felipearmel", "https://linkedin.com/in/felipearmel")],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [new TextRun({ text: "Sao Paulo, SP", size: pt(9), font: "Arial" })],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [linkHyperlink("(11) 98674-8218", "https://wa.me/5511986748218")],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [linkHyperlink("armelfelipe@gmail.com", "mailto:armelfelipe@gmail.com")],
        spacing: { after: 0 }
      }),

      espaco(8),
      secao("Summary"),

      new Paragraph({
        children: [
          new TextRun({ text: "Senior Product Operations executive with 20+ years building scalable operations from scratch. At iFood as Director of Operations, managed ", size: pt(9), font: "Arial" }),
          new TextRun({ text: "R$300MM", bold: true, size: pt(9), font: "Arial" }),
          new TextRun({ text: " annual budget and 240 people, achieving ", size: pt(9), font: "Arial" }),
          new TextRun({ text: "R$70MM/year", bold: true, size: pt(9), font: "Arial" }),
          new TextRun({ text: " saving with service-level simulator. At WeHandle, restructured Multi-channel Platforms support infrastructure reducing cost per ticket 13% and impacting 15% on gross margin. Seeking a Product Operations role to drive agency governance, budget allocation and collections infrastructure.", size: pt(9), font: "Arial" })
        ],
        spacing: { after: 0 }
      }),

      espaco(8),
      secao("Experience"),

      espaco(3),
      cargoParagraph("Head of Operations", "wehandle", "May 2024 – Feb 2026"),
      bullet([
        { text: "Led Product Operations and multi-channel Collections Infrastructure for a 30-person team, overseeing Zendesk, CloudHumans and Movidesk platforms with SLA at 95% and direct budget accountability." }
      ]),
      bullet([
        { text: "Led 2 platform migrations and integrated 3 platforms via API for real-time data flows, using SQL, Python and Metabase for Data-Driven Decision Making across WhatsApp, chatbot and AI channels." }
      ]),
      bullet([
        { text: "Reduced cost per ticket from R$4.14 to ", bold: false },
        { text: "R$3.61 (\u221213%)", bold: true },
        { text: ", improved CSAT from 85% to 92%, and impacted 15% on gross margin through Process Optimization and channel reallocation." }
      ]),

      espaco(6),
      cargoParagraph("Director of Operations", "iFood", "Apr 2022 – Mar 2024"),
      bullet([
        { text: "Directed Budget Management of ", bold: false },
        { text: "R$300MM/year", bold: true },
        { text: " for delivery costs, Agency Governance over logistics partners, and People Management of ~240 people across FieldOps, Payments and New Business, with direct P&L accountability." }
      ]),
      bullet([
        { text: "Conducted monthly executive S&OP consolidating demand, supply and cost across Brazil, using Python, SQL and Databricks for scenario modeling and Cross-functional Leadership with C-level." }
      ]),
      bullet([
        { text: "Reduced comparable cost by 3% YoY, expanded coverage from 400 to ", bold: false },
        { text: "800 cities", bold: true },
        { text: ", and increased grouped deliveries from 12% to 25%, reaching breakeven on R$300MM annual operations." }
      ]),

      espaco(6),
      cargoParagraph("Head of Operations", "iFood", "Nov 2018 – Mar 2022"),
      bullet([
        { text: "Built liveOps, fleet planning and pricing from scratch for a 28-person team, with Stakeholder Management across engineering, product and marketing in a high-ambiguity environment." }
      ]),
      bullet([
        { text: "Built the fleet capacity simulator using SQL, Python and Grafana, and defined Agency Governance rules for MPOS distribution covering fraud risk and partner qualification across 352 cities." }
      ]),
      bullet([
        { text: "Generated ", bold: false },
        { text: "R$70MM/year", bold: true },
        { text: " saving with the service-level simulator, reduced fleet unavailability from 5.4% to 0.5% in top-6 cities, and cut MPOS distribution cost by 80% (14\u21922 days lead time)." }
      ]),

      espaco(6),
      cargoParagraph("Manager of Commercial Planning and Operations", "VivaReal", "May 2015 – Dec 2017"),
      bullet([
        { text: "Led commercial operations, SDR pipeline and CS architecture for 33 direct reports, including Collections Recovery campaigns that generated R$1M in recovered revenue, and Stakeholder Management with C-level." }
      ]),
      bullet([
        { text: "Restructured the SDR pipeline with Salesforce and automated dashboards, and architected the CS area from scratch \u2014 defining onboarding journeys and hiring leadership for a team that scaled to 91 people." }
      ]),
      bullet([
        { text: "Increased SDR inbound conversion from 18% to ", bold: false },
        { text: "50%", bold: true },
        { text: " (\u221240% cost of sales), achieved NPS of 80% and drove churn below 3%/month in the used-properties BU." }
      ]),

      espaco(6),
      cargoParagraph("S&OP Coordinator", "Scalina (Trifil)", "Jan 2010 – Sep 2014"),
      bullet([
        { text: "Created the S&OP area from scratch (4 years), managing 40K SKUs across 2 brands and all distribution channels, with executive S&OP rituals and Portfolio Allocation across the production plan." }
      ]),
      bullet([
        { text: "Built the S&OP/MRP simulator in Excel VBA and managed the corporate MRP, outsourcing planning and safety stock policy with trade-offs between delivery and financial liquidity." }
      ]),
      bullet([
        { text: "Reduced manufacturing overhead by ", bold: false },
        { text: "R$8MM", bold: true },
        { text: " on the P&L (GGF project), delivered R$4.6MM above budget target through August, and maintained OTIF and fill rate as central KPIs reported to the CEO." }
      ]),

      espaco(8),
      secao("Education"),
      espaco(3),
      bullet([{ text: "Specialization Certificate in Corporate Strategies \u2014 BSP Business School Sao Paulo (2016\u20132017)" }]),
      bullet([{ text: "Six Sigma Green Belt \u2014 Setec Consulting (2020)" }]),
      bullet([{ text: "ILead \u2014 Leadership for Leaders of Leaders \u2014 Fundacao Dom Cabral (2021)" }]),
      bullet([{ text: "Chemical Engineering \u2014 Faculdades Oswaldo Cruz (2014)" }]),
      bullet([{ text: "Technical Degree in Chemistry \u2014 SENAI Mario Amato (1997)" }]),

      espaco(8),
      secao("Technical Skills"),
      espaco(3),
      new Paragraph({
        children: [new TextRun({ text: "SQL \u00b7 Python \u00b7 PySpark \u00b7 Databricks \u00b7 Grafana \u00b7 Power BI \u00b7 Tableau \u00b7 Metabase \u00b7 Excel/VBA \u00b7 Salesforce \u00b7 Zendesk", size: pt(9), font: "Arial" })],
        spacing: { after: 0 }
      }),

      espaco(8),
      secao("Languages"),
      espaco(3),
      bullet([{ text: "Portuguese \u2014 Native" }]),
      bullet([{ text: "English \u2014 Advanced" }])
    ]
  }]
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync("outputs/_tmp/cv_product_operations_manager_iii_nubank_en.docx", buffer);
  console.log("ok");
});