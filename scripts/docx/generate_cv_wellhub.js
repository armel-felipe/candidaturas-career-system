const { Document, Packer, Paragraph, TextRun, TabStopType, TabStopPosition, AlignmentType, BorderStyle } = require('docx');
const fs = require('fs');

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

// Keywords: Business Transformation, NPS and CSAT Improvement, Dashboard Creation and Analytics,
// Cross-functional Collaboration, Data-driven Decision Making

const doc = new Document({
  creator: "Felipe Armel",
  title: "Felipe Armel - Operations Performance Manager - Wellhub",
  description: "CV for Wellhub Operations Performance Manager position",
  numbering: {
    config: [{
      reference: "bullets",
      levels: [{
        level: 0, format: "bullet", text: "\u2022",
        alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 360, hanging: 180 } } }
      }]
    }]
  },
  styles: {
    default: {
      document: { run: { font: "Arial", size: pt(9) } }
    },
    paragraphStyles: [
      { id: "Normal", name: "Normal", quickFormat: true,
        run: { font: "Arial", size: pt(9) },
        paragraph: { spacing: { after: 0 } } },
      { id: "ListParagraph", name: "List Paragraph", basedOn: "Normal", quickFormat: true,
        run: { font: "Arial", size: pt(9) },
        paragraph: { spacing: { after: 0 } } }
    ]
  },
  sections: [{
    properties: {
      page: { margin: { top: 720, right: 504, bottom: 720, left: 504 } }
    },
    children: [
      // Nome
      new Paragraph({
        children: [new TextRun({ text: "Felipe Armel Dias da Silva", bold: true, size: pt(12), font: "Arial" })],
        spacing: { after: 0 }
      }),
      // Contatos
      new Paragraph({
        children: [
          new TextRun({ text: "linkedin.com/in/felipearmel", size: pt(9), font: "Arial", color: "0000FF" }),
          new TextRun({ text: "    ", size: pt(9), font: "Arial" }),
          new TextRun({ text: "São Paulo, SP", size: pt(9), font: "Arial" }),
          new TextRun({ text: "    ", size: pt(9), font: "Arial" }),
          new TextRun({ text: "(11) 98674-8218", size: pt(9), font: "Arial", color: "0000FF" }),
          new TextRun({ text: "    ", size: pt(9), font: "Arial" }),
          new TextRun({ text: "armelfelipe@gmail.com", size: pt(9), font: "Arial", color: "0000FF" })
        ],
        spacing: { after: pt(4) }
      }),

      espaco(3),

      // Resumo — max 480
      secao("Resumo"),
      new Paragraph({
        children: [
          new TextRun({ text: "Executivo sênior com 20 anos em operações, Customer Success e transformação de processos. Como Head de Operações na WeHandle, geri time de 30 pessoas e budget de custos com resultado de ", size: pt(9), font: "Arial" }),
          new TextRun({ text: "CSAT de 85% para 92% e SLA em 95%", bold: true, size: pt(9), font: "Arial" }),
          new TextRun({ text: ". No iFood como Diretor de Operações, geri R$300MM/ano e 240 pessoas escalando logística de 400 para 800 cidades. Minha trajetória combina gestão de métricas operacionais (NPS, CSAT), criação de dashboards analíticos e colaboração multifuncional — sempre com foco em negócio e resultado. Busco posição de Operations Performance Manager em empresa de tecnologia.", size: pt(9), font: "Arial" })
        ],
        spacing: { after: pt(4) }
      }),

      espaco(6),

      // Experiência — WeHandle
      secao("Experiência"),
      cargoParagraph("Head de Operações", "WeHandle", "mai/2024 — fev/2026"),
      bullet([{ text: "Fui responsável pela operação de suporte com time de 30 pessoas, conduzindo ", bold: false }, { text: "Business Transformation", bold: true }, { text: " IA first com duas migrações de plataforma, chatbot e canal WhatsApp — resultado: custo por atendimento de R$1,04 para R$0,56 e CSAT de 85% para 92%.", bold: false }]),
      bullet([{ text: "Desenvolvi ", bold: false }, { text: "Dashboard Creation and Analytics", bold: true }, { text: " conectando via API três plataformas de atendimento (Movidesk, CloudHumans, Zendesk) — dados disponíveis em tempo real sem dependência da área de dados, com redução de 60% no backlog e SLA de execução de 67% para 85%.", bold: false }]),
      bullet([{ text: "Conduzi gestão de capacidade e workload com SLA em 95% dos tickets e ", bold: false }, { text: "NPS and CSAT Improvement", bold: true }, { text: " medido mensalmente — interface semanal com time de produto para priorização de roadmap de bugs e melhorias (VoC).", bold: false }]),

      espaco(6),

      // iFood Diretor
      cargoParagraph("Diretor de Operações", "iFood", "abr/2022 — mar/2024"),
      bullet([{ text: "Fui responsável pelo P&L de custo das entregas com budget de R$300MM/ano e 240 pessoas, fazendo leitura semanal de DRE e análise de variação vs meta — ", bold: false }, { text: "Data-driven Decision Making", bold: true }, { text: " aplicado a trade-offs operacionais e financeiros.", bold: false }]),
      bullet([{ text: "Conduzi o rito executivo mensal de S&OP conectando marketing, promoções, frota e operação em processo único — ", bold: false }, { text: "Cross-functional Collaboration", bold: true }, { text: " com C-level para direcionais de curto prazo e cenários de budget.", bold: false }]),
      bullet([{ text: "Melhorei eficiência logística com redução de 3% YoY em custo comparável e expandi cobertura de 400 para 800 cidades.", bold: false }]),

      espaco(6),

      // iFood Head
      cargoParagraph("Head de Operações", "iFood", "nov/2018 — mar/2022"),
      bullet([{ text: "Construí torre de operações no México com métricas em tempo real via Grafana — ", bold: false }, { text: "Dashboard Creation and Analytics", bold: true }, { text: " proprietária que identificou correlação entre saturação logística e cancelamentos, alcançando redução de 60% no cancelamento.", bold: false }]),
      bullet([{ text: "Desenvolvi simulador de ", bold: false }, { text: "Capacity Planning", bold: true }, { text: " de frota com Python e SQL que manteve nível de serviço com saving de R$70M/ano — testes controlados de elasticidade de preço por zona.", bold: false }]),
      bullet([{ text: "Conduzi ", bold: false }, { text: "Business Transformation", bold: true }, { text: " logística escalando de 800K para 30M pedidos/mês com time de 28 pessoas em liveOps, pricing e modelagem de dados.", bold: false }]),

      espaco(6),

      // VivaReal
      cargoParagraph("Gerente de Planejamento Comercial e Operações", "VivaReal", "mai/2015 — dez/2017"),
      bullet([{ text: "Arquitetei área de CS que escalou para 91 pessoas e atingiu NPS 80%, CSAT acima de 92% e churn abaixo de 3%/mês — ação orientada a ", bold: false }, { text: "NPS and CSAT Improvement", bold: true }, { text: " e retenção de clientes.", bold: false }]),
      bullet([{ text: "Desenvolvi dashboards SQL e Excel automatizado que reduziram tempo de relatório de 4h para 14min — ", bold: false }, { text: "Data-driven Decision Making", bold: true }, { text: " disponível sem dependência de outras áreas.", bold: false }]),
      bullet([{ text: "Conduzi interface multifuncional com CFO, time comercial e time de produto — ", bold: false }, { text: "Cross-functional Collaboration", bold: true }, { text: " para alinhamento de roadmap e decisões de pricing e expansão.", bold: false }]),

      espaco(8),

      // Formação
      secao("Formação"),
      new Paragraph({
        children: [
          new TextRun({ text: "MBA Corporate Strategy — Business School São Paulo (2017)", bold: true, size: pt(9), font: "Arial" })
        ],
        spacing: { after: pt(2) }
      }),
      new Paragraph({
        children: [
          new TextRun({ text: "Engenharia Química — Faculdades Oswaldo Cruz (2014)", bold: true, size: pt(9), font: "Arial" })
        ],
        spacing: { after: pt(2) }
      }),

      espaco(6),

      // Stack técnica
      secao("Stack técnica"),
      new Paragraph({
        children: [
          new TextRun({ text: "Python · SQL · Databricks · Grafana · Tableau · Excel VBA · Salesforce · Zendesk", size: pt(9), font: "Arial" })
        ],
        spacing: { after: 0 }
      }),

      espaco(6),

      // Idiomas
      secao("Idiomas"),
      new Paragraph({
        numbering: { reference: "bullets", level: 0 },
        children: [new TextRun({ text: "Português — Nativo", size: pt(9), font: "Arial" })],
        spacing: { after: pt(2) }
      }),
      new Paragraph({
        numbering: { reference: "bullets", level: 0 },
        children: [new TextRun({ text: "Inglês — Avançado", size: pt(9), font: "Arial" })],
        spacing: { after: 0 }
      })
    ]
  }]
});

const outputPath = "outputs/felipe_armel_cv_operations_performance_manager_wellhub.docx";
Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync(outputPath, buffer);
  console.log("OK:" + outputPath);
}).catch(err => {
  console.error("ERROR:" + err.message);
  process.exit(1);
});