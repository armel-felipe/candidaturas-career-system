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
const outputName = "felipe_armel_cv_gerente_operacoes_logisticas_petlove_working.docx";
const outputDir = path.join(workspace, "outputs");
const outputPath = path.join(outputDir, outputName);

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
      new TextRun({ text: `${cargo} - ${empresa}`, bold: true, size: pt(9), font: "Arial" }),
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

const experiences = [
  {
    cargo: "Head de Operacoes",
    empresa: "wehandle",
    periodo: "Mai/2024 - Fev/2026",
    bullets: [
      [{ text: "Fui responsavel por operacao de suporte e CX com " }, { text: "30 pessoas", bold: true }, { text: ", SLAs e melhoria de margem bruta em ambiente de construcao." }],
      [{ text: "Utilizando SQL, Metabase e APIs em " }, { text: "3 plataformas", bold: true }, { text: " de atendimento para decisao operacional em tempo real." }],
      [{ text: "Consegui elevar CSAT de " }, { text: "85% para 92%", bold: true }, { text: ", manter SLA em 95% dos tickets, reduzir TME de 20 para 8 minutos e impactar 15% na margem bruta." }],
    ],
  },
  {
    cargo: "Diretor de Operacoes",
    empresa: "iFood",
    periodo: "Abr/2022 - Mar/2024",
    bullets: [
      [{ text: "Fui responsavel por Operacoes Logisticas, B2C Operations, FieldOps, meios de pagamento e novos negocios, liderando " }, { text: "240 pessoas", bold: true }, { text: " e R$300MM/ano de custo logistico." }],
      [{ text: "Utilizando People Management, S&OP executivo e KPIs em " }, { text: "800 cidades", bold: true }, { text: " para balancear custo, nivel de servico e capacidade." }],
      [{ text: "Consegui expandir cobertura de 400 para " }, { text: "800 cidades", bold: true }, { text: ", aumentar pedidos agrupados de 12% para 25% e reduzir custo logistico comparavel em 3% YoY." }],
    ],
  },
  {
    cargo: "Head de Operacoes",
    empresa: "iFood",
    periodo: "Nov/2018 - Mar/2022",
    bullets: [
      [{ text: "Fui responsavel por liveOps, regionalOps, pricing, modelagem de dados e planejamento de frota com " }, { text: "28 pessoas", bold: true }, { text: " em operacao B2C de alta escala." }],
      [{ text: "Utilizando Grafana, SQL e Databricks em " }, { text: "30M pedidos/mes", bold: true }, { text: " para monitorar saturacao logistica, SLAs e oferta de entregadores." }],
      [{ text: "Consegui gerar " }, { text: "R$70MM/ano", bold: true }, { text: " de saving com simulador de nivel de servico e reduzir custo de distribuicao de MPOS em 80%, com lead time de 14 para 2 dias." }],
    ],
  },
  {
    cargo: "Gerente de Customer Success",
    empresa: "Renault do Brasil",
    periodo: "Jan/2018 - Out/2018",
    bullets: [
      [{ text: "Fui responsavel por migrar " }, { text: "2 BPOs com 40 PAs", bold: true }, { text: " para operacao propria de 8 pessoas, com governanca de SLA e controle de funil." }],
      [{ text: "Utilizando Power BI, Excel/VBA e discadores em " }, { text: "2 dias", bold: true }, { text: " para estabilizar a operacao e direcionar planos de acao." }],
      [{ text: "Consegui aumentar conversao de leads de " }, { text: "24% para 46%", bold: true }, { text: " e aprovar o projeto de internalizacao em 2 reunioes com ROI defendido para VP e controller." }],
    ],
  },
  {
    cargo: "Gerente de Planejamento Comercial e Operacoes",
    empresa: "VivaReal",
    periodo: "Mai/2015 - Dez/2017",
    bullets: [
      [{ text: "Fui responsavel por planejamento comercial, operacoes, qualidade, SDR e cadastro de imoveis, com " }, { text: "33 pessoas", bold: true }, { text: " e 5 liderancas diretas." }],
      [{ text: "Utilizando SQL, dashboards diarios e rituais semanais de produto em " }, { text: "3 frentes", bold: true }, { text: " para controlar metas, carteira e backlog operacional." }],
      [{ text: "Consegui elevar conversao SDR inbound de " }, { text: "18% para 50%", bold: true }, { text: ", reduzir custo de vendas em 40% e estruturar como arquiteto a area de CS que escalou para 91 pessoas." }],
    ],
  },
  {
    cargo: "Coordenador de S&OP",
    empresa: "Scalina (Trifil)",
    periodo: "Jan/2010 - Set/2014",
    bullets: [
      [{ text: "Fui responsavel por Abastecimento, Ressuprimento, planejamento de demanda e S&OP de " }, { text: "40K SKUs", bold: true }, { text: " em marcas, canais e lojas franqueadas." }],
      [{ text: "Utilizando Inventory Management, safety stock e KPIs em " }, { text: "4 anos", bold: true }, { text: " de ritos para equilibrar OTIF, fill rate, giro e liquidez de estoque." }],
      [{ text: "Consegui reduzir " }, { text: "R$8MM", bold: true }, { text: " de GGF, sustentar o Projeto Entrega Certa e melhorar o giro de estoque de 8 para 6 meses." }],
    ],
  },
  {
    cargo: "Coordenador de Planejamento de Materiais",
    empresa: "Scalina (Trifil)",
    periodo: "Nov/2007 - Dez/2008",
    bullets: [
      [{ text: "Fui responsavel por planejamento de materiais, compras de aviamentos, embalagens e fios em base com mais de " }, { text: "150K SKUs", bold: true }, { text: "." }],
      [{ text: "Utilizando Strategic Sourcing, MRP e analise de capacidade em " }, { text: "24 teares", bold: true }, { text: " para suportar suprimentos e decisao de investimento." }],
      [{ text: "Consegui reduzir custo de compras em " }, { text: "27%", bold: true }, { text: ", diminuir falta de estoque em 40% e aprovar projeto que reduziu custo de fabricacao em 15%." }],
    ],
  },
  {
    cargo: "Coordenador de Expedicao",
    empresa: "Scalina (Trifil)",
    periodo: "Jan/2007 - Out/2007",
    bullets: [
      [{ text: "Fui responsavel por Inbound, Controle de Estoque, Warehouse Operations, picking, packing, armazenagem e expedicao em " }, { text: "1 centro", bold: true }, { text: " de operacao fisica." }],
      [{ text: "Utilizando WMS, coletores RF e enderecamento em " }, { text: "1 operacao", bold: true }, { text: " que uniu separacao e conferencia no fluxo de expedicao." }],
      [{ text: "Consegui elevar acuracia de estoque de 85% para " }, { text: "98%", bold: true }, { text: ", aumentar produtividade em 35%, reduzir perdas em 30% e cortar tempo de pedidos customizados em 50%." }],
    ],
  },
];

