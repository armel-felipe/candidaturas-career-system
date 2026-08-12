const pt = n => n * 2;
const fs = require('fs');
const {
  Document, Packer, Paragraph, TextRun,
  AlignmentType, TabStopType, TabStopPosition,
  ExternalHyperlink, LevelFormat, BorderStyle
} = require('docx');

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
      // Cabeçalho
      new Paragraph({
        children: [new TextRun({ text: "Felipe Armel Dias da Silva", bold: true, size: pt(12), font: "Arial" })],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [
          new ExternalHyperlink({
            children: [new TextRun({ text: "linkedin.com/in/felipearmel", size: pt(9), font: "Arial" })],
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
          new ExternalHyperlink({
            children: [new TextRun({ text: "(11) 98674-8218", size: pt(9), font: "Arial" })],
            link: "https://wa.me/5511986748218"
          })
        ],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [
          new ExternalHyperlink({
            children: [new TextRun({ text: "armelfelipe@gmail.com", size: pt(9), font: "Arial" })],
            link: "mailto:armelfelipe@gmail.com"
          })
        ],
        spacing: { after: 0 }
      }),
      espaco(8),

      // Resumo
      secao("Resumo"),
      new Paragraph({
        children: [
          new TextRun({
            text: "Executivo sênior com 20+ anos de experiência em operações, planejamento estratégico e gestão de performance em empresas de tecnologia, marketplace e indústria. No iFood, como Diretor de Operações, geri budget de R$ 300MM/ano e expandi cobertura de 400 para 800 cidades com redução de 3% YoY. Como Head de Operações, criei simulador que gerou saving de R$ 70MM/ano. Na WeHandle, reduzi custo por atendimento de R$ 4,14 para R$ 3,61 (−13%). Na VivaReal, arquitetei área de CS que escalou para 91 pessoas. Busco posição de Gerente Sênior de Planejamento e Performance.",
            size: pt(9), font: "Arial"
          })
        ],
        spacing: { after: 0 }
      }),
      espaco(8),

      // Experiências
      secao("Experiência"),
      espaco(3),

      // WeHandle
      cargoParagraph("Head de Operações", "WeHandle", "Mai 2024 – Fev 2026"),
      espaco(3),
      bullet([{ text: "Fui responsável por liderar operação de suporte com 30 pessoas, estruturando área de CX e implementando plataforma IA-first com integração em tempo real via API." }]),
      bullet([{ text: "Conduzi a migração de plataforma de atendimento, automatizei canais via WhatsApp e modelei indicadores de contato, CSat, SLA e custo por ticket." }]),
      bullet([{ text: "Reduzi custo por atendimento de R$ ", bold: false }, { text: "4,14 para R$ 3,61 (−13%)", bold: true }, { text: ", elevei CSat de 85% para 92% e melhorei SLA para 95% dos tickets." }]),
      espaco(6),

      // iFood Diretor
      cargoParagraph("Diretor de Operações", "iFood", "Abr 2022 – Mar 2024"),
      espaco(3),
      bullet([{ text: "Fui responsável por gerir operações logísticas com equipe de ~240 pessoas e budget de R$ 300MM/ano, conduzindo S&OP executivo mensal com interface C-level." }]),
      bullet([{ text: "Conduzi planejamento integrado de demanda, supply, custo e nível de serviço, balanceei capacidade de frota por cidade e mantive leitura semanal de variação vs meta." }]),
      bullet([{ text: "Ampliei cobertura de 400 para 800 cidades, reduzi custo comparável em ", bold: false }, { text: "3% YoY", bold: true }, { text: " e isolei impactos de políticas de remuneração em Full Service." }]),
      espaco(6),

      // iFood Head
      cargoParagraph("Head de Operações", "iFood", "Nov 2018 – Mar 2022"),
      espaco(3),
      bullet([{ text: "Fui responsável por liderar time de 28 pessoas em liveOps, pricing e modelagem, estruturando torre de operações no México e expandindo logística para 800 cidades." }]),
      bullet([{ text: "Criei simulador de nível de serviço em Python e SQL que gerou ", bold: false }, { text: "saving de R$ 70MM/ano", bold: true }, { text: ", monitorado em tempo real via Grafana." }]),
      bullet([{ text: "Reduzi indisponibilidade de frota de 5% para ", bold: false }, { text: "0,5%", bold: true }, { text: " nas top 6 cidades e aumentei pedidos agrupados de 12% para 25%." }]),
      espaco(6),

      // VivaReal
      cargoParagraph("Gerente de Planejamento Comercial e Operações", "VivaReal", "Mai 2015 – Dez 2017"),
      espaco(3),
      bullet([{ text: "Fui responsável por arquitetar área de CS do zero, definindo onboarding, régua de relacionamento e métricas de churn e CSat, com equipe de 33 pessoas e 5 lideranças." }]),
      bullet([{ text: "Estruturei esteira de SDR e processos de recuperação de inadimplentes, criando painéis em SQL e Excel automatizado para acompanhamento diário." }]),
      bullet([{ text: "Elevei conversão inbound de 18% para ", bold: false }, { text: "50%", bold: true }, { text: ", reduzi churn para abaixo de 3%/mês e atingi NPS de 80% com CSAT acima de 92%." }]),
      espaco(6),

      // Renault
      cargoParagraph("Gerente de Customer Success", "Renault", "Jan 2018 – Out 2018"),
      espaco(3),
      bullet([{ text: "Fui responsável por conduzir migração de operação terceirizada (BPO) de 40 PA para estrutura própria com 8 pessoas, redesenhando o funil digital de contato." }]),
      bullet([{ text: "Conduzi modelagem de dados com Excel, VBA e Power BI, estruturando qualificação objetiva e governança de SLA de retorno." }]),
      bullet([{ text: "Elevei conversão de vendas de leads de 24% para ", bold: false }, { text: "46%", bold: true }, { text: " e aprobei projeto com ROI calculado corretamente em 2 reuniões com VP de Marketing." }]),
      espaco(6),

      // Trifil
      cargoParagraph("Coordenador de S&OP", "Trifil", "Jan 2010 – Set 2014"),
      espaco(3),
      bullet([{ text: "Fui responsável por criar área de S&OP do zero, gerenciando 40K SKUs em duas marcas e todos os canais de distribuição, coordenando MRP e planejamento de outsourcing." }]),
      bullet([{ text: "Aprofundei planejamento de demanda com acurácia de previsão como KPI, defini políticas de safety stock e conduzi GGF com meta de R$ 154MM, economizando R$ 8MM." }]),
      bullet([{ text: "Reduzi GGF em ", bold: false }, { text: "R$ 8MM", bold: true }, { text: " do P&L, melhorei giro de estoque de 8 para 6 meses e criei simulador VBA para validação de cenários." }]),
      espaco(8),

      // Formação
      secao("Formação"),
      espaco(3),
      bullet([{ text: "MBA Corporate Strategy — BSP Business School São Paulo (2016–2017)" }]),
      bullet([{ text: "Engenheiro Químico — Faculdades Oswaldo Cruz (2014)" }]),
      bullet([{ text: "Técnico em Química — SENAI Mario Amato (1997)" }]),
      espaco(8),

      // Competências
      secao("Competências"),
      espaco(3),
      bullet([{ text: "Planejamento Estratégico · S&OP · OKRs · Capacity Planning · KPIs" }]),
      bullet([{ text: "Gestão de Stakeholders · Governança · Liderança de Líderes" }]),
      bullet([{ text: "Performance Operacional · Redução de Custos · Expansão Geográfica" }]),
      espaco(8),

      // Stack técnica
      secao("Stack Técnica"),
      espaco(3),
      bullet([{ text: "SQL · Python · Databricks · PySpark · Grafana · Power BI" }]),
      bullet([{ text: "Excel/VBA · Salesforce · Zendesk · ERP Infor LN" }]),
      espaco(8),

      // Idiomas
      secao("Idiomas"),
      espaco(3),
      bullet([{ text: "Português — Nativo" }]),
      bullet([{ text: "Inglês — Avançado" }]),
    ]
  }]
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync("outputs/_tmp/cv_gerente_planejamento_performance_arco.docx", buffer);
  console.log("ok");
});