const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, ExternalHyperlink,
  TabStopType, TabStopPosition, BorderStyle, LevelFormat, AlignmentType,
  Numbering
} = require("docx");

const pt = n => n * 2;

const espaco = (ptSize = 6) => new Paragraph({
  children: [new TextRun({ text: "", size: pt(ptSize), font: "Arial" })],
  spacing: { after: 0 }
});

const secao = (text) => new Paragraph({
  children: [new TextRun({ text, size: pt(12), font: "Arial" })],
  border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "000000", space: 1 } },
  spacing: { before: pt(6), after: pt(3) }
});

const cargo = (cargoTexto, empresa, periodo) => new Paragraph({
  tabStops: [{ type: TabStopType.RIGHT, position: TabStopPosition.MAX }],
  children: [
    new TextRun({ text: `${cargoTexto} — ${empresa}`, bold: true, size: pt(9), font: "Arial" }),
    new TextRun({ text: "\t" + periodo, size: pt(9), font: "Arial" })
  ],
  spacing: { after: 0 }
});

const bullet = (runs) => new Paragraph({
  numbering: { reference: "bullets", level: 0 },
  children: runs.map(r => new TextRun({ text: r.text, bold: r.bold || false, size: pt(9), font: "Arial" })),
  spacing: { after: pt(2) }
});

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
      // Nome
      new Paragraph({
        children: [new TextRun({ text: "Felipe Armel Dias da Silva", bold: true, size: pt(12), font: "Arial" })],
        spacing: { after: 0 }
      }),

      // Contato — links
      new Paragraph({
        children: [new ExternalHyperlink({ link: "https://linkedin.com/in/felipearmel", children: [new TextRun({ text: "linkedin.com/in/felipearmel", style: "Hyperlink", size: pt(9), font: "Arial" })] })],
        spacing: { after: 0 }
      }),
      new Paragraph({ children: [new TextRun({ text: "São Paulo, SP", size: pt(9), font: "Arial" })], spacing: { after: 0 } }),
      new Paragraph({
        children: [new ExternalHyperlink({ link: "https://wa.me/5511986748218", children: [new TextRun({ text: "(11) 98674-8218", style: "Hyperlink", size: pt(9), font: "Arial" })] })],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [new ExternalHyperlink({ link: "mailto:armelfelipe@gmail.com", children: [new TextRun({ text: "armelfelipe@gmail.com", style: "Hyperlink", size: pt(9), font: "Arial" })] })],
        spacing: { after: 0 }
      }),

      espaco(8),

      // Resumo
      secao("Resumo"),
      espaco(3),
      new Paragraph({
        children: [          new TextRun({ text: "Executivo com engenharia química e MBA pela BSP, trajetória em S&OP e operações no iFood, WeHandle, VivaReal e Trifil. Como Diretor de Operações, liderei S&OP executivo com budget de ", size: pt(9), font: "Arial" }),
          new TextRun({ text: "R$300MM/ano", bold: true, size: pt(9), font: "Arial" }),
          new TextRun({ text: ". Como Head, criei simulador com saving de ", size: pt(9), font: "Arial" }),
          new TextRun({ text: "R$70M/ano", bold: true, size: pt(9), font: "Arial" }),
          new TextRun({ text: ". Na Trifil, criei a área de S&OP do zero reduzindo ", size: pt(9), font: "Arial" }),
          new TextRun({ text: "R$8MM de GGF", bold: true, size: pt(9), font: "Arial" }),
          new TextRun({ text: ". Busco posicao de Gerente de Planejamento Integrado liderando o Plano Operacional Unico.", size: pt(9), font: "Arial" })
        ],
        spacing: { after: 0 }
      }),

      espaco(8),

      // Experiência
      secao("Experiência"),
      espaco(3),

      // WeHandle
      cargo("Head de Operações", "WeHandle", "Mai 2024 – Fev 2026"),
      bullet([
        { text: "Fui responsável por liderar a operação de suporte ao cliente com time de 30 pessoas, reestruturando processos e custos com impacto de ", bold: false },
        { text: "15% na margem bruta", bold: true },
        { text: " da empresa.", bold: false }
      ]),
      bullet([
        { text: "Liderei duas migrações de plataforma de atendimento para modelo IA first, integrei dados via API entre três plataformas e implementei canal WhatsApp com automação por chatbot.", bold: false }
      ]),
      bullet([
        { text: "Reduzi o custo total por atendimento de ", bold: false },
        { text: "R$4,14 para R$3,61 (−13%)", bold: true },
        { text: ", o TME de 20 para 8 minutos e elevei o CSAT de 85% para 92%.", bold: false }
      ]),
      espaco(6),

      // iFood Diretor
      cargo("Diretor de Operações", "iFood", "Abr 2022 – Mar 2024"),
      bullet([
        { text: "Fui responsável por gerir as operações logísticas com equipe de ~240 pessoas e budget de ", bold: false },
        { text: "R$300MM/ano", bold: true },
        { text: ", conduzindo o S&OP executivo mensal com trade-offs de custo e nível de serviço.", bold: false }
      ]),
      bullet([
        { text: "Liderei o planejamento integrado conectando marketing, promoções, clima, frota e supply em processo único, com modelagem em Python e Databricks para planejamento de capacidade por cidade.", bold: false }
      ]),
      bullet([
        { text: "Ampliei a cobertura logística de ", bold: false },
        { text: "400 para 800 cidades", bold: true },
        { text: ", reduzi o custo comparável em ", bold: false },
        { text: "3% YoY", bold: true },
         { text: " com analise de performance continua (PDCA semanal) de variacao vs meta e aumentei o agrupamento de entregas de 12% para 25%.", bold: false }
      ]),
      espaco(6),

      // iFood Head
      cargo("Head de Operações", "iFood", "Nov 2018 – Mar 2022"),
      bullet([
        { text: "Fui responsável pela estruturação de liveOps, planejamento de frota, pricing e modelagem de dados com equipe de 28 pessoas, atuando em interface direta com engenharia de produto.", bold: false }
      ]),
      bullet([
         { text: "Criei um simulador de nivel de servico para simulacao de cenarios de frota, demanda e raios de entrega, utilizando SQL e Databricks para analise de elasticidade de preco por zona.", bold: false }
      ]),
      bullet([
        { text: "Gerei saving de ", bold: false },
        { text: "R$70M/ano", bold: true },
        { text: " com o simulador, reduzi a indisponibilidade de frota de 5% para 1%, implementei torre no México com ", bold: false },
        { text: "−60% de cancelamentos", bold: true },
        { text: " e reduzi em 80% o custo de distribuição de MPOS.", bold: false }
      ]),
      espaco(6),

      // VivaReal
      cargo("Gerente de Planejamento Comercial e Operações", "VivaReal", "Mai 2015 – Dez 2017"),
      bullet([
        { text: "Fui responsável pelo planejamento estratégico, desdobramento de metas, definição de preços e comissionamento da força de vendas, atuando como arquiteto da área de CS com 33 pessoas sob gestão de 5 lideranças diretas.", bold: false }
      ]),
      bullet([
        { text: "Estruturei a régua de onboarding, implantei processo de SDR com dados de tempo ideal de contato e utilizei SQL e dashboards automatizados para inteligência de dados comerciais.", bold: false }
      ]),
      bullet([
        { text: "Elevei a conversão SDR inbound de ", bold: false },
        { text: "18% para 50%", bold: true },
        { text: ", reduzi o custo de vendas em 40%, recuperei ", bold: false },
        { text: "R$1M em inadimplentes", bold: true },
        { text: ", alcancei NPS de 80% e CSAT acima de 92%.", bold: false }
      ]),
      espaco(6),

      // Trifil S&OP
      cargo("Coordenador de S&OP", "Trifil", "Jan 2010 – Set 2014"),
      bullet([
        { text: "Fui responsável por criar a área de S&OP do zero, coordenando o ciclo mensal de planejamento tático-estratégico e a rotina semanal de execução para correção de rota, intermediando comercial e produção para ", bold: false },
        { text: "40K SKUs", bold: true },
        { text: " em 2 marcas.", bold: false }
      ]),
      bullet([
        { text: "Criei um simulador de MRP e avaliação de cenários em Excel VBA, defini política de safety stock e coordenei planejamento de outsourcing nacional e internacional.", bold: false }
      ]),
      bullet([
        { text: "Reduzi ", bold: false },
        { text: "R$8MM de GGF", bold: true },
        { text: " do P&L com projeto de otimização de energia, gás e embalagens, gerei MRP corporativo com análise de capacidade de produção e sustentei os ritos de S&OP por 4 anos.", bold: false }
      ]),

      espaco(8),

      // Formação
      secao("Formação"),
      espaco(3),
      bullet([{ text: "MBA Corporate Strategy — BSP Business School São Paulo (2016–2017)", bold: false }]),
      bullet([{ text: "Engenharia Química — Faculdades Oswaldo Cruz (2014)", bold: false }]),
      bullet([{ text: "Six Sigma Green Belt — Setec Consulting (2020)", bold: false }]),
      bullet([{ text: "Problem Solving — Ventus Consulting (2020)", bold: false }]),
      bullet([{ text: "ILíder para líder de líderes — Fundação Dom Cabral (2021)", bold: false }]),

      espaco(8),

      // Stack técnica
      secao("Stack técnica"),
      espaco(3),
      new Paragraph({
        children: [new TextRun({ text: "Python · SQL · Databricks · Grafana · Excel/VBA · ERP Infor LN · Zendesk · Salesforce · Power BI · Metabase · Tableau", size: pt(9), font: "Arial" })],
        spacing: { after: 0 }
      }),

      espaco(8),

      // Idiomas
      secao("Idiomas"),
      espaco(3),
      bullet([{ text: "Português — Nativo", bold: false }]),
      bullet([{ text: "Inglês — Avançado", bold: false }])
    ]
  }]
});

Packer.toBuffer(doc).then(buffer => {
  const outPath = "outputs/_tmp/cv_gerente_planejamento_integrado_atvos.docx";
  fs.writeFileSync(outPath, buffer);
  console.log("ok");
});
