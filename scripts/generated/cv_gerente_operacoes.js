const { Document, Packer, Paragraph, TextRun, BorderStyle, AlignmentType, TabStopType, TabStopPosition, LevelFormat } = require("docx");
const fs = require("fs");

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

function paragrafo(runs) {
  const children = runs.map(r =>
    new TextRun({ text: r.text, bold: r.bold || false, size: pt(9), font: "Arial" })
  );
  return new Paragraph({
    children,
    spacing: { after: pt(2) }
  });
}

const doc = new Document({
  styles: {
    default: {
      document: {
        run: { font: "Arial", size: pt(9) },
        paragraph: { spacing: { after: 0 } }
      }
    },
    paragraphStyles: [
      {
        id: "Normal",
        name: "Normal",
        basedOn: "Normal",
        next: "Normal",
        quickFormat: true,
        run: { font: "Arial", size: pt(9) },
        paragraph: { spacing: { after: 0 } }
      },
      {
        id: "ListParagraph",
        name: "List Paragraph",
        basedOn: "Normal",
        quickFormat: true,
        run: { font: "Arial", size: pt(9) },
        paragraph: { spacing: { after: 0 } }
      }
    ]
  },
  numbering: {
    config: [{
      reference: "bullets",
      levels: [{
        level: 0,
        format: LevelFormat.BULLET,
        text: "\u2022",
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
      // Cabeçalho
      new Paragraph({
        children: [new TextRun({ text: "Felipe Armel Dias da Silva", size: pt(12), bold: true, font: "Arial" })],
        spacing: { after: pt(3) }
      }),
      new Paragraph({
        children: [
          new TextRun({
            text: "linkedin.com/in/felipearmel",
            size: pt(9),
            font: "Arial",
            link: { target: "https://linkedin.com/in/felipearmel" }
          })
        ],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [
          new TextRun({
            text: "(11) 98674-8218",
            size: pt(9),
            font: "Arial",
            link: { target: "https://wa.me/5511986748218" }
          })
        ],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [
          new TextRun({
            text: "armelfelipe@gmail.com",
            size: pt(9),
            font: "Arial",
            link: { target: "mailto:armelfelipe@gmail.com" }
          })
        ],
        spacing: { after: pt(6) }
      }),

      // Resumo
      secao("Resumo"),
      paragrafo([
        { text: "Executivo Sênior com trajetória em operações de atendimento, logística e planejamento, atuando em empresas como iFood, wehandle e VivaReal. " },
        { text: "No iFood, como Diretor de Operações, ampliei cobertura de 400 para 800 cidades e reduzi custo logístico comparável em 3% YoY com budget de R$300MM/ano. ", bold: true },
        { text: "Na wehandle, como Head de Operações, reduzi custo por atendimento de R$4,14 para R$3,61 (−13%) e elevei CSAT de 85% para 92%. Busco posição de Gerente de Operações." }
      ]),
      espaco(8),

      // Experiência
      secao("Experiência"),
      
      // wehandle
      cargoParagraph("Head de Operações", "wehandle", "Mai 2024 – Fev 2026"),
      bullet([{ text: "Fui responsável por liderar customer support operations com time de 30 pessoas, reestruturando processos de atendimento e backoffice com impacto de 15% na margem bruta e SLA management." }]),
      bullet([{ text: "Implantei automação com IA e canal WhatsApp substituindo telefone, conectei dados de atendimento ao datalake via API e criei área de CX com board no ClickUp para priorização de bugs e process improvement." }]),
      bullet([
        { text: "Reduzi custo por atendimento de " },
        { text: "R$4,14 para R$3,61 (−13%)", bold: true },
        { text: ", elevei " },
        { text: "CSAT de 85% para 92%", bold: true },
        { text: ", alcancei " },
        { text: "SLA em 95% dos tickets", bold: true },
        { text: " e reduzi " },
        { text: "TME de 20 para 8 minutos (−60%)", bold: true },
        { text: "." }
      ]),
      espaco(6),

      // iFood
      cargoParagraph("Diretor de Operações", "iFood", "Abr 2022 – Mar 2024"),
      bullet([{ text: "Fui responsável por gerir as operações logísticas com equipe de ~240 pessoas e budget de R$300MM/ano, conduzindo S&OP executivo mensal com foco em CPO, cobertura e SLA com liderança de times multidisciplinares e performance analysis." }]),
      bullet([{ text: "Conduzi planejamento com S&OP executivo mensal, modelagem em Python, SQL e Databricks, e capacity planning de frota por cidade." }]),
      bullet([
        { text: "Ampliei " },
        { text: "cobertura de 400 para 800 cidades", bold: true },
        { text: ", reduzi " },
        { text: "custo logístico comparável em 3% YoY", bold: true },
        { text: " e mantive SLA em operação de " },
        { text: "30M pedidos/mês", bold: true },
        { text: "." }
      ]),
      espaco(6),

      // VivaReal
      cargoParagraph("Gerente de Planejamento Comercial e Operações", "VivaReal", "Mai 2015 – Dez 2017"),
      bullet([{ text: "Fui responsável por equipes de Qualidade, SDR e cadastro de imóveis (33 pessoas, 5 lideranças diretas), além de planejamento estratégico, precificação e comissionamento com monitoramento de KPIs." }]),
      bullet([{ text: "Estruturei processos de onboarding, métricas de CSAT e NPS, e usei Salesforce para pipeline, carteira, pricing e pagamentos com Power BI para inteligência de dados." }]),
      bullet([
        { text: "A área de CS escalou para " },
        { text: "91 pessoas com churn abaixo de 3%/mês e NPS de 80%", bold: true },
        { text: ", aumentei " },
        { text: "conversão SDR inbound de 18% para 50% (−40% custo de vendas)", bold: true },
        { text: " e recuperei " },
        { text: "R$1M em receita", bold: true },
        { text: " de inadimplentes." }
      ]),
      espaco(6),

      // Trifil
      cargoParagraph("Coordenador de S&OP", "Trifil", "Jan 2010 – Set 2014"),
      bullet([{ text: "Fui responsável por criar e sustentar a área de S&OP por 4 anos, gerenciando 40K SKUs em duas marcas e todos os canais, com reporte de OTIF e fill rate ao CEO." }]),
      bullet([{ text: "Criei simulador de MRP/S&OP em Excel VBA para avaliação de cenários e liderei o projeto GGF 2014 de otimização de custos industriais." }]),
      bullet([
        { text: "Reduzi " },
        { text: "R$8MM de GGF do P&L", bold: true },
        { text: " e mantive economia de " },
        { text: "R$4,6M acima da meta em ago/2014", bold: true },
        { text: "." }
      ]),
      espaco(8),

      // Formação
      secao("Formação"),
      bullet([{ text: "MBA Corporate Strategy — BSP Business School São Paulo (2016–2017)" }]),
      bullet([{ text: "Engenheiro Químico — Faculdades Oswaldo Cruz (2014)" }]),
      bullet([{ text: "Six Sigma Green Belt — Setec Consulting (2020)" }]),
      bullet([{ text: "ILEad — Fundação Dom Cabral (2021)" }]),
      espaco(8),

      // Stack técnica
      secao("Stack técnica"),
      paragrafo([{ text: "Excel/VBA · SQL · Python · Databricks · Power BI · Tableau · Salesforce · Zendesk · ERP Infor LN · WMS" }]),
      espaco(8),

      // Idiomas
      secao("Idiomas"),
      bullet([{ text: "Português — Nativo" }]),
      bullet([{ text: "Inglês — Avançado" }])
    ]
  }]
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync("outputs/_tmp/cv_gerente_operacoes.docx", buffer);
  console.log("ok");
});
