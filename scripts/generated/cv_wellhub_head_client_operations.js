// CV — Felipe Armel Dias da Silva
// Vaga: Head of Client Operations — Wellhub
// Persona B: SaaS/CX — wehandle → iFood Diretor → VivaReal
// Datas validadas em autoconhecimento.md:
//   wehandle   Head de Operações                           mai/2024 – fev/2026
//   iFood      Diretor de Operações                        abr/2022 – mar/2024
//   VivaReal   Gerente de Planejamento Comercial e Ops     mai/2015 – dez/2017

const fs = require("fs");
const path = require("path");
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

const pt = n => n * 2; // half-points. NUNCA n * 20.

const workspace = process.env.CAREER_WORKSPACE || process.cwd();
const outputDir = process.env.CAREER_OUTPUTS || path.join(workspace, "outputs");
const OUTPUT_NAME = "felipe_armel_cv_head_client_operations_wellhub.docx";

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
    children: runs.map(r => new TextRun({
      text: r.text,
      bold: r.bold || false,
      size: pt(9),
      font: "Arial",
    })),
    spacing: { after: pt(2) },
  });
}

function paragrafo(text, options = {}) {
  return new Paragraph({
    children: [new TextRun({
      text,
      size: pt(options.size || 9),
      bold: !!options.bold,
      font: "Arial",
    })],
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
          text: "•",
          alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 360, hanging: 180 } } },
        }],
      }],
    },
    sections: [{
      properties: {
        page: {
          size: { width: 11906, height: 16838 }, // A4
          margin: { top: 720, right: 504, bottom: 720, left: 504 },
        },
      },
      children: [

        // ─── CABEÇALHO ───────────────────────────────────────────────────────
        paragrafo("Felipe Armel Dias da Silva", { size: 12, bold: true }),
        hyperlink("linkedin.com/in/felipearmel", "https://linkedin.com/in/felipearmel"),
        paragrafo("São Paulo, SP"),
        hyperlink("(11) 98674-8218", "https://wa.me/5511986748218"),
        hyperlink("armelfelipe@gmail.com", "mailto:armelfelipe@gmail.com"),

        espaco(8),

        // ─── RESUMO ──────────────────────────────────────────────────────────
        secao("Resumo"),
        espaco(3),
        paragrafo(
          "Executivo Sênior com trajetória em operações de cliente, CX e planejamento em empresas de tecnologia. " +
          "No iFood, como Diretor de Operações, gerenciei budget de R$ 300MM/ano e conduzi S&OP executivo com C-level. " +
          "Na wehandle, como Head de Operações, reduzi custo por atendimento em 13% e impactei margem bruta em 15%. " +
          "Busco posição de Head of Client Operations."
        ),

        espaco(8),

        // ─── EXPERIÊNCIA ─────────────────────────────────────────────────────
        secao("Experiência"),

        // wehandle ────────────────────────────────────────────────────────────
        espaco(3),
        cargoParagraph("Head de Operações", "wehandle", "Mai 2024 – Fev 2026"),

        bullet([
          { text: "Fui responsável pela " },
          { text: "Client Operations Management", bold: true },
          { text: " da wehandle — startup de SaaS B2B —, liderando time de 30 pessoas em " },
          { text: "B2B Support Operations", bold: true },
          { text: " e Customer Experience (CX), garantindo excelência na jornada do cliente com gestão direta de performance operacional." },
        ]),
        bullet([
          { text: "Utilizando " },
          { text: "Performance Monitoring", bold: true },
          { text: " em tempo real (Zendesk, Metabase, API própria), " },
          { text: "Root Cause Analysis", bold: true },
          { text: " para priorização de backlog de produto via ClickUp e automação com IA (chatbot + WhatsApp)." },
        ]),
        bullet([
          { text: "Consegui elevar CSAT de 85% para " },
          { text: "92%", bold: true },
          { text: ", SLA em 95% dos tickets, reduzir TME de 20 para 8 minutos e custo por atendimento de R$ 4,14 para " },
          { text: "R$ 3,61 (−13%)", bold: true },
          { text: ", impactando a margem bruta em 15%." },
        ]),

        espaco(6),

        // iFood Diretor ───────────────────────────────────────────────────────
        cargoParagraph("Diretor de Operações", "iFood", "Abr 2022 – Mar 2024"),

        bullet([
          { text: "Fui responsável pelas operações logísticas e " },
          { text: "Operational Excellence", bold: true },
          { text: " do iFood no Brasil, liderando ~240 pessoas (diretos e indiretos) e conduzindo S&OP executivo mensal com C-level, com budget de " },
          { text: "R$ 300MM/ano", bold: true },
          { text: "." },
        ]),
        bullet([
          { text: "Utilizando " },
          { text: "Stakeholder Management", bold: true },
          { text: " e " },
          { text: "Cross-functional Collaboration", bold: true },
          { text: " com produto, marketing e finanças — sem linha de reporte direta —, além de SQL, Databricks e Python para modelagem de dados e leitura recorrente de DRE executiva." },
        ]),
        bullet([
          { text: "Consegui reduzir custo logístico em " },
          { text: "3% YoY", bold: true },
          { text: ", expandir cobertura de 400 para " },
          { text: "800 cidades", bold: true },
          { text: " e gerar saving de R$ 70MM/ano com simulador proprietário de nível de serviço." },
        ]),

        espaco(6),

        // VivaReal ────────────────────────────────────────────────────────────
        cargoParagraph("Gerente de Planejamento Comercial e Operações", "VivaReal", "Mai 2015 – Dez 2017"),

        bullet([
          { text: "Fui responsável por operações comerciais e CX da VivaReal — marketplace B2B de imóveis —, arquitetando a área de Customer Experience que escalou para " },
          { text: "91 pessoas", bold: true },
          { text: ", além de liderar 33 pessoas em qualidade, SDR e cadastro." },
        ]),
        bullet([
          { text: "Utilizando " },
          { text: "Customer Journey", bold: true },
          { text: " mapping, segmentação de carteira e " },
          { text: "Talent Development", bold: true },
          { text: " — com contratação de liderança própria para CS — e régua de onboarding especializada por fase da jornada do cliente." },
        ]),
        bullet([
          { text: "Consegui churn abaixo de 3%/mês, " },
          { text: "NPS de 80%", bold: true },
          { text: ", CSAT acima de 92% e conversão SDR de 18% para " },
          { text: "50%", bold: true },
          { text: ", reduzindo custo de vendas em 40%." },
        ]),

        espaco(8),

        // ─── FORMAÇÃO ────────────────────────────────────────────────────────
        secao("Formação"),
        espaco(3),
        paragrafo("ILead Liderança para Líder de Líderes — Fundação Dom Cabral (2021)"),
        paragrafo("Six Sigma Green Belt — Setec Consulting (2020)"),
        paragrafo("MBA Corporate Strategy — BSP Business School São Paulo (2016–2017)"),
        paragrafo("Engenheiro Químico — Faculdades Oswaldo Cruz (2014)"),

        espaco(8),

        // ─── STACK TÉCNICA ───────────────────────────────────────────────────
        secao("Stack técnica"),
        espaco(3),
        paragrafo("SQL  ·  Python  ·  Zendesk  ·  Salesforce  ·  Metabase  ·  Power BI  ·  Excel/VBA"),

        espaco(8),

        // ─── IDIOMAS ─────────────────────────────────────────────────────────
        secao("Idiomas"),
        espaco(3),
        paragrafo("Português — Nativo     |     Inglês — Avançado"),
      ],
    }],
  });

  const buffer = await Packer.toBuffer(doc);
  const outputPath = path.join(outputDir, OUTPUT_NAME);
  fs.writeFileSync(outputPath, buffer);
  console.log("ok");
  console.log(outputPath);
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
