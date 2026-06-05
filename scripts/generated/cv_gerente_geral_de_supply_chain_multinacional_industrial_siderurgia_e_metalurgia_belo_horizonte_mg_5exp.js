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

const pt = n => n * 2;

const workspace = process.cwd();
const tempDir = path.join(workspace, "outputs", "_tmp");
const outputName = "felipe_armel_cv_gerente_geral_de_supply_chain_multinacional_industrial_siderurgia_e_metalurgia_belo_horizonte_mg_5exp.docx";
const rawOutput = path.join(tempDir, "felipe_armel_cv_gerente_geral_de_supply_chain_multinacional_industrial_siderurgia_e_metalurgia_belo_horizonte_mg_5exp_raw.docx");

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
    children: runs.map(run => new TextRun({ text: run.text, bold: !!run.bold, size: pt(9), font: "Arial" })),
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
  fs.mkdirSync(tempDir, { recursive: true });

  const children = [
    paragraph("Felipe Armel Dias da Silva", { size: 12, bold: true }),
    hyperlink("linkedin.com/in/felipearmel", "https://linkedin.com/in/felipearmel"),
    paragraph("São Paulo, SP"),
    hyperlink("(11) 98674-8218", "https://wa.me/5511986748218"),
    hyperlink("armelfelipe@gmail.com", "mailto:armelfelipe@gmail.com"),

    espaco(8),
    secao("Resumo"),
    paragraph("Engenheiro Químico com atuação em operações, planejamento industrial e cadeia de suprimentos. No iFood, como Diretor de Operações, gerei budget de R$300MM/ano e ampliei cobertura de 400 para 800 cidades. Na Trifil, criei a área de S&OP e reduzi R$8MM de GGF."),

    espaco(8),
    secao("Experiência"),

    cargoParagraph("Head de Operações", "wehandle", "Mai 2024 – Fev 2026"),
    bullet([
      { text: "Fui responsável por liderar a operação de suporte com ", bold: false },
      { text: "30 pessoas", bold: true },
      { text: ", organizando SLA, CSAT, taxa de contato, orçamento e backlog junto ao time de produto." },
    ]),
    bullet([
      { text: "Liderei migrações de plataforma, automação com IA e canal de WhatsApp, conectando dados via API e Metabase para decisão diária." }],
    ),
    bullet([
      { text: "Reduzi o custo por atendimento de ", bold: false },
      { text: "R$4,14 para R$3,61", bold: true },
      { text: ", derrubei o backlog em 60% e mantive SLA em 95% dos tickets." },
    ]),

    espaco(6),
    cargoParagraph("Diretor de Operações", "iFood", "Abr 2022 – Mar 2024"),
    bullet([
      { text: "Fui responsável por uma operação de ", bold: false },
      { text: "240 pessoas", bold: true },
      { text: " em FieldOps, meios de pagamento e novos negócios, com S&OP executivo e budget logístico." },
    ]),
    bullet([
      { text: "Liderei planejamento de capacidade, modelagem em SQL, Python, Databricks e Tableau, e governança mensal com demanda, supply, custo e nível de serviço." }],
    ),
    bullet([
      { text: "Ampliei a cobertura de ", bold: false },
      { text: "400 para 800 cidades", bold: true },
      { text: ", reduzi custo comparável em 3% YoY e encurtei o prazo de distribuição de 14 para 2 dias dentro do budget de R$300MM/ano." },
    ]),

    espaco(6),
    cargoParagraph("Head de Operações", "iFood", "Nov 2018 – Mar 2022"),
    bullet([
      { text: "Fui responsável por liderar ", bold: false },
      { text: "28 pessoas", bold: true },
      { text: " em liveOps, regionalOps, pricing, modelagem de dados e planejamento de frota por cidade." },
    ]),
    bullet([
      { text: "Estruturei Order Management do fluxo de distribuição de MPOS, com modelagem em SQL/Databricks e métricas em tempo real no Grafana." }],
    ),
    bullet([
      { text: "Consegui saving de ", bold: false },
      { text: "R$70MM/ano", bold: true },
      { text: ", reduzir o custo de distribuição de MPOS em 80% e estabilizar a operação em 352 cidades." },
    ]),

    espaco(6),
    cargoParagraph("Coordenador de S&OP", "Scalina (Trifil)", "Jan 2010 – Set 2014"),
    bullet([
      { text: "Fui responsável por planejamento da cadeia de suprimentos do zero, sustentando os ritos por ", bold: false },
      { text: "4 anos", bold: true },
      { text: " e gerindo 40K SKUs." },
    ]),
    bullet([
      { text: "Implantei OTIF, fill rate, acurácia de previsão e sequenciamento da produção com Excel/VBA para apoiar produção e estoque." }],
    ),
    bullet([
      { text: "Reduzi ", bold: false },
      { text: "R$8MM", bold: true },
      { text: " de GGF, elevei a acurácia de estoque para 98% e sustentei a liquidez com trade-offs de serviço." },
    ]),

    espaco(6),
    cargoParagraph("Coordenador de Planejamento de Materiais", "Scalina (Trifil)", "Nov 2007 – Dez 2008"),
    bullet([
      { text: "Fui responsável por planejamento de materiais para ", bold: false },
      { text: "150K+ SKUs", bold: true },
      { text: ", incluindo aviamentos, embalagens, fios e regras do plano de produção." },
    ]),
    bullet([
      { text: "Estruturei planejamento de inventário com compras, MRP e análise de capacidade para balancear abastecimento, estoque e produção." }],
    ),
    bullet([
      { text: "Reduzi custo de compras em ", bold: false },
      { text: "27%", bold: true },
      { text: ", falta de estoque em 40% e apliquei Product Scheduling no sequenciamento da produção." },
    ]),

    espaco(8),
    secao("Formação"),
    paragraph("MBA Corporate Strategy — BSP Business School São Paulo (2016–2017)"),
    paragraph("Engenharia Química — Faculdades Oswaldo Cruz (concluído 2014)"),
    paragraph("Setec Consulting (2020)"),
    paragraph("Planejamento e Previsão de Demanda — CEBRALOG (2014)"),

    espaco(8),
    secao("Stack técnica"),
    paragraph("Excel/VBA · SQL · Python · Databricks · Grafana · Tableau · Metabase · ERP Infor LN · WMS"),

    espaco(8),
    secao("Idiomas"),
    paragraph("Português — Nativo"),
    paragraph("Inglês — Avançado"),
  ];

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
          size: { width: 11906, height: 16838 },
          margin: { top: 720, right: 504, bottom: 720, left: 504 },
        },
      },
      children,
    }],
  });

  const buffer = await Packer.toBuffer(doc);
  fs.writeFileSync(rawOutput, buffer);
  console.log(rawOutput);
}

main().catch(error => {
  console.error(error);
  process.exit(1);
});
