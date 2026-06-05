const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, TabStopPosition, TabStopType,
  ExternalHyperlink, BorderStyle, AlignmentType, LevelFormat, PageBreak
} = require("docx");

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

function txt(text, opts = {}) {
  return new TextRun({ text, bold: opts.bold || false, size: pt(9), font: "Arial" });
}

function hyperlink(text, url) {
  return new ExternalHyperlink({
    children: [new TextRun({ text, style: "Hyperlink", size: pt(9), font: "Arial" })],
    link: url
  });
}

const doc = new Document({
  styles: {
    default: { document: { run: { font: "Arial", size: pt(9) } } },
    paragraphStyles: [
      {
        id: "Normal", name: "Normal", quickFormat: true,
        run: { font: "Arial", size: pt(9) },
        paragraph: { spacing: { after: 0 } }
      },
      {
        id: "ListParagraph", name: "List Paragraph", basedOn: "Normal", quickFormat: true,
        run: { font: "Arial", size: pt(9) },
        paragraph: { spacing: { after: 0 } }
      }
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
      // Header
      new Paragraph({
        children: [new TextRun({ text: "Felipe Armel Dias da Silva", bold: true, size: pt(12), font: "Arial" })],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [hyperlink("linkedin.com/in/felipearmel", "https://linkedin.com/in/felipearmel")],
        spacing: { after: 0 }
      }),
      espaco(2),
      new Paragraph({
        children: [txt("São Paulo, SP")],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [hyperlink("(11) 98674-8218", "https://wa.me/5511986748218")],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [hyperlink("armelfelipe@gmail.com", "mailto:armelfelipe@gmail.com")],
        spacing: { after: 0 }
      }),
      espaco(8),

      // Resumo
      secao("Resumo"),
      espaco(3),
      new Paragraph({
        children: [txt("No iFood, como Diretor de Operações, liderei o S&OP executivo mensal com budget de R$300MM/ano e time de 240 pessoas. Como Head, criei simulador de nível de serviço com saving de R$70M/ano. Estruturei a área de S&OP do zero na Trifil e liderei projetos de redução de GGF (-R$8M). MBA Corporate Strategy pela BSP, busco posição de Gerente de Planejamento Estratégico onde possa estruturar governança, conectar estratégia à execução e gerar disciplina financeira.")],
        spacing: { after: 0 }
      }),
      espaco(8),

      // Experiencia
      secao("Experiência"),
      espaco(3),

      // iFood
      cargoParagraph("Head e Diretor de Operações", "iFood", "Nov 2018 – Mar 2024"),
      bullet([
        { text: "Fui responsável por gerir as operações logísticas do maior marketplace de food do Brasil, com equipe de " },
        { text: "240 pessoas", bold: true },
        { text: " e budget de " },
        { text: "R$300MM/ano", bold: true },
        { text: ", conduzindo o S&OP executivo mensal com a alta liderança e conectando marketing, clima, frota e operação em processo único de planejamento." }
      ]),
      bullet([
        { text: "Modelei dados com Python, SQL e Databricks, criei dashboards no Grafana e desenvolvi simulador de nível de serviço para balancear capacidade de frota por cidade com trade-offs entre custo e SLA." }
      ]),
      bullet([
        { text: "Ampliei a cobertura de " },
        { text: "400 para 800", bold: true },
        { text: " cidades, reduzi o custo logístico comparável em " },
        { text: "3% YoY", bold: true },
        { text: " e gerei saving de " },
        { text: "R$70M/ano", bold: true },
        { text: " com o simulador." }
      ]),
      espaco(6),

      // WeHandle
      cargoParagraph("Head de Operações", "wehandle", "Mai 2024 – Fev 2026"),
      bullet([
        { text: "Fui responsável pela operação de atendimento ao cliente com time de 30 pessoas, liderando a transformação digital do suporte com migração para plataforma IA first e integração omnichannel." }
      ]),
      bullet([
        { text: "Implantei chatbot com IA humanizada, integrei três plataformas de atendimento via API e conectei dados ao datalake para gerar insights que reduziram o contact rate em 8%." }
      ]),
      bullet([
        { text: "Reduzi o custo por atendimento de " },
        { text: "R$4,14 para R$3,61", bold: true },
        { text: " (" },
        { text: "-13%", bold: true },
        { text: "), o tempo médio de " },
        { text: "20 para 8 minutos", bold: true },
        { text: " e elevei o CSAT de " },
        { text: "85% para 92%", bold: true },
        { text: "." }
      ]),
      espaco(6),

      // Trifil
      cargoParagraph("Coordenador de S&OP | Supply Chain", "Trifil (Scalina)", "Jan 2006 – Set 2014"),
      bullet([
        { text: "Fui responsável por criar a área de S&OP do zero, sustentando os ritos por 4 anos com gestão de " },
        { text: "40K SKUs", bold: true },
        { text: " em duas marcas e todos os canais de distribuição, liderando o Projeto Entrega Certa com KPIs de OTIF, fill rate e acurácia reportados ao CEO." }
      ]),
      bullet([
        { text: "Liderei projeto de Strategic Sourcing em 150K+ SKUs e conduzi a modelagem econômico-financeira de projetos de capex com análise de ROI, VPL e Payback para aprovação da diretoria." }
      ]),
      bullet([
        { text: "Reduzi " },
        { text: "R$8M de GGF", bold: true },
        { text: " do P&L otimizando energia, gás e embalagens, reduzi custo de compras em " },
        { text: "27%", bold: true },
        { text: " e elevei a acurácia de estoque de " },
        { text: "85% para 98%", bold: true },
        { text: "." }
      ]),
      espaco(6),

      // Essencis
      cargoParagraph("Analista de Negócios", "Essencis", "Nov 2001 – Abr 2002"),
      bullet([
        { text: "Fui responsável por elaborar planos de negócio e modelagem econômico-financeira com DCF, VPL e Payback para projetos de expansão apresentados ao conselho da empresa." }
      ]),
      bullet([
        { text: "Modelei cenários de viabilidade e construí análises de impacto estratégico para tomada de decisão de M&A e investimento." }
      ]),
      bullet([
        { text: "Aprovei um projeto de aquisição de empresa em estágio de engenharia com business case aprovado em conselho." }
      ]),
      espaco(8),

      // Formacao
      secao("Formação"),
      espaco(3),
      new Paragraph({
        children: [txt("MBA Corporate Strategy — BSP Business School São Paulo (2016–2017)")],
        spacing: { after: pt(2) }
      }),
      new Paragraph({
        children: [txt("Engenharia Química — Faculdades Oswaldo Cruz (2014)")],
        spacing: { after: pt(2) }
      }),
      new Paragraph({
        children: [txt("Six Sigma Green Belt — Setec Consulting (2020)")],
        spacing: { after: pt(2) }
      }),
      new Paragraph({
        children: [txt("Planejamento e Orçamento — Saint Paul Escola de Negócios (2016)")],
        spacing: { after: pt(2) }
      }),
      espaco(8),

      // Stack
      secao("Stack técnica"),
      espaco(3),
      new Paragraph({
        children: [txt("Excel/VBA · SQL · Python · Databricks · Grafana · Power BI · Salesforce · Zendesk · ERP Infor LN")],
        spacing: { after: 0 }
      }),
      espaco(8),

      // Idiomas
      secao("Idiomas"),
      espaco(3),
      bullet([{ text: "Português — Nativo" }]),
      bullet([{ text: "Inglês — Avançado" }])
    ]
  }]
});

const outPath = "outputs/_tmp/cv_alloha_fibra.docx";
Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync(outPath, buffer);
  console.log("ok");
});
