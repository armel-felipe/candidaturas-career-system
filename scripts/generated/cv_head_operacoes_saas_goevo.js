const { Document, Packer, Paragraph, TextRun, AlignmentType, TabStopType, TabStopPosition, LevelFormat, convertInchesToTwip, ExternalHyperlink, BorderStyle } = require("docx");
const fs = require("fs");

const pt = n => n * 2; // half-points

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

function paragrafo(text) {
  return new Paragraph({
    children: [new TextRun({ text, size: pt(9), font: "Arial" })],
    spacing: { after: 0 }
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
        style: {
          paragraph: {
            indent: { left: convertInchesToTwip(0.25), hanging: convertInchesToTwip(0.125) }
          }
        }
      }]
    }]
  },
  styles: {
    default: {
      document: {
        run: { font: "Arial", size: pt(9) }
      }
    },
    paragraphStyles: [
      {
        id: "Normal",
        name: "Normal",
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
        children: [new TextRun({ text: "Felipe Armel Dias da Silva", bold: true, size: pt(12), font: "Arial" })],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [
          new ExternalHyperlink({
            children: [new TextRun({ text: "linkedin.com/in/felipearmel", size: pt(9), font: "Arial", style: "Hyperlink" })],
            link: "https://linkedin.com/in/felipearmel"
          })
        ],
        spacing: { after: 0 }
      }),
      paragrafo("São Paulo, SP"),
      new Paragraph({
        children: [
          new ExternalHyperlink({
            children: [new TextRun({ text: "(11) 98674-8218", size: pt(9), font: "Arial", style: "Hyperlink" })],
            link: "https://wa.me/5511986748218"
          })
        ],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [
          new ExternalHyperlink({
            children: [new TextRun({ text: "armelfelipe@gmail.com", size: pt(9), font: "Arial", style: "Hyperlink" })],
            link: "mailto:armelfelipe@gmail.com"
          })
        ],
        spacing: { after: 0 }
      }),

      espaco(8),

      // Resumo
      secao("Resumo"),
      espaco(3),
      paragrafo("Executivo Sênior com formação em Engenharia Química e MBA em Corporate Strategy (BSP). Na WeHandle, como Head de Operações em SaaS B2B, impactei 15% na margem bruta estruturando operação escalável. No iFood, como Diretor de Operações, ampliei cobertura de 400 para 800 cidades com budget de R$300MM/ano. Busco posição de Head de Operações SaaS em ambiente de construção, onde autonomia e impacto percentual são maiores."),

      espaco(8),

      // Experiência
      secao("Experiência"),
      espaco(3),

      // WeHandle
      cargoParagraph("Head de Operações", "WeHandle", "Mai 2024 – Fev 2026"),
      bullet([
        { text: "Fui responsável por estruturar operação escalável em SaaS B2B com time de 30 pessoas em atendimento e Customer Success, criando área de CX e conduzindo 2 migrações de plataforma IA first (implantação Software Implementation) para alcançar excelência operacional." }
      ]),
      bullet([
        { text: "Apliquei integração de sistemas (System Integration) conectando 3 plataformas via API com datalake, otimização de processos com board no ClickUp para alinhamento com time de produto, e gestão de mudança implantando canal WhatsApp." }
      ]),
      bullet([
        { text: "Reduzi custo por atendimento de " },
        { text: "R$4,14 para R$3,61 (−13%)", bold: true },
        { text: ", elevei CSAT de 85% para " },
        { text: "92%", bold: true },
        { text: ", diminuí TME de 20 para " },
        { text: "8 minutos", bold: true },
        { text: ", e gerei " },
        { text: "impacto de 15% na margem bruta", bold: true },
        { text: " via automação." }
      ]),

      espaco(6),

      // iFood Diretor
      cargoParagraph("Diretor de Operações", "iFood", "Abr 2022 – Mar 2024"),
      bullet([
        { text: "Fui responsável pela linha de custo das entregas do P&L com budget de " },
        { text: "R$300MM/ano", bold: true },
        { text: " exercendo Cross-functional Leadership de equipe de " },
        { text: "~240 pessoas", bold: true },
        { text: " em FieldOps, Meios de Pagamento e Novos Negócios, conduzindo gestão de stakeholders em S&OP executivo mensal com C-level consolidando demanda, supply, custo logístico, NDS e cenários." }
      ]),
      bullet([
        { text: "Liderei planejamento integrado conectando marketing, produto, frota e operação via decisões orientadas a dados, modelagem em Python, SQL e Databricks, e capacity planning por cidade com escalabilidade para 800 cidades." }
      ]),
      bullet([
        { text: "Ampliei cobertura de " },
        { text: "400 para 800 cidades", bold: true },
        { text: ", reduzi custo comparável em " },
        { text: "3% YoY", bold: true },
        { text: " (2023 vs 2022), aumentei entregas agrupadas de 12% para " },
        { text: "25%", bold: true },
        { text: ", e mantive SLA de " },
        { text: "30M pedidos/mês", bold: true },
        { text: " com gerenciamento de operações integrado." }
      ]),

      espaco(6),

      // iFood Head
      cargoParagraph("Head de Operações", "iFood", "Nov 2018 – Mar 2022"),
      bullet([
        { text: "Fui responsável por operações logísticas com equipe de 28 pessoas em liveOps, regionalOps, pricing, modelagem de dados e planejamento de frota, criando métricas em tempo real no Grafana correlacionando saturação logística, NDS e ganhos dos entregadores." }
      ]),
      bullet([
        { text: "Estruturei capacity planning de frota com simulador proprietário de nível de serviço, implantei MPOS com critérios de elegibilidade protegendo risco de fraude, e conduzi testes controlados de elasticidade de preço por zona." }
      ]),
      bullet([
        { text: "Gerei " },
        { text: "saving de R$70MM/ano", bold: true },
        { text: " com simulador mantendo SLA, distribuí MPOS em " },
        { text: "352 cidades", bold: true },
        { text: " com zero perda financeira, e reduzi indisponibilidade de frota de 5% para " },
        { text: "1%", bold: true },
        { text: " (top 6 cidades: 5,4% para " },
        { text: "0,5%", bold: true },
        { text: ")." }
      ]),

      espaco(6),

      // VivaReal
      cargoParagraph("Gerente de Planejamento Comercial e Operações", "VivaReal", "Mai 2015 – Dez 2017"),
      bullet([
        { text: "Fui responsável por planejamento estratégico, operações de qualidade, SDR e cadastro de imóveis com clientes corporativos B2B do setor imobiliário, 33 pessoas e 5 lideranças diretas, projetando área de Customer Success do zero que escalou para " },
        { text: "91 pessoas", bold: true },
        { text: " sob gestão de outros — fui arquiteto da área, não gestor." }
      ]),
      bullet([
        { text: "Conduzi alinhamento com time de produto em reuniões semanais para priorização de roadmap, estruturei onboarding de clientes com régua especializada por fase da jornada, e implantei telefonia digital e recebimento por cartão." }
      ]),
      bullet([
        { text: "Elevei conversão SDR inbound de 18% para " },
        { text: "50% (−40% custo de vendas)", bold: true },
        { text: ", recuperei " },
        { text: "R$1M", bold: true },
        { text: " com campanha de inadimplentes, e alcancei " },
        { text: "NPS 80%", bold: true },
        { text: ", " },
        { text: "CSAT 92%", bold: true },
        { text: " e " },
        { text: "churn <3%/mês", bold: true },
        { text: " após estruturação de CS." }
      ]),

      espaco(8),

      // Formação
      secao("Formação"),
      espaco(3),
      bullet([{ text: "MBA Corporate Strategy — BSP Business School São Paulo (2016–2017)" }]),
      bullet([{ text: "Engenheiro Químico — Faculdades Oswaldo Cruz (2014)" }]),
      bullet([{ text: "Six Sigma Green Belt — Setec Consulting (2020)" }]),

      espaco(8),

      // Stack Técnica
      secao("Stack Técnica"),
      espaco(3),
      paragrafo("SQL · Python · Databricks · Grafana · Excel/VBA · Power BI · Salesforce · Zendesk · ERP Infor LN · ClickUp"),

      espaco(8),

      // Idiomas
      secao("Idiomas"),
      espaco(3),
      bullet([{ text: "Português — Nativo" }]),
      bullet([{ text: "Inglês — Avançado" }])
    ]
  }]
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync("outputs/_tmp/cv_head_operacoes_saas_goevo.docx", buffer);
  console.log("ok");
}).catch(err => {
  console.error("Erro ao gerar DOCX:", err);
  process.exit(1);
});
