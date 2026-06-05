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

const pt = n => n * 2; // half-points. Never use n * 20 here.

const workspace = process.cwd();
const tempDir = path.join(workspace, "outputs", "_tmp");
const rawOutput = path.join(tempDir, "cv_gerente_senior_supply_chain_adm_raw.docx");

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
  const children = runs.map(r =>
    new TextRun({ text: r.text, bold: r.bold || false, size: pt(9), font: "Arial" })
  );
  return new Paragraph({
    numbering: { reference: "bullets", level: 0 },
    children,
    spacing: { after: pt(2) },
  });
}

function paragraph(text, options = {}) {
  return new Paragraph({
    children: [new TextRun({ text, size: pt(options.size || 9), bold: !!options.bold, font: "Arial" })],
    spacing: { after: 0 },
  });
}

function contactLink(text, url) {
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

function plainBullet(text) {
  return bullet([{ text }]);
}

async function main() {
  fs.mkdirSync(tempDir, { recursive: true });
  const children = [
    paragraph("Felipe Armel Dias da Silva", { size: 12, bold: true }),
    contactLink("linkedin.com/in/felipearmel", "https://linkedin.com/in/felipearmel"),
    paragraph("São Paulo, SP"),
    contactLink("(11) 98674-8218", "https://wa.me/5511986748218"),
    contactLink("armelfelipe@gmail.com", "mailto:armelfelipe@gmail.com"),

    espaco(8),
    secao("Resumo"),
    paragraph("Engenheiro Químico com trajetória em Supply Chain Management, S&OP, MPS, MRP, Inventory Management e logística. Na Trifil, liderei planejamento industrial de 40K SKUs; no iFood, gestão de R$300MM/ano em custo logístico. Busco posição de Gerente Sênior de Supply Chain."),

    espaco(8),
    secao("Experiência"),

    cargoParagraph("Head de Operações", "wehandle", "mai/2024 - fev/2026"),
    bullet([
      { text: "Fui responsável por liderar operação de suporte com " },
      { text: "30 pessoas", bold: true },
      { text: ", estruturando indicadores de SLA, CSAT, taxa de contato e orçamento de custos." },
    ]),
    bullet([
      { text: "Utilizando " },
      { text: "3 plataformas", bold: true },
      { text: " de atendimento, APIs e Metabase, conectei dados operacionais ao datalake para decisão diária." },
    ]),
    bullet([
      { text: "Consegui impacto de " },
      { text: "15%", bold: true },
      { text: " na margem bruta e reduzi custo por atendimento de R$4,14 para R$3,61 (-13%)." },
    ]),
    espaco(6),

    cargoParagraph("Diretor de Operações", "iFood", "abr/2022 - mar/2024"),
    bullet([
      { text: "Fui responsável por operação logística com " },
      { text: "240 pessoas", bold: true },
      { text: ", FieldOps, meios de pagamento e S&OP executivo para custo, demanda, supply e Service Level." },
    ]),
    bullet([
      { text: "Utilizando " },
      { text: "3 frentes", bold: true },
      { text: " de Capacity Planning, KPIs e cenários de demanda, conduzi trade-offs entre nível de serviço e custo logístico." },
    ]),
    bullet([
      { text: "Consegui gerir " },
      { text: "R$300MM/ano", bold: true },
      { text: " em budget de custo logístico, reduzir custo comparável em 3% YoY e expandir cobertura de 400 para 800 cidades." },
    ]),
    espaco(6),

    cargoParagraph("Head de Operações", "iFood", "nov/2018 - mar/2022"),
    bullet([
      { text: "Fui responsável por liderar " },
      { text: "28 pessoas", bold: true },
      { text: " em liveOps, regionalOps, pricing, modelagem de dados e planejamento de frota por cidade." },
    ]),
    bullet([
      { text: "Utilizando " },
      { text: "3 alavancas", bold: true },
      { text: " de Capacity Planning, SQL/Databricks e Grafana, estruturei simulador de nível de serviço e distribuição de MPOS." },
    ]),
    bullet([
      { text: "Consegui saving de " },
      { text: "R$70MM/ano", bold: true },
      { text: ", reduzir custo de distribuição de MPOS em 80% e lead time de 14 para 2 dias." },
    ]),
    espaco(6),

    cargoParagraph("Coordenador de S&OP", "Scalina (Trifil)", "jan/2010 - set/2014"),
    bullet([
      { text: "Fui responsável por criar o S&OP do zero por " },
      { text: "4 anos", bold: true },
      { text: ", gerindo Supply Chain Management, Demand Planning, Production Planning, MPS, MRP e 40K SKUs." },
    ]),
    bullet([
      { text: "Utilizando " },
      { text: "3 instrumentos", bold: true },
      { text: " de MRP, Capacity Planning e KPIs, defini safety stock, calendário de S&OP e cenários com Excel/VBA." },
    ]),
    bullet([
      { text: "Consegui reduzir " },
      { text: "R$8MM", bold: true },
      { text: " de GGF, sustentar OTIF/fill rate/acurácia de previsão e equilibrar nível de serviço com liquidez de estoque." },
    ]),
    espaco(6),

    cargoParagraph("Coordenador de Planejamento de Materiais", "Scalina (Trifil)", "nov/2007 - dez/2008"),
    bullet([
      { text: "Fui responsável por Material Planning de " },
      { text: "150K+ SKUs", bold: true },
      { text: ", incluindo aviamentos, embalagens, fios, regras do plano de produção e período congelado." },
    ]),
    bullet([
      { text: "Utilizando " },
      { text: "3 frentes", bold: true },
      { text: " de Strategic Sourcing, MRP e análise de capacidade, dimensionei materiais e investimentos produtivos." },
    ]),
    bullet([
      { text: "Consegui reduzir custo de compras em " },
      { text: "27%", bold: true },
      { text: ", falta de estoque em 40%, giro de 8 para 6 meses e custo de fabricação em 15%." },
    ]),
    espaco(6),

    cargoParagraph("Coordenador de Expedição", "Scalina (Trifil)", "jan/2007 - out/2007"),
    bullet([
      { text: "Fui responsável por Inventory Management e expedição com " },
      { text: "1 centro", bold: true },
      { text: " de picking, packing, armazenagem, endereçamento, devoluções e abastecimento visual." },
    ]),
    bullet([
      { text: "Utilizando " },
      { text: "3 recursos", bold: true },
      { text: " de WMS, coletores RF/wi-fi e inventário rotativo, uni separação e conferência em uma operação." },
    ]),
    bullet([
      { text: "Consegui elevar acurácia de estoque de 85% para " },
      { text: "98%", bold: true },
      { text: ", aumentar produtividade em 35%, reduzir perdas em 30% e pedidos customizados em 50%." },
    ]),

    espaco(8),
    secao("Formação"),
    plainBullet("Six Sigma Green Belt — Setec Consulting (2020)"),
    plainBullet("MBA Corporate Strategy — BSP Business School São Paulo (2016-2017)"),
    plainBullet("Engenharia Química — Faculdades Oswaldo Cruz (concluído 2014)"),
    plainBullet("Planejamento e Previsão de Demanda — CEBRALOG (2014)"),

    espaco(8),
    secao("Stack técnica"),
    paragraph("Excel/VBA · Power BI · SQL · Python · Databricks · Grafana · Tableau · Metabase · ERP Infor LN · WMS"),

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
  console.log("ok");
}

main().catch(error => {
  console.error(error);
  process.exit(1);
});
