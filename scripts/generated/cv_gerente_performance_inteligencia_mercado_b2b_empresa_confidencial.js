const fs = require("fs");
const { Document, Packer, Paragraph, TextRun, ExternalHyperlink, TabStopPosition, TabStopType, AlignmentType, LevelFormat, BorderStyle, PageBreak } = require("docx");

const pt = n => n * 2;

function secao(text) {
  return new Paragraph({
    children: [new TextRun({ text, size: pt(12), font: "Arial" })],
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "000000", space: 1 } },
    spacing: { before: pt(6), after: pt(3) }
  });
}

function espaco(ptSize = 6) {
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

function link(text, url) {
  return new ExternalHyperlink({
    children: [new TextRun({ text, style: "Hyperlink", size: pt(9), font: "Arial" })],
    link: url
  });
}

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
      // === HEADER ===
      new Paragraph({
        children: [new TextRun({ text: "Felipe Armel Dias da Silva", bold: true, size: pt(12), font: "Arial" })],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [link("linkedin.com/in/felipearmel", "https://linkedin.com/in/felipearmel")],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [new TextRun({ text: "São Paulo, SP", size: pt(9), font: "Arial" })],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [link("(11) 98674-8218", "https://wa.me/5511986748218")],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [link("armelfelipe@gmail.com", "mailto:armelfelipe@gmail.com")],
        spacing: { after: 0 }
      }),

      // === RESUMO ===
      espaco(8),
      secao("Resumo"),
      espaco(3),
      new Paragraph({
        children: [new TextRun({
          text: "Executivo sênior com 20+ anos em operações, planejamento e inteligência de mercado. No iFood, como Diretor de Operações, liderei budget de R$300MM/ano, expandi cobertura de 400 para 800 cidades e consolidei Executive Reporting para o C-level. Como Head, criei simulador com saving de R$70M/ano. Na Trifil, estruturei inteligência comercial do zero elevando faturamento de R$80M para R$120M/ano. Busco posição de Gerente de Performance e Inteligência de Mercado.",
          size: pt(9), font: "Arial"
        })],
        spacing: { after: 0 }
      }),

      // === EXPERIÊNCIA ===
      espaco(8),
      secao("Experiência"),
      espaco(3),

      // WeHandle
      cargoParagraph("Head de Operações", "wehandle", "Mai 2024 – Fev 2026"),
      bullet([
        { text: "Fui responsável pela operação de suporte a clientes com time de 30 pessoas, reestruturando processos e impactando ", bold: false },
        { text: "15% na margem bruta", bold: true },
        { text: " da companhia.", bold: false }
      ]),
      bullet([
        { text: "Liderei duas migrações de plataforma de atendimento para modelo IA first, implantei canal WhatsApp e automatizei processos com chatbot e inteligência artificial.", bold: false }
      ]),
      bullet([
        { text: "Reduzi o custo por atendimento de R$4,14 para R$3,61 (−13%)", bold: true },
        { text: " e elevei o CSAT de 85% para 92%.", bold: false }
      ]),
      espaco(6),

      // iFood Diretor
      cargoParagraph("Diretor de Operações", "iFood", "Abr 2022 – Mar 2024"),
      bullet([
        { text: "Fui responsável pelas operações logísticas com equipe de ~240 pessoas e budget de ", bold: false },
        { text: "R$300MM/ano", bold: true },
        { text: ", cobrindo FieldOps, Meios de Pagamento e Novos Negócios.", bold: false }
      ]),
      bullet([
        { text: "Conduzi o S&OP executivo mensal com modelagem em Python, SQL e Databricks, conectando marketing, clima, frota e operação em planejamento integrado, consolidando a Business Strategy da operação para decisões do C-level.", bold: false }
      ]),
      bullet([
        { text: "Ampliei a cobertura de 400 para 800 cidades", bold: true },
        { text: ", reduzi o custo logístico comparável em 3% YoY e mantive o SLA em 30M pedidos/mês.", bold: false }
      ]),
      espaco(6),

      // iFood Head
      cargoParagraph("Head de Operações", "iFood", "Nov 2018 – Mar 2022"),
      bullet([
        { text: "Fui responsável por liderar equipe de 28 pessoas em liveOps, pricing, modelagem de dados e planejamento de frota.", bold: false }
      ]),
      bullet([
        { text: "Criei dashboards em tempo real no Grafana, modelei dados com SQL e Databricks, e desenvolvi simulador de nível de serviço para decisões de balanceamento de frota por cidade.", bold: false }
      ]),
      bullet([
        { text: "Gerei saving de R$70M/ano", bold: true },
        { text: " com o simulador e reduzi cancelamentos em 60% no México ajustando raios de entrega.", bold: false }
      ]),
      espaco(6),

      // VivaReal
      cargoParagraph("Gerente de Planejamento Comercial e Operações", "VivaReal", "Mai 2015 – Dez 2017"),
      bullet([
        { text: "Fui responsável pelo planejamento comercial e operações com equipe de 33 pessoas, cobrindo SDR, qualidade e cadastro de imóveis.", bold: false }
      ]),
      bullet([
        { text: "Estruturei a esteira de SDR com análise de dados e definição de KPIs, apurei o comissionamento da força de vendas e fui arquiteto da área de CS que escalou para 91 pessoas.", bold: false }
      ]),
      bullet([
        { text: "Elevei a conversão inbound de 18% para 50%", bold: true },
        { text: ", reduzi o custo de vendas em 40% e mantive o churn abaixo de 3%/mês.", bold: false }
      ]),
      espaco(6),

      // Trifil
      cargoParagraph("Coordenador de Inteligência Comercial", "Scalina (Trifil)", "Jan 2009 – Dez 2009"),
      bullet([
        { text: "Fui responsável por criar a área de inteligência comercial do zero, estruturando dados de mercado, tendências e concorrência para orientar decisões de precificação e canal.", bold: false }
      ]),
      bullet([
        { text: "Modelei dados com Excel/VBA e SQL, automatizei relatórios que consumiam 4h para serem entregues em 14min e criei algoritmo de alocação de estoque por pedido.", bold: false }
      ]),
      bullet([
        { text: "Elevei o faturamento de R$80M para R$120M/ano", bold: true },
        { text: " com o sistema de alocação e reduzi relatórios de 4h para 14min.", bold: false }
      ]),

      // === FORMAÇÃO ===
      espaco(8),
      secao("Formação"),
      espaco(3),
      new Paragraph({
        children: [new TextRun({ text: "MBA Corporate Strategy — BSP Business School São Paulo (2017)", size: pt(9), font: "Arial" })],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [new TextRun({ text: "Engenharia Química — Faculdades Oswaldo Cruz (2014)", size: pt(9), font: "Arial" })],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [new TextRun({ text: "Six Sigma Green Belt — Setec Consulting (2020)", size: pt(9), font: "Arial" })],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [new TextRun({ text: "Liderança para Líder de Líderes — Fundação Dom Cabral (2021)", size: pt(9), font: "Arial" })],
        spacing: { after: 0 }
      }),

      // === STACK TÉCNICA ===
      espaco(8),
      secao("Stack técnica"),
      espaco(3),
      new Paragraph({
        children: [new TextRun({ text: "SQL · Python · Databricks · Excel/VBA · Grafana · Metabase · Tableau · Power BI · Salesforce · Zendesk · ERP Infor LN", size: pt(9), font: "Arial" })],
        spacing: { after: 0 }
      }),

      // === IDIOMAS ===
      espaco(8),
      secao("Idiomas"),
      espaco(3),
      bullet([{ text: "Português — Nativo", bold: false }]),
      bullet([{ text: "Inglês — Avançado", bold: false }])
    ]
  }]
});

Packer.toBuffer(doc).then(buffer => {
  const outPath = "outputs/_tmp/cv_gerente_performance_inteligencia_mercado_b2b_empresa_confidencial.docx";
  fs.writeFileSync(outPath, buffer);
  console.log("ok");
});
