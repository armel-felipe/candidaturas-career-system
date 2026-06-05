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

const pt = n => n * 2; // half-points. Never use n * 20 here.

const workspace = process.env.CAREER_WORKSPACE || process.cwd();
const outputDir = process.env.CAREER_OUTPUTS || path.join(workspace, "outputs");

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

function paragraph(text, options = {}) {
  return new Paragraph({
    children: [new TextRun({ text, size: pt(options.size || 9), bold: !!options.bold, font: "Arial" })],
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
  const outputName = process.argv[2] || "felipe_armel_cv_associate_director_delivery_operations_monks_en.docx";
  fs.mkdirSync(outputDir, { recursive: true });

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

        // --- SUMMARY ---
        secao("Summary"),
        paragraph("Executive with 20 years in digital operations and business transformation across marketplace and technology. As Director at iFood, owned the delivery P&L (R$300MM), expanding logistics from 400 to 800 cities while improving margins. At WeHandle, led AI-first reengineering of customer ops, reducing costs 13% and improving gross margin 15%. Brings Data-driven Decision Making and hands-on execution to turn complexity into profitable, scalable delivery."),
        espaco(8),

        // --- EXPERIENCE ---
        secao("Experience"),

        // WeHandle
        cargoParagraph("Head of Operations", "wehandle", "May 2024 – Feb 2026"),
        bullet([{ text: "Led full reengineering of customer operations (30 people), owning cost P&L with direct impact on gross margin, AI automation strategy, and multi-platform integration across Movidesk, CloudHumans, and Zendesk." }]),
        bullet([{ text: "Implemented AI-first platform migrations and WhatsApp channel substitution, building proprietary API connections to the company datalake — delivering real-time metrics 3 months ahead of the data team." }]),
        bullet([{ text: "Reduced cost per interaction ", bold: false }, { text: "13% (R$4.14 → R$3.61)", bold: true }, { text: ", improved gross margin ", bold: false }, { text: "15%", bold: true }, { text: ", raised CSAT 85% → 92% at 95% SLA, and cut average handling time from 20 to 8 minutes." }]),
        espaco(6),

        // iFood Director
        cargoParagraph("Director of Operations", "iFood", "Apr 2022 – Mar 2024"),
        bullet([{ text: "Owned delivery cost P&L (R$300MM annual budget) with full Margin Ownership, leading ", bold: false }, { text: "240", bold: true }, { text: " people across Field Operations, Payments, and New Business — accountable for EBITDA targets through weekly DRE analysis and corrective actions." }]),
        bullet([{ text: "Led monthly executive S&OP bridging operations, finance, and C-level strategy in a Cross-functional Leadership capacity — modeled trade-offs between cost and service level using Python, SQL, and Databricks to protect EBITDA." }]),
        bullet([{ text: "Drove Resource Allocation across 800 cities balancing online and cloud fleet, reduced comparable cost ", bold: false }, { text: "3% YoY", bold: true }, { text: ", scaled to ", bold: false }, { text: "30M monthly orders", bold: true }, { text: " with stable SLA and fleet availability improvement from 5% → 1% downtime." }]),
        espaco(6),

        // iFood Head
        cargoParagraph("Head of Operations", "iFood", "Nov 2018 – Mar 2022"),
        bullet([{ text: "Led a 28-person team across liveOps, regional operations, pricing, data modeling, and fleet Capacity Planning — responsible for real-time operational metrics and delivery-time indicators via Grafana." }]),
        bullet([{ text: "Built a capacity simulator generating ", bold: false }, { text: "R$70M/year savings", bold: true }, { text: " in fleet planning, balancing online and cloud fleet models across geographies with strong Unit Economics analysis." }]),
        bullet([{ text: "Defined fleet pricing architecture and conducted controlled elasticity tests; expanded MPOS distribution to 352 cities with zero financial loss, reducing delivery time from 14 to 2 days." }]),
        espaco(6),

        // Renault
        cargoParagraph("Customer Success Manager", "Renault do Brasil", "Jan 2018 – Oct 2018"),
        bullet([{ text: "Approved business case in two meetings by correctly calculating ROI for transitioning outsourced operations to in-house — demonstrating net savings with higher-value headcount." }]),
        bullet([{ text: "Migrated two BPO operations (40 agents) to an 8-person in-house team, raising lead-to-sale conversion from ", bold: false }, { text: "24% → 46%", bold: true }, { text: " within two days by implementing real-time data tracking and intelligent dialing." }]),
        bullet([{ text: "Redesigned digital contact flow with SLA governance, data-driven lead qualification, and pipeline control — creating a scalable model with measurable quality and response-time standards." }]),
        espaco(6),

        // VivaReal
        cargoParagraph("Commercial Planning and Operations Manager", "VivaReal", "May 2015 – Dec 2017"),
        bullet([{ text: "Architected the Customer Success function from scratch — designed all processes, onboarding protocols, and hired leadership. The area scaled to ", bold: false }, { text: "91 people", bold: true }, { text: " under subsequent management (never managed CS directly)." }]),
        bullet([{ text: "Led SDR operations discovering the optimal lead-contact window (3 days), raising inbound conversion ", bold: false }, { text: "18% → 50%", bold: true }, { text: " and reducing CAC 40% through data-driven pipeline management." }]),
        bullet([{ text: "Managed planning for 33 people across quality, SDR, and listings operations; kept churn below ", bold: false }, { text: "3% monthly", bold: true }, { text: ", achieved CSAT 92% and NPS 80%, with direct CFO interface for budget and revenue scenarios." }]),
        espaco(6),

        // Trifil
        cargoParagraph("S&OP Coordinator", "Trifil / Scalina", "Jan 2006 – Sep 2014"),
        bullet([{ text: "Created the S&OP function from scratch with full Operational Governance and Process Standardization, sustaining executive rhythms for 4 years across 2 brands (Trifil, Scala) and all distribution channels — integrating demand, supply, service level, and cost into a single framework." }]),
        bullet([{ text: "Led Cost Optimization through the GGF project reducing factory overhead by ", bold: false }, { text: "R$8M", bold: true }, { text: " annually and managed Strategic Sourcing for ", bold: false }, { text: "150K SKUs", bold: true }, { text: " with procurement cost reduction of 27%." }]),
        bullet([{ text: "Led Team Leadership for cross-functional teams across planning, procurement, and commercial intelligence; improved inventory turns by 2 months (8→6), reduced production costs ", bold: false }, { text: "15%", bold: true }, { text: " via automated dyeing system with 1.5-year payback (projected: 3 years)." }]),
        espaco(8),

        // --- EDUCATION ---
        secao("Education"),
        bullet([{ text: "Specialization Certificate in Corporate Strategies — BSP Business School São Paulo (2017)" }]),
        bullet([{ text: "Chemical Engineering — Faculdades Oswaldo Cruz (2014)" }]),
        bullet([{ text: "Six Sigma Green Belt — Setec Consulting (2020)" }]),
        bullet([{ text: "ILEad Leadership for Leaders of Leaders — Fundação Dom Cabral (2021)" }]),
        espaco(8),

        // --- TECHNICAL STACK ---
        secao("Technical Skills"),
        paragraph("Python · SQL · Databricks · Grafana · Tableau · Excel / VBA"),
        paragraph("Salesforce · Zendesk · Movidesk · CloudHumans · APIs / Integrations"),
        espaco(8),

        // --- LANGUAGES ---
        secao("Languages"),
        bullet([{ text: "Portuguese — Native" }]),
        bullet([{ text: "English — Advanced" }]),
      ],
    }],
  });

  const buffer = await Packer.toBuffer(doc);
  const outputPath = path.join(outputDir, outputName);
  fs.writeFileSync(outputPath, buffer);
  const themeScript = path.join(workspace, "scripts", "docx", "inject_arial_theme.py");
  const themeResult = spawnSync(process.env.PYTHON || "python", [themeScript, outputPath], { stdio: "inherit" });
  if (themeResult.status !== 0) {
    process.exit(themeResult.status || 1);
  }
  console.log(outputPath);
}

main().catch(error => {
  console.error(error);
  process.exit(1);
});
