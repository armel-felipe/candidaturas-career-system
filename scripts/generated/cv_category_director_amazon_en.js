const fs = require("fs");
const path = require("path");
const { spawnSync } = require("child_process");
const {
  AlignmentType,
  BorderStyle,
  Document,
  ExternalHyperlink,
  LevelFormat,
  Packer,
  Paragraph,
  TabStopPosition,
  TabStopType,
  TextRun,
} = require("docx");

const pt = n => n * 2;

const workspace = process.env.CAREER_WORKSPACE || process.cwd();
const outputDir = path.join(workspace, "outputs");

function secao(text) {
  return new Paragraph({
    children: [new TextRun({ text, size: pt(12), font: "Arial" })],
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "000000", space: 1 } },
    spacing: { before: pt(6), after: pt(3) },
  });
}

function espaco(ptSize) {
  return new Paragraph({
    children: [new TextRun({ text: "", size: pt(ptSize || 6), font: "Arial" })],
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
  return new Paragraph({
    numbering: { reference: "bullets", level: 0 },
    children: runs.map(run => new TextRun({
      text: run.text,
      bold: run.bold || false,
      size: pt(9),
      font: "Arial",
    })),
    spacing: { after: pt(2) },
  });
}

function paragraph(text, options) {
  return new Paragraph({
    children: [new TextRun({ text, size: pt((options && options.size) || 9), bold: !!(options && options.bold), font: "Arial" })],
    spacing: { after: 0 },
  });
}

function hyperlink(text, url) {
  return new Paragraph({
    children: [
      new ExternalHyperlink({
        link: url,
        children: [new TextRun({ text, style: "Hyperlink", size: pt(9), font: "Arial" })],
      }),
    ],
    spacing: { after: 0 },
  });
}

async function main() {
  const outputName = process.argv[2] || "felipe_armel_cv_category_director_brazil_stores_amazon_en.docx";
  fs.mkdirSync(outputDir, { recursive: true });
  fs.mkdirSync(path.join(workspace, "outputs", "_tmp"), { recursive: true });

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
    numbering: {
      config: [{
        reference: "bullets",
        levels: [{
          level: 0,
          format: LevelFormat.BULLET,
          text: "\u2022",
          alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 360, hanging: 180 } } },
        }],
      }],
    },
    sections: [{
      properties: {
        page: {
          margin: { top: 720, right: 504, bottom: 720, left: 504 },
        },
      },
      children: [
        paragraph("Felipe Armel Dias da Silva", { size: 12, bold: true }),
        hyperlink("linkedin.com/in/felipearmel", "https://linkedin.com/in/felipearmel"),
        paragraph("São Paulo, SP"),
        hyperlink("(11) 98674-8218", "https://wa.me/5511986748218"),
        hyperlink("armelfelipe@gmail.com", "mailto:armelfelipe@gmail.com"),
        espaco(8),

        secao("Resumo"),
        paragraph("Senior executive with 15+ years scaling marketplace operations and managing P&L of R$300MM/year at iFood — expanding coverage from 400 to 800 cities, delivering R$70MM/year in savings, and reducing logistics cost by 3% YoY. Built S&OP from scratch at Trifil, managing 40K SKUs and cutting R$8MM in overhead. Chemical Engineer, MBA in Corporate Strategy. Business-level English. Seeking a Category Director role where strategic thinking, P&L discipline, and cross-functional leadership drive customer impact."),
        espaco(8),

        secao("Experiência"),

        // WeHandle
        cargoParagraph("Head of Operations", "wehandle (fintech SaaS)", "May 2024 – Feb 2026"),
        bullet([{ text: "Led B2B support operations and CX for a fintech SaaS, managing a team of 30 with direct P&L ownership and CEO-level reporting; integrated customer data pipelines via API across three platforms (Movidesk, CloudHumans, Zendesk), delivering operational metrics 3 months ahead of the data team." }]),
        bullet([{ text: "Drove cost-per-contact from R$4.14 to R$3.61 (–13%) through AI chatbot automation and WhatsApp channel migration; reduced digital-channel cost from R$1.04 to R$0.56 (–46%), directly improving gross margin by 15%." }]),
        bullet([{ text: "Built the CX function from scratch, establishing a product feedback loop that reduced backlog by 60%, lifted execution SLA from 67% to 85%, and lowered contact rate by 8% through root-cause analysis." }]),
        bullet([{ text: "Increased CSAT from 85% to 92%, maintained 95% ticket SLA, and cut average handling time from 20 to 8 minutes using Python, SQL, and Metabase for real-time dashboards." }]),
        espaco(6),

        // iFood Diretor
        cargoParagraph("Director of Operations", "iFood (largest LatAm food marketplace)", "Apr 2022 – Mar 2024"),
        bullet([{ text: "Owned logistics P&L with R$300MM/year budget, managing a cross-functional team of 240 across FieldOps, Payments, and New Business verticals; delivered weekly executive P&L reviews with scenario analysis to protect EBITDA targets." }]),
        bullet([{ text: "Led monthly executive S&OP connecting marketing, promotions, weather, fleet capacity, geographic expansion, and supply into a single Strategic Planning process — translating operational risks into short-term directional decisions for C-level." }]),
        bullet([{ text: "Scaled logistics coverage from 400 to 800 cities while maintaining SLA across 30M orders/month; reduced fleet unavailability from 5% to 0.5% in top 6 cities and increased bundled orders from 12% to 25%, reaching operational breakeven through Operational Efficiency programs." }]),
        bullet([{ text: "Reduced comparable logistics cost by 3% YoY (2023 vs 2022), neutralizing structural cost increase from 2021, using Python, SQL, and Databricks modeling; participated in strategic cycle planning setting company-wide targets with Data-Driven Decision Making across all operational levers." }]),
        bullet([{ text: "Conducted controlled pricing elasticity tests and yield management for driver compensation by zone, balancing on-demand supply with growth targets via dynamic incentives, gamification, and geo-targeted promotions." }]),
        espaco(6),

        // iFood Head
        cargoParagraph("Head of Operations", "iFood", "Nov 2018 – Mar 2022"),
        bullet([{ text: "Led liveOps, fleet pricing, data modeling, and capacity planning teams (28 direct reports), orchestrating operations across 800+ cities with direct interface to data engineering and product." }]),
        bullet([{ text: "Built a service-level simulator that maintained SLA while delivering R$70MM/year in savings — modeling elasticity between order frequency, promise time, and customer delay tolerance per region." }]),
        bullet([{ text: "Structured MPOS (payment device) commodatum distribution to 352 cities with fraud-risk eligibility criteria: zero financial loss across 200K monthly orders, proving MPOS as the primary growth lever in expansion markets." }]),
        bullet([{ text: "Implemented operations tower in the Mexico subsidiary, reducing cancellations by 60% through delivery-radius optimization; built real-time Grafana metrics for liveOps correlating fleet saturation with delivery-time targets." }]),
        bullet([{ text: "Designed the pricing architecture for driver compensation by zone and service model, running controlled elasticity experiments — the functional equivalent of category pricing applied to a logistics marketplace." }]),
        espaco(6),

        // VivaReal
        cargoParagraph("Commercial Planning & Operations Manager", "VivaReal (proptech marketplace)", "May 2015 – Dec 2017"),
        bullet([{ text: "Architected the Customer Success function from scratch — designed processes, onboarding journey, and client experience, hired the leadership team that scaled the area to 91 people; never the direct CS manager, always the architect." }]),
        bullet([{ text: "Managed commercial planning, SDR, and quality teams (33 people, 5 direct leads) with responsibility over product pricing, goal deployment, commission analysis, and CFO-level P&L discussions for board projections." }]),
        bullet([{ text: "Discovered the optimal lead-contact window (3 days) and built a process that lifted inbound SDR conversion from 18% to 50%, reducing cost of sales by 40% with automated SQL and Excel dashboards." }]),
        bullet([{ text: "Achieved monthly churn below 3%, NPS of 80%, and CSAT above 92%; created a delinquency recovery unit that recovered R$1M in launch campaigns; held weekly product roadmap meetings for Salesforce feature prioritization." }]),
        espaco(6),

        // Trifil — S&OP
        cargoParagraph("S&OP Coordinator", "Trifil / Scalina (textile manufacturing)", "Jan 2010 – Sep 2014"),
        bullet([{ text: "Created the S&OP function from scratch and sustained ritos for 4 years, managing 40K finished-goods SKUs across two brands (Trifil and Scala) through distributor, retail, key account, and franchise channels — with OTIF as the central metric connecting demand accuracy, production fill rate, and delivery performance directly to the CEO." }]),
        bullet([{ text: "Built an S&OP scenario simulator in Excel VBA for MRP validation and capacity trade-offs; led the GGF 2014 project that cut R$8MM in manufacturing overhead (energy, gas, maintenance, packaging) vs prior year through integrated planning and cost governance." }]),
        bullet([{ text: "Defined safety stock policies for high-turn SKUs balancing fill rate against inventory liquidity; coordinated S&OE execution evaluating stock-outs and surpluses, recalibrating commercial opportunities in weekly rhythm." }]),
        bullet([{ text: "Intermediated between commercial and manufacturing (PCP) on resource constraints, managing outsourcing (national and international) and corporate MRP generation; responsible for capacity analysis and collection production monitoring." }]),
        bullet([{ text: "Managed the dimensioning and economic feasibility project for acquiring 24 automated circular knitting machines, optimizing future capacity and reducing total manufacturing cost by 15%." }]),
        espaco(6),

        // Trifil — Commercial Intelligence
        cargoParagraph("Commercial Intelligence Coordinator", "Trifil / Scalina (textile manufacturing)", "Jan 2009 – Dec 2009"),
        bullet([{ text: "Created the Commercial Intelligence area from scratch with a team of 2 analysts, structuring market trend data, opportunity formatting, sales commission tracking, and decision-support metrics for the commercial board." }]),
        bullet([{ text: "Built a VBA allocation algorithm that maximized margin and revenue — scaling annual revenue from R$80MM to R$120MM; automated daily sales reports from 4 hours to 14 minutes with recurring routines." }]),
        bullet([{ text: "Supported commercial directors on pricing strategy, product mix optimization, and discount approval tables; normalized sales-team data with BI dashboards that eliminated reporting misalignments." }]),
        bullet([{ text: "Led the client recadastering project preparing the database for B2B system implementation; conducted analyses of discontinued inventory to unlock revenue from slow-moving stock." }]),
        espaco(8),

        secao("Formação"),
        bullet([{ text: "Specialization Certificate in Corporate Strategies — BSP Business School São Paulo (2016–2017)" }]),
        bullet([{ text: "Chemical Engineering — Faculdades Oswaldo Cruz (2014)" }]),
        bullet([{ text: "Six Sigma Green Belt — Setec Consulting (2020)" }]),
        bullet([{ text: "ILEad Leadership for Leaders of Leaders — Fundação Dom Cabral (2021)" }]),
        espaco(8),

        secao("Technical Skills"),
        paragraph("Excel/VBA · SQL · Python · PySpark · Databricks · Grafana · Tableau · Power BI · Metabase · Salesforce · Zendesk · ERP Infor LN · WMS"),
        espaco(8),

        secao("Idiomas"),
        bullet([{ text: "Portuguese — Native" }]),
        bullet([{ text: "English — Advanced" }]),
      ],
    }],
  });

  const buffer = await Packer.toBuffer(doc);
  const tmpPath = path.join(workspace, "outputs", "_tmp", outputName);
  fs.writeFileSync(tmpPath, buffer);

  const themeScript = path.join(workspace, "scripts", "docx", "inject_arial_theme.py");
  const finalPath = path.join(workspace, "outputs", outputName);
  const themeResult = spawnSync(process.env.PYTHON || "python", [themeScript, tmpPath, finalPath], { stdio: "inherit" });
  if (themeResult.status !== 0) {
    process.exit(themeResult.status || 1);
  }
  console.log("ok");
}

main().catch(error => {
  console.error(error);
  process.exit(1);
});
