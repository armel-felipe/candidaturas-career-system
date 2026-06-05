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

const workspace = process.env.CAREER_WORKSPACE || process.cwd();
const tempDir = path.join(workspace, "outputs", "_tmp");
const rawOutput = path.join(tempDir, "felipe_armel_cv_gerente_planejamento_e_logistica_einstein_hospital_israelita_raw.docx");

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
  fs.mkdirSync(tempDir, { recursive: true });

  const children = [
    paragraph("Felipe Armel Dias da Silva", { size: 12, bold: true }),
    hyperlink("linkedin.com/in/felipearmel", "https://linkedin.com/in/felipearmel"),
    paragraph("São Paulo, SP"),
    hyperlink("(11) 98674-8218", "https://wa.me/5511986748218"),
    hyperlink("armelfelipe@gmail.com", "mailto:armelfelipe@gmail.com"),

    espaco(8),

    secao("Resumo"),
    paragraph(
      "Executivo sênior com formação em Engenharia Química, MBA Corporate Strategy — BSP Business School São Paulo e atuação em planejamento de demanda, MRP, supply chain, politica de estoque, gestao de estoques, armazenagem, expedicao e nivel de servico logistico. No iFood, como Diretor de Operações, gerenciei R$300MM/ano e ampliei cobertura de 400 para 800 cidades. Na VivaReal, estruturei planejamento comercial, SDR e CS com escala para 91 pessoas e conversão inbound de 18% para 50%. Na Trifil, liderei S&OP, estoque e expedição com acuracidade de 98% e redução de R$8MM de GGF. Busco posição de Gerente Planejamento e Logística."
    ),

    espaco(8),

    secao("Experiência"),
    espaco(3),

    cargoParagraph("Head de Operações", "wehandle", "Mai 2024 – Fev 2026"),
    bullet([
      { text: "Fui responsável por liderar a operação de suporte e CX com 30 pessoas, monitorando SLA, taxa de contato e orçamento em uma área em construção." },
    ]),
    bullet([
      { text: "Estruturei integrações via API entre Movidesk, CloudHumans e Zendesk e conectei os dados em SQL, Python e Metabase para leitura em tempo real sem depender da área de dados." },
    ]),
    bullet([
      { text: "Implantei WhatsApp, chatbot e IA humanizada, reduzindo o custo total de R$4,14 para R$3,61 e o custo do canal WhatsApp de R$1,04 para R$0,56." },
    ]),
    bullet([
      { text: "Alcancei CSAT de 85% para 92%, SLA em 95% dos tickets e redução de 60% no backlog de cards, com impacto de 15% na margem bruta." },
    ]),

    espaco(6),

    cargoParagraph("Diretor de Operações", "iFood", "Abr 2022 – Mar 2024"),
    bullet([
      { text: "Fui responsável pela linha de custo das entregas com budget de R$300MM/ano e equipe de 240 pessoas entre FieldOps, Meios de Pagamento e Novos Negócios." },
    ]),
    bullet([
      { text: "Liderei S&OP executivo mensal com leitura de demanda, supply, frota, clima e promoções, usando Python, SQL, Databricks e Tableau para simulação de cenários." },
    ]),
    bullet([
      { text: "Ampliei cobertura de 400 para 800 cidades, reduzi indisponibilidade de frota de 5% para 1% no Brasil e de 5,4% para 0,5% nas top 6 cidades." },
    ]),
    bullet([
      { text: "Criei simulador de nivel de servico logistico que gerou saving de R$70MM/ano e reduziu o custo logístico comparável em 3% YoY." },
    ]),

    espaco(6),

    cargoParagraph("Head de Operações", "iFood", "Nov 2018 – Mar 2022"),
    bullet([
      { text: "Fui responsável por 28 pessoas em liveOps, regionalOps, pricing, modelagem de dados e planejamento de frota em operação nacional de alta criticidade." },
    ]),
    bullet([
      { text: "Estruturei métricas em tempo real no Grafana e modelei os dados com SQL, Databricks e Tableau para correlacionar saturação logística, frequência de pedidos e promessa de entrega." },
    ]),
    bullet([
      { text: "Estruturei o planejamento de frota OL e o balanceamento por cidade, ajustando raios de entrega no México e reduzindo cancelamentos em 60%." },
    ]),
    bullet([
      { text: "Implementei distribuição de MPOS, reduzindo custo em 80% e prazo de 14 para 2 dias, com expansão para 352 cidades e zero perda financeira." },
    ]),

    espaco(6),

    cargoParagraph("Gerente de Planejamento Comercial e Operações", "VivaReal", "Mai 2015 – Dez 2017"),
    bullet([
      { text: "Fui responsável por planejamento comercial e operações com 33 pessoas e 5 lideranças diretas, cobrindo qualidade, SDR, cadastro de imóveis e desdobramento de metas." },
    ]),
    bullet([
      { text: "Estruturei a área de CS do zero, definindo processos, régua de onboarding e contratação da liderança, com a operação escalando para 91 pessoas sob gestão de outros." },
    ]),
    bullet([
      { text: "Desenvolvi a esteira de SDR com SQL, dashboards e rotinas diárias, elevando a conversão inbound de 18% para 50% e reduzindo o custo de vendas em 40%." },
    ]),
    bullet([
      { text: "Alcancei churn abaixo de 3% ao mês, NPS de 80%, CSAT acima de 92% e recuperação de R$1MM em inadimplência nas campanhas de lançamento." },
    ]),

    espaco(6),

    cargoParagraph("Coordenador de S&OP", "Scalina (Trifil)", "Jan 2010 – Set 2014"),
    bullet([
      { text: "Fui responsável por criar e sustentar a área de S&OP do zero por 4 anos, com 40K SKUs e interface com comercial, PCP e fábricas." },
    ]),
    bullet([
      { text: "Estruturei planejamento de demanda, MRP corporativo, politica de estoque e gestao de estoques, definindo safety stock e calibrando capacidade de produção e outsourcing." },
    ]),
    bullet([
      { text: "Conduzi o Projeto Entrega Certa com OTIF, previsão de vendas, acuracidade de produção e giro de estoque como indicadores reportados ao CEO." },
    ]),
    bullet([
      { text: "Reduzi R$8MM de GGF, melhorei o giro de estoque de 8 para 6 meses e usei um simulador em Excel VBA para cenários de S&OP." },
    ]),

    espaco(6),

    cargoParagraph("Coordenador de Expedição", "Scalina (Trifil)", "Jan 2007 – Out 2007"),
    bullet([
      { text: "Fui responsável pelo centro de expedição com picking, packing, armazenagem e gestão do fluxo de devolução de cliente." },
    ]),
    bullet([
      { text: "Implantei inventário rotativo, endereçamento de estoque e coletores RF/wi-fi, elevando a acuracidade de 85% para 98%." },
    ]),
    bullet([
      { text: "Redesenhei o layout da área, aumentei a produtividade em 35% e reduzi perdas e refugos em 30%." },
    ]),
    bullet([
      { text: "Estruturei a área de packing e o sistema visual de abastecimento, reduzindo em 50% o preparo de pedidos customizados." },
    ]),

    espaco(8),

    secao("Formação"),
    espaco(3),
    paragraph("MBA Corporate Strategy — BSP Business School São Paulo (2016–2017)"),
    paragraph("Engenheiro Químico — Faculdades Oswaldo Cruz (2014)"),
    paragraph("Planejamento e Orçamento — Saint Paul Escola de Negócios (2016)"),
    paragraph("Six Sigma Green Belt — Setec Consulting (2020)"),

    espaco(8),

    secao("Stack técnica"),
    espaco(3),
    paragraph("Excel/VBA · SQL · Python · Databricks · Grafana · Tableau · Metabase · WMS · ERP Infor LN · Power BI"),

    espaco(8),

    secao("Idiomas"),
    espaco(3),
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
