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

const pt = n => n * 2; // half-points. NEVER n * 20 (twips).

const workspace = process.cwd();
const tempDir = path.join(workspace, "outputs", "_tmp");
const rawOutput = path.join(tempDir, "cv_petlove_gerente_ops_logisticas_raw.docx");

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

async function main() {
  fs.mkdirSync(tempDir, { recursive: true });
  const children = [
    // CABEÇALHO
    paragraph("Felipe Armel Dias da Silva", { size: 12, bold: true }),
    contactLink("linkedin.com/in/felipearmel", "https://linkedin.com/in/felipearmel"),
    paragraph("São Paulo, SP"),
    contactLink("(11) 98674-8218", "https://wa.me/5511986748218"),
    contactLink("armelfelipe@gmail.com", "mailto:armelfelipe@gmail.com"),

    espaco(8),

    // RESUMO
    secao("Resumo"),
    new Paragraph({
      children: [
        new TextRun({ text: "Gerente Sênior de Operações Logísticas com 20 anos de experiência em operações industriais, supply chain e logística. No iFood, como Diretor de Operações, gerenciei ", size: pt(9), font: "Arial" }),
        new TextRun({ text: "R$300MM/ano", bold: true, size: pt(9), font: "Arial" }),
        new TextRun({ text: " em OPEX logístico em operações B2C cobrindo 800 cidades. Na Trifil, implantei WMS, atingi ", size: pt(9), font: "Arial" }),
        new TextRun({ text: "98%", bold: true, size: pt(9), font: "Arial" }),
        new TextRun({ text: " de acurácia de estoque e estruturei S&OP gerenciando 40K SKUs nos canais varejo, distribuidor e franquias. Busco posição de Gerente de Operações Logísticas.", size: pt(9), font: "Arial" }),
      ],
      spacing: { after: 0 },
    }),

    espaco(8),

    // EXPERIÊNCIA
    secao("Experiência"),
    espaco(3),

    // wehandle
    cargoParagraph("Head de Operações", "wehandle", "mai/2024 – fev/2026"),
    bullet([
      { text: "Fui responsável por liderar equipe de 30 pessoas em operações de CX e suporte, estruturando SLAs, KPIs de atendimento e processos operacionais end-to-end em ambiente de construção de área." },
    ]),
    bullet([
      { text: "Utilizando automação com IA (Zendesk, CloudHumans), integração via API e dashboards em tempo real para tomada de decisão operacional." },
    ]),
    bullet([
      { text: "Consegui reduzir custo por atendimento de R$4,14 para " },
      { text: "R$3,61 (−13%)", bold: true },
      { text: ", impactando " },
      { text: "15%", bold: true },
      { text: " na margem bruta da operação." },
    ]),
    espaco(6),

    // iFood Diretor
    cargoParagraph("Diretor de Operações", "iFood", "abr/2022 – mar/2024"),
    bullet([
      { text: "Fui responsável por liderar " },
      { text: "240 pessoas", bold: true },
      { text: " em FieldOps, Meios de Pagamento e Novos Negócios, gerenciando OPEX logístico de " },
      { text: "R$300MM/ano", bold: true },
      { text: " em operações B2C de 800 cidades e 30M pedidos/mês." },
    ]),
    bullet([
      { text: "Utilizando S&OP executivo, capacity planning e KPIs em tempo real (Grafana, Databricks) para gestão de trade-offs custo vs. SLA em operação de larga escala." },
    ]),
    bullet([
      { text: "Consegui expandir cobertura de 400 para " },
      { text: "800 cidades", bold: true },
      { text: ", reduzir indisponibilidade de frota de 5% para 0,5% nas top 6 cidades e manter custo logístico 3% menor YoY." },
    ]),
    espaco(6),

    // iFood Head
    cargoParagraph("Head de Operações", "iFood", "nov/2018 – mar/2022"),
    bullet([
      { text: "Fui responsável por liderar " },
      { text: "28 pessoas", bold: true },
      { text: " em liveOps, pricing logístico e planejamento de frota, estruturando indicadores em tempo real e processos de abastecimento logístico em marketplace B2C de alta escala." },
    ]),
    bullet([
      { text: "Utilizando modelagem de dados (SQL, Databricks), Grafana e simulação de cenários de oferta e demanda por zona para gestão operacional em tempo real." },
    ]),
    bullet([
      { text: "Consegui criar simulador de nível de serviço com saving de " },
      { text: "R$70MM/ano", bold: true },
      { text: "; reduzir custo de distribuição em 80% (de 14 para 2 dias) e escalar para 352 cidades com zero perda financeira." },
    ]),
    espaco(6),

    // Scalina (Trifil)
    cargoParagraph("Coordenador de Expedição | Materiais | S&OP", "Scalina (Trifil)", "jan/2006 – set/2014"),
    bullet([
      { text: "Fui responsável por inbound, inventory management, controle de estoque e abastecimento com 40K SKUs, liderando expedição, planejamento de materiais e S&OP nos canais varejo, distribuidor e franquias com foco em ressuprimento e warehouse operations." },
    ]),
    bullet([
      { text: "Utilizando WMS com coletores RF/wi-fi, ERP Infor LN, PDCA/GPD e melhoria contínua, com safety stock por SKU e gestão de demanda." },
    ]),
    bullet([
      { text: "Consegui elevar acurácia de estoque de 85% para " },
      { text: "98%", bold: true },
      { text: ", aumentar produtividade em 35%, reduzir perdas em 30%, giro de estoque de 8 para 6 meses e gerar " },
      { text: "R$8MM", bold: true },
      { text: " de redução em GGF." },
    ]),

    espaco(8),

    // FORMAÇÃO
    secao("Formação"),
    espaco(3),
    paragraph("Six Sigma Green Belt — Setec Consulting (2020)"),
    espaco(2),
    paragraph("MBA Corporate Strategy — BSP Business School São Paulo (2016–2017)"),
    espaco(2),
    paragraph("Engenharia Química — Faculdades Oswaldo Cruz (2014)"),

    espaco(8),

    // STACK TÉCNICA
    secao("Stack técnica"),
    espaco(3),
    paragraph("WMS · ERP Infor LN · SQL · Python · Databricks · Grafana · Power BI · Excel/VBA · Lean · PDCA/GPD"),

    espaco(8),

    // IDIOMAS
    secao("Idiomas"),
    espaco(3),
    paragraph("Português — Nativo · Inglês — Avançado"),
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
          text: "•",
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