async function main() {
  fs.mkdirSync(outputDir, { recursive: true });
  const children = [
    paragraph("Felipe Armel Dias da Silva", { size: 12, bold: true }),
    hyperlink("linkedin.com/in/felipearmel", "https://linkedin.com/in/felipearmel"),
    paragraph("Sao Paulo, SP"),
    hyperlink("(11) 98674-8218", "https://wa.me/5511986748218"),
    hyperlink("armelfelipe@gmail.com", "mailto:armelfelipe@gmail.com"),
    espaco(8),
    secao("Resumo"),
    paragraph("Executivo Senior em operacoes logisticas, estoque e planejamento. No iFood, como Diretor de Operacoes, liderei 240 pessoas e R$300MM/ano de custo logistico; na Trifil, atingi 98% de acuracia de estoque e geri 40K SKUs. Busco posicao de Gerente de Operacoes Logisticas."),
    espaco(8),
    secao("Experiencia"),
  ];

  experiences.forEach((exp, index) => {
    if (index > 0) children.push(espaco(6));
    children.push(cargoParagraph(exp.cargo, exp.empresa, exp.periodo));
    exp.bullets.forEach(item => children.push(bullet(item)));
  });

  children.push(
    espaco(8),
    secao("Formacao"),
    bullet([{ text: "ILEad lideranca para lider de lideres - Fundacao Dom Cabral (2021)." }]),
    bullet([{ text: "Six Sigma Green Belt - Setec Consulting (2020)." }]),
    bullet([{ text: "MBA Corporate Strategy - BSP Business School Sao Paulo (2016-2017)." }]),
    bullet([{ text: "Engenharia Quimica - Faculdades Oswaldo Cruz (2014)." }]),
    espaco(8),
    secao("Stack tecnica"),
    paragraph("WMS - ERP Infor LN - Excel/VBA - SQL - Python - Databricks - Grafana - Tableau - Power BI - Metabase"),
    espaco(8),
    secao("Idiomas"),
    paragraph("Portugues - Nativo"),
    paragraph("Ingles - Avancado")
  );

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
      children,
    }],
  });

  const buffer = await Packer.toBuffer(doc);
  fs.writeFileSync(outputPath, buffer);
  console.log("ok");
}

main().catch(error => {
  console.error(error);
  process.exit(1);
});
