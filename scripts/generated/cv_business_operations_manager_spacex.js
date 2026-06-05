const { Document, Packer, Paragraph, TextRun, ExternalHyperlink, TabStopType, TabStopPosition, AlignmentType, LevelFormat, BorderStyle } = require("docx");
const fs = require("fs");

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

function headerLink(text, url) {
  return new ExternalHyperlink({
    children: [new TextRun({ text, style: "Hyperlink", size: pt(9), font: "Arial" })],
    link: url
  });
}

function headerText(text) {
  return new TextRun({ text, size: pt(9), font: "Arial" });
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
      // HEADER
      new Paragraph({
        children: [new TextRun({ text: "Felipe Armel Dias da Silva", bold: true, size: pt(12), font: "Arial" })],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [headerLink("linkedin.com/in/felipearmel", "https://linkedin.com/in/felipearmel")],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [headerText("S\u00e3o Paulo, SP")],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [headerLink("(11) 98674-8218", "https://wa.me/5511986748218")],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [headerLink("armelfelipe@gmail.com", "mailto:armelfelipe@gmail.com")],
        spacing: { after: 0 }
      }),
      espaco(6),

      // SUMMARY
      secao("Profile"),
      espaco(3),
      new Paragraph({
        children: [new TextRun({ text: "Executive with 17+ years in operations, business planning, and data-driven growth across marketplace logistics, SaaS, and supply chain. As Director of Operations at iFood, managed R$300M annual OPEX, steered executive S&OP, and expanded coverage from 400 to 800 cities. As Head of Operations at wehandle, redefined CX operations impacting gross margin by 15% in an early-stage environment. Combines strategic planning, pricing analytics, P&L discipline, and cross-functional execution. Seeking a Business Operations role to drive subscriber and revenue growth in an ambitious market-entry context.", size: pt(9), font: "Arial" })],
        spacing: { after: 0 }
      }),
      espaco(6),

      // EXPERIENCE
      secao("Experience"),
      espaco(3),

      // wehandle
      cargoParagraph("Head of Operations", "wehandle", "May 2024 \u2013 Feb 2026"),
      espaco(3),
      bullet([
        { text: "Led customer support and CX operations with a 30-person team, defining KPIs and managing P&L in an early-stage environment where I built processes from the ground up \u2014 choosing this role consciously for the autonomy and impact of a construction-stage company." }
      ]),
      bullet([
        { text: "Integrated three support platforms via API (Movidesk, CloudHumans, Zendesk) ahead of the data team, implemented AI-first automation and WhatsApp channel, and created a CX function connecting operational insights to product and data roadmaps." }
      ]),
      bullet([
        { text: "Reduced total cost per contact from R$4.14 to R$" }, { text: "3.61", bold: true }, { text: " (\u221213%), cut WhatsApp channel cost from R$1.04 to R$0.56 (\u221246%), and drove a " }, { text: "17% CSAT", bold: true }, { text: " improvement through strategic segmentation \u2014 directly impacting " }, { text: "15% of gross margin", bold: true }, { text: "." }
      ]),
      espaco(6),

      // iFood Director
      cargoParagraph("Director of Operations", "iFood", "Apr 2022 \u2013 Mar 2024"),
      espaco(3),
      bullet([
        { text: "Led logistics operations with a " }, { text: "240-person", bold: true }, { text: " organization spanning FieldOps, payment methods, and new business units, managing an annual OPEX budget of " }, { text: "R$300MM", bold: true }, { text: " through executive S&OP processes connecting growth, marketing, fleet, and financial planning." }
      ]),
      bullet([
        { text: "Drove " }, { text: "cross-functional decision-making", bold: true }, { text: " using Python, SQL, Databricks, and Tableau for capacity planning, " }, { text: "forecasting supply and demand", bold: true }, { text: ", pricing analysis, and trade-off modeling between cost and service level \u2014 presenting scenarios to C-level leadership in monthly planning cycles." }
      ]),
      bullet([
        { text: "Expanded coverage from " }, { text: "400 to 800 cities", bold: true }, { text: ", reduced comparable logistics cost by " }, { text: "3% YoY", bold: true }, { text: ", cut fleet unavailability from 5% to 0.5% in top-6 cities, and increased order batching from 12% to " }, { text: "25%", bold: true }, { text: ", reaching breakeven." }
      ]),
      espaco(6),

      // iFood Head
      cargoParagraph("Head of Operations", "iFood", "Nov 2018 \u2013 Mar 2022"),
      espaco(3),
      bullet([
        { text: "Built and led a 28-person operations team covering liveOps, regional operations, pricing, data modeling, and fleet planning \u2014 defining the architecture for Brazil\u2019s largest last-mile logistics marketplace." }
      ]),
      bullet([
        { text: "Created a proprietary simulation model for service-level optimization (saving " }, { text: "R$70M/year", bold: true }, { text: "), designed " }, { text: "pricing elasticity tests", bold: true }, { text: " to balance driver supply with demand by zone, and established the MPOS distribution program with eligibility rules that scaled to 352 cities with zero financial loss." }
      ]),
      bullet([
        { text: "Reduced MPOS distribution cost by " }, { text: "80%", bold: true }, { text: " and lead time from 14 to 2 days, raised availability from 70% to 97%, and cut Mexico cancellations by 60% through delivery radius adjustments." }
      ]),
      espaco(6),

      // VivaReal
      cargoParagraph("Commercial Planning and Operations Manager", "VivaReal", "May 2015 \u2013 Dec 2017"),
      espaco(3),
      bullet([
        { text: "Architected the Customer Success area from scratch \u2014 designing onboarding processes, customer journey, and hiring the leadership team \u2014 while leading commercial planning, SDR, and quality teams of 33 people with 5 direct reports." }
      ]),
      bullet([
        { text: "Analyzed lead response data to determine the optimal contact window (3 days), restructured the SDR funnel using SQL, Salesforce, and automated dashboards, and built financial scenarios with direct CFO interface for board-level revenue projections." }
      ]),
      bullet([
        { text: "Increased SDR inbound conversion from " }, { text: "18% to 50%", bold: true }, { text: ", reduced sales cost by " }, { text: "40%", bold: true }, { text: ", and scaled CS operations to " }, { text: "91 people", bold: true }, { text: " under independent management \u2014 achieving 92% CSAT, sub-3% monthly churn, and recovering R$1M from delinquent campaigns." }
      ]),
      espaco(6),

      // Trifil
      cargoParagraph("S&OP Coordinator", "Trifil (Scalina)", "Jan 2010 \u2013 Sep 2014"),
      espaco(3),
      bullet([
        { text: "Created the S&OP function from zero, running the full planning cycle for 4 years across " }, { text: "40K SKUs", bold: true }, { text: ", two brands, and all distribution channels \u2014 with direct interface between commercial and manufacturing." }
      ]),
      bullet([
        { text: "Built an MRP simulation tool in Excel/VBA for scenario validation, implemented strategic sourcing for 150K+ SKUs (cutting procurement costs by " }, { text: "27%", bold: true }, { text: " and stock-outs by 40%), and managed the executive S&OP rhythm connecting demand forecasting, capacity analysis, and financial trade-offs." }
      ]),
      bullet([
        { text: "Reduced General Manufacturing Expenses by " }, { text: "R$8M", bold: true }, { text: " from the P&L and increased company revenue from R$80M to " }, { text: "R$120M/year", bold: true }, { text: " through inventory allocation algorithms." }
      ]),
      espaco(8),

      // EDUCATION
      secao("Education"),
      espaco(3),
      new Paragraph({
        children: [new TextRun({ text: "Specialization Certificate in Corporate Strategies \u2014 BSP Business School S\u00e3o Paulo (2017)", size: pt(9), font: "Arial" })],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [new TextRun({ text: "Bachelor\u2019s Degree in Chemical Engineering \u2014 Faculdades Oswaldo Cruz (2014)", size: pt(9), font: "Arial" })],
        spacing: { after: 0 }
      }),
      espaco(8),

      // TECH STACK
      secao("Tech Stack"),
      espaco(3),
      new Paragraph({
        children: [new TextRun({ text: "Python \u00b7 SQL \u00b7 Databricks \u00b7 Tableau \u00b7 Power BI \u00b7 Grafana \u00b7 Excel/VBA \u00b7 Salesforce \u00b7 Zendesk \u00b7 ERP Infor LN", size: pt(9), font: "Arial" })],
        spacing: { after: 0 }
      }),
      espaco(8),

      // LANGUAGES
      secao("Languages"),
      espaco(3),
      bullet([
        { text: "Portuguese \u2014 Native" }
      ]),
      bullet([
        { text: "English \u2014 Advanced" }
      ]),
    ]
  }]
});

Packer.toBuffer(doc).then(buffer => {
  const outPath = "outputs/_tmp/cv_business_operations_manager_spacex_en.docx";
  fs.writeFileSync(outPath, buffer);
  console.log("ok");
});
