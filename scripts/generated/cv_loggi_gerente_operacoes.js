const { Document, Packer, Paragraph, TextRun, BorderStyle, AlignmentType, TabStopPosition, TabStopType, LevelFormat } = require("docx");
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

const doc = new Document({
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
  sections: [{
    properties: {
      page: {
        margin: { top: 720, right: 504, bottom: 720, left: 504 }
      }
    },
    children: [
      // Cabeçalho
      new Paragraph({
        children: [
          new TextRun({ text: "Felipe Armel Dias da Silva", bold: true, size: pt(12), font: "Arial" })
        ],
        spacing: { after: pt(3) }
      }),
      new Paragraph({
        children: [
          new TextRun({
            text: "linkedin.com/in/felipearmel",
            size: pt(9),
            font: "Arial",
            link: "https://linkedin.com/in/felipearmel"
          })
        ],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [
          new TextRun({ text: "São Paulo, SP", size: pt(9), font: "Arial" })
        ],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [
          new TextRun({
            text: "(11) 98674-8218",
            size: pt(9),
            font: "Arial",
            link: "https://wa.me/5511986748218"
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
            link: "mailto:armelfelipe@gmail.com"
          })
        ],
        spacing: { after: pt(6) }
      }),

      // Resumo
      secao("Resumo"),
      bullet([{
        text: "Engenheiro Químico com MBA Corporate Strategy. Executivo sênior com 18+ anos em Last Mile e operações logísticas. No iFood, como Diretor de Operações, ampliei cobertura de 400 para 800 cidades e reduzi custo logístico em 3% YoY com budget de R$300MM/ano. Como Head de Operações, gerei saving de R$70MM/ano com simulador de nível de serviço. Na Trifil, reduzi R$8MM de GGF e elevei acurácia de estoque para 98%. Busco posição de Gerente de Operações Logísticas Last Mile.",
        bold: false
      }]),
      espaco(8),

      // Experiência
      secao("Experiência"),
      espaco(3),

      // wehandle
      cargoParagraph("Head de Operações", "wehandle", "Mai 2024 – Fev 2026"),
      bullet([{
        text: "Fui responsável por liderança de equipes com 30 pessoas e redução de custos de ",
        bold: false
      }, {
        text: "15% na margem bruta",
        bold: true
      }, {
        text: " através de simulações de receita e identificação de alavancas operacionais.",
        bold: false
      }]),
      bullet([{
        text: "Liderei melhoria de processos com automação IA, WhatsApp e migração para Zendesk, conectando dados ao datalake via API.",
        bold: false
      }]),
      bullet([{
        text: "Reduzi custo por atendimento de ",
        bold: false
      }, {
        text: "R$4,14 para R$3,61 (−13%)",
        bold: true
      }, {
        text: ", elevei CSAT de 85% para 92% e atingi gestão de SLA em 95% dos tickets.",
        bold: false
      }]),
      espaco(6),

      // iFood Diretor
      cargoParagraph("Diretor de Operações", "iFood", "Abr 2022 – Mar 2024"),
      bullet([{
        text: "Fui responsável por operações em larga escala com budget de ",
        bold: false
      }, {
        text: "R$300MM/ano",
        bold: true
      }, {
        text: ", ~240 pessoas e S&OP executivo mensal para C-level.",
        bold: false
      }]),
      bullet([{
        text: "Conduzi planejamento integrado com modelagem em Python, SQL e Databricks, planejamento de capacidade de frota por cidade e trade-offs custo vs NDS.",
        bold: false
      }]),
      bullet([{
        text: "Ampliei cobertura de ",
        bold: false
      }, {
        text: "400 para 800 cidades",
        bold: true
      }, {
        text: ", reduzi custo logístico comparável em 3% YoY e mantive gestão de KPIs e SLA em operação de 30M pedidos/mês.",
        bold: false
      }]),
      espaco(6),

      // iFood Head
      cargoParagraph("Head de Operações", "iFood", "Nov 2018 – Mar 2022"),
      bullet([{
        text: "Fui responsável por Last Mile com equipe de 28 pessoas, cobrindo 800 cidades e 30M pedidos/mês.",
        bold: false
      }]),
      bullet([{
        text: "Estruturei torre de operações no México, simulador de nível de serviço e processo de distribuição de MPOS com critérios de elegibilidade.",
        bold: false
      }]),
      bullet([{
        text: "Gerei ",
        bold: false
      }, {
        text: "saving de R$70MM/ano",
        bold: true
      }, {
        text: " com simulador, reduzi custo de distribuição de MPOS em 80% (14 para 2 dias) e indisponibilidade de frota de 5% para 0,5%.",
        bold: false
      }]),
      espaco(6),

      // VivaReal
      cargoParagraph("Gerente de Planejamento Comercial e Operações", "VivaReal", "Mai 2015 – Dez 2017"),
      bullet([{
        text: "Fui responsável por liderança de equipes com 33 pessoas (5 lideranças diretas) em Qualidade, SDR e cadastro de imóveis, além de planejamento estratégico e precificação.",
        bold: false
      }]),
      bullet([{
        text: "Criei processo de SDR com enriquecimento de leads, distribuição em carteira e régua de onboarding especializada por jornada.",
        bold: false
      }]),
      bullet([{
        text: "Aumentei conversão SDR inbound de ",
        bold: false
      }, {
        text: "18% para 50%",
        bold: true
      }, {
        text: ", reduzi custo de vendas em 40% e recuperei R$1M em campanha de inadimplentes.",
        bold: false
      }]),
      espaco(6),

      // Trifil S&OP
      cargoParagraph("Coordenador de S&OP", "Trifil", "Jan 2010 – Set 2014"),
      bullet([{
        text: "Fui responsável por operações logísticas com S&OP corporativo, MRP, análise de capacidade produtiva e Projeto Entrega Certa com gestão de KPIs de OTIF, fill rate e acurácia de produção.",
        bold: false
      }]),
      bullet([{
        text: "Liderei projeto GGF 2014 com monitoramento de energia, gás, manutenção e embalagens, e defini política de safety stock para SKUs de maior giro.",
        bold: false
      }]),
      bullet([{
        text: "Reduzi ",
        bold: false
      }, {
        text: "R$8MM de GGF do P&L",
        bold: true
      }, {
        text: " e gerei economia de R$4,6M acima da meta em agosto, gerenciando 40K SKUs em duas marcas e todos os canais.",
        bold: false
      }]),
      espaco(6),

      // Formação
      secao("Formação"),
      espaco(3),
      bullet([{ text: "MBA Corporate Strategy — BSP Business School São Paulo (2016–2017)", bold: false }]),
      bullet([{ text: "Engenheiro Químico — Faculdades Oswaldo Cruz (2014)", bold: false }]),
      bullet([{ text: "Six Sigma Green Belt — Setec Consulting (2020)", bold: false }]),
      bullet([{ text: "Problem Solving — Ventus Consulting (2020)", bold: false }]),
      espaco(8),

      // Stack técnica
      secao("Stack técnica"),
      espaco(3),
      bullet([{ text: "Excel/VBA · SQL · Python · Databricks · Power BI · Tableau · Grafana · WMS · ERP Infor LN · Totvs Logix", bold: false }]),
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
  fs.writeFileSync("outputs/_tmp/cv_loggi_gerente_operacoes.docx", buffer);
  console.log("ok");
});
