const {
  Document, Packer, Paragraph, TextRun, ExternalHyperlink,
  TabStopType, TabStopPosition, BorderStyle, AlignmentType,
  LevelFormat, Numbering
} = require("docx");
const fs = require("fs");
const path = require("path");

const pt = n => n * 2; // half-points — NUNCA n * 20

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
      // Header
      new Paragraph({
        children: [new TextRun({ text: "Felipe Armel Dias da Silva", bold: true, size: pt(12), font: "Arial" })],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [
          new ExternalHyperlink({
            children: [new TextRun({ text: "linkedin.com/in/felipearmel", style: "Hyperlink", size: pt(9), font: "Arial" })],
            link: "https://linkedin.com/in/felipearmel"
          })
        ],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [new TextRun({ text: "São Paulo, SP", size: pt(9), font: "Arial" })],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [
          new ExternalHyperlink({
            children: [new TextRun({ text: "(11) 98674-8218", style: "Hyperlink", size: pt(9), font: "Arial" })],
            link: "https://wa.me/5511986748218"
          })
        ],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [
          new ExternalHyperlink({
            children: [new TextRun({ text: "armelfelipe@gmail.com", style: "Hyperlink", size: pt(9), font: "Arial" })],
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
          new TextRun({ text: "Engenheiro Químico com MBA em Corporate Strategy pela BSP, trajetória executiva de 7+ anos em Customer Service, Customer Success e operações de atendimento. No WeHandle, liderei a operação de suporte com time de 30 pessoas, elevando CSAT de 85% para 92% e impactando a margem bruta em +15%. No iFood, como Diretor de Operações, geri budget de R$300MM/ano com gestão de equipes de ~240 pessoas. Busco posição de Gerente de Customer Service.", size: pt(9), font: "Arial" })
        ],
        spacing: { after: 0 }
      }),

      espaco(8),

      // Experiência
      secao("Experiência"),

      // WeHandle
      espaco(3),
      cargoParagraph("Head de Operações", "WeHandle", "Mai 2024 – Fev 2026"),
      bullet([
        { text: "Fui responsável por liderar a operação de Customer Service com time de 30 pessoas, definindo estratégia de canais, indicadores de desempenho, gestão de equipes e orçamento de custos da área.", bold: false }
      ]),
      bullet([
        { text: "Liderei a implantação de automação com IA e canal WhatsApp, integrei dados via API ao datalake; utilizei CRM (Zendesk e Salesforce) como plataformas centrais de atendimento.", bold: false }
      ]),
      bullet([
        { text: "Elevei o CSAT de 85% para 92%, mantive ", bold: false },
        { text: "SLA em 95%", bold: true },
        { text: " dos tickets, reduzi o TME de 20 para 8 minutos e gerei impacto de +15% na margem bruta.", bold: false }
      ]),

      espaco(6),

      // iFood Diretor
      cargoParagraph("Diretor de Operações", "iFood", "Abr 2022 – Mar 2024"),
      bullet([
        { text: "Fui responsável pelas operações logísticas com equipe de ~", bold: false },
        { text: "240 pessoas", bold: true },
        { text: " e gestão de budget de R$300MM/ano com reporte direto ao C-level.", bold: false }
      ]),
      bullet([
        { text: "Conduzi o S&OP executivo mensal conectando marketing, frota e supply, com modelagem em Python, SQL e Databricks.", bold: false }
      ]),
      bullet([
        { text: "Ampliei cobertura de 400 para ", bold: false },
        { text: "800 cidades", bold: true },
        { text: ", reduzi custo logístico comparável em 3% YoY e elevei agrupamento de pedidos de 12% para 25%.", bold: false }
      ]),

      espaco(6),

      // iFood Head
      cargoParagraph("Head de Operações", "iFood", "Nov 2018 – Mar 2022"),
      bullet([
        { text: "Fui responsável por estruturar o planejamento de frota e operações em tempo real com equipe de 28 pessoas em liveOps, pricing e modelagem.", bold: false }
      ]),
      bullet([
        { text: "Criei simulador de nível de serviço no Grafana e ferramentas de restrição de raio para equilibrar oferta de frota com demanda por região.", bold: false }
      ]),
      bullet([
        { text: "Gerei ", bold: false },
        { text: "saving de R$70MM/ano", bold: true },
        { text: " com o simulador, reduzi lead time de distribuição de 14 para 2 dias e escalei distribuição de MPOS para 352 cidades.", bold: false }
      ]),

      espaco(6),

      // Renault
      cargoParagraph("Gerente de Customer Success", "Renault do Brasil", "Jan 2018 – Out 2018"),
      bullet([
        { text: "Fui responsável por gerenciar a operação de Customer Success, conduzindo a transição de BPO terceirizado (40 PAS) para time próprio de 8 pessoas.", bold: false }
      ]),
      bullet([
        { text: "Redesenhei o fluxo digital de contato com consumidores e estruturei metodologia de qualificação baseada em dados com Excel e Power BI.", bold: false }
      ]),
      bullet([
        { text: "Elevei a conversão de vendas de leads de ", bold: false },
        { text: "24% para 46%", bold: true },
        { text: " e estabilizei a operação com governança de SLA de retorno em tempo real.", bold: false }
      ]),

      espaco(6),

      // VivaReal
      cargoParagraph("Gerente de Planejamento Comercial e Operações", "VivaReal", "Mai 2015 – Dez 2017"),
      bullet([
        { text: "Fui arquiteto da área de Customer Service — desenhei processos, régua de onboarding e contratei liderança; área escalou para ", bold: false },
        { text: "91 pessoas", bold: true },
        { text: " sob gestão direta de outros.", bold: false }
      ]),
      bullet([
        { text: "Estruturei a operação de SDR com processo de contato em 3 dias para maximizar conversão, utilizando SQL e dashboards para decisão diária.", bold: false }
      ]),
      bullet([
        { text: "Alcancei ", bold: false },
        { text: "NPS de 80%", bold: true },
        { text: " e CSAT acima de 92%, elevei conversão de vendas inbound de 18% para 50% com redução de 40% no custo de vendas.", bold: false }
      ]),

      espaco(6),

      // Trifil
      cargoParagraph("Coordenador de S&OP", "Trifil (Scalina)", "Jan 2010 – Set 2014"),
      bullet([
        { text: "Fui responsável pelo planejamento integrado da companhia, gerenciando o S&OP executivo, MRP e 40K SKUs em dois canais de distribuição.", bold: false }
      ]),
      bullet([
        { text: "Modelei simuladores em Excel/VBA para validação do MRP e implantei sistema de melhoria contínua com GPD/PDCA em toda área produtiva.", bold: false }
      ]),
      bullet([
        { text: "Reduzi ", bold: false },
        { text: "R$8MM de GGF", bold: true },
        { text: " do P&L anual, melhorei giro de estoque de 8 para 6 meses e otimizei políticas de estoque de segurança.", bold: false }
      ]),

      espaco(8),

      // Formação
      secao("Formação"),
      bullet([{ text: "MBA Corporate Strategy — BSP Business School São Paulo (2017)", bold: false }]),
      bullet([{ text: "Engenharia Química — Faculdades Oswaldo Cruz (2014)", bold: false }]),
      bullet([{ text: "Six Sigma Green Belt — Setec Consulting (2020)", bold: false }]),
      bullet([{ text: "ILead Liderança para Líder de Líderes — Fundação Dom Cabral (2021)", bold: false }]),

      espaco(8),

      // Stack Técnica
      secao("Stack técnica"),
      new Paragraph({
        children: [new TextRun({ text: "SQL · Python · Databricks · Grafana · Zendesk · Salesforce · Power BI · Metabase · Excel avançado/VBA · ERP LN Infor", size: pt(9), font: "Arial" })],
        spacing: { after: 0 }
      }),

      espaco(8),

      // Idiomas
      secao("Idiomas"),
      bullet([{ text: "Português — Nativo", bold: false }]),
      bullet([{ text: "Inglês — Avançado", bold: false }])
    ]
  }]
});

Packer.toBuffer(doc).then(buffer => {
  const workspace = path.resolve(__dirname, "..", "..");
  const outPath = path.join(workspace, "outputs", "_tmp", "cv_customer_service_book_fair.docx");
  fs.writeFileSync(outPath, buffer);
  console.log("ok");
});
