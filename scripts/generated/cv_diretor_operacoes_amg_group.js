const docx = require("docx");
const fs = require("fs");
const {
  Document, Paragraph, TextRun, ExternalHyperlink,
  TabStopType, TabStopPosition, AlignmentType,
  BorderStyle, LevelFormat, Packer
} = docx;

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
    children: [new TextRun({ text: "", size: pt(ptSize || 6), font: "Arial" })],
    spacing: { after: 0 }
  });
}

function cargoParagraph(cargo, empresa, periodo) {
  return new Paragraph({
    tabStops: [{ type: TabStopType.RIGHT, position: TabStopPosition.MAX }],
    children: [
      new TextRun({ text: cargo + " \u2014 " + empresa, bold: true, size: pt(9), font: "Arial" }),
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

function linkParagraph(label, url) {
  return new Paragraph({
    children: [
      new ExternalHyperlink({
        children: [new TextRun({ text: label, style: "Hyperlink", size: pt(9), font: "Arial" })],
        link: url
      })
    ],
    spacing: { after: 0 }
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
      // HEADER
      new Paragraph({
        children: [new TextRun({ text: "Felipe Armel Dias da Silva", bold: true, size: pt(12), font: "Arial" })],
        spacing: { after: 0 }
      }),
      linkParagraph("linkedin.com/in/felipearmel", "https://linkedin.com/in/felipearmel"),
      linkParagraph("wa.me/5511986748218", "https://wa.me/5511986748218"),
      linkParagraph("armelfelipe@gmail.com", "mailto:armelfelipe@gmail.com"),
      new Paragraph({
        children: [new TextRun({ text: "São Paulo, SP", size: pt(9), font: "Arial" })],
        spacing: { after: 0 }
      }),

      espaco(8),

      // RESUMO
      secao("Resumo"),
      new Paragraph({
        children: [new TextRun({
          text: "Diretor de Operações com experiência em operações logísticas de larga escala, liderança de equipes de até 240 pessoas, elaboração de orçamentos e gestão de budget de R$300MM/ano. Como Diretor de Operações no iFood, reduzi custos em 3% YoY e ampliei cobertura de 400 para 800 cidades. Uso business intelligence (Python, SQL, Databricks) como alavanca de decisão. Busco posição de Diretor de Operações.",
          size: pt(9), font: "Arial"
        })],
        spacing: { after: 0 }
      }),

      espaco(8),

      // EXPERIENCIA
      secao("Experiência"),

      espaco(3),

      // 1. wehandle
      cargoParagraph("Head de Operações", "WeHandle", "Mai 2024 \u2013 Fev 2026"),
      bullet([
        { text: "Fui responsável por liderar a operação de suporte ao cliente com equipe de 30 pessoas, reestruturando processos, automação e redução de custos com impacto de ", bold: false },
        { text: "15% na margem bruta", bold: true },
        { text: " da companhia", bold: false }
      ]),
      bullet([
        { text: "Implantei canal WhatsApp de atendimento, automação com IA via Zendesk e dashboards de business intelligence conectados ao datalake via API", bold: false }
      ]),
      bullet([
        { text: "Reduzi o custo por atendimento de ", bold: false },
        { text: "R$4,14 para R$3,61 (\u221213%)", bold: true },
        { text: ", elevei o CSAT de 85% para 92% e melhorei o SLA para 95% dos tickets", bold: false }
      ]),

      espaco(6),

      // 2. iFood Diretor
      cargoParagraph("Diretor de Operações", "iFood", "Abr 2022 \u2013 Mar 2024"),
      bullet([
        { text: "Fui responsável pelas operações logísticas com equipe de ~240 pessoas, elaboração de orçamentos e budget de ", bold: false },
        { text: "R$300MM/ano", bold: true },
        { text: ", gerindo o P&L de custo das entregas", bold: false }
      ]),
      bullet([
        { text: "Conduzi o S&OP executivo mensal com Python, SQL e Databricks, conectando demanda, frota, custo e cenários para decisão do C-level", bold: false }
      ]),
      bullet([
        { text: "Ampliei cobertura logística de ", bold: false },
        { text: "400 para 800 cidades", bold: true },
        { text: " e reduzi custo comparável em 3% YoY mantendo SLA em 30M pedidos/m\u00eas", bold: false }
      ]),

      espaco(6),

      // 3. iFood Head
      cargoParagraph("Head de Operações", "iFood", "Nov 2018 \u2013 Mar 2022"),
      bullet([
        { text: "Fui responsável por estruturar liveOps, planejamento de frota e pricing operacional com time de 28 pessoas", bold: false }
      ]),
      bullet([
        { text: "Usei business intelligence com dashboards em tempo real no Grafana e criei simulador de n\u00edvel de servi\u00e7o com SQL, Python e Databricks", bold: false }
      ]),
      bullet([
        { text: "Gerei saving de ", bold: false },
        { text: "R$70M/ano", bold: true },
        { text: " com simulador de frota e reduzi cancelamentos no M\u00e9xico em 60% ajustando raios de entrega", bold: false }
      ]),

      espaco(6),

      // 4. Renault
      cargoParagraph("Gerente de Customer Success", "Renault do Brasil", "Jan 2018 \u2013 Out 2018"),
      bullet([
        { text: "Fui responsável por reestruturar opera\u00e7\u00e3o de CS, migrando de BPO terceirizado para estrutura pr\u00f3pria com 8 pessoas", bold: false }
      ]),
      bullet([
        { text: "Redesenhei fluxo digital com discadores e metodologia de qualifica\u00e7\u00e3o baseada em dados", bold: false }
      ]),
      bullet([
        { text: "Elevei convers\u00e3o de leads de ", bold: false },
        { text: "24% para 46%", bold: true },
        { text: " em dois dias de opera\u00e7\u00e3o reestruturada", bold: false }
      ]),

      espaco(6),

      // 5. VivaReal
      cargoParagraph("Gerente de Planejamento Comercial e Opera\u00e7\u00f5es", "VivaReal", "Mai 2015 \u2013 Dez 2017"),
      bullet([
        { text: "Fui responsável pelo planejamento estrat\u00e9gico e opera\u00e7\u00f5es de BU com 33 pessoas, cobrindo SDR, Qualidade e Cadastro de im\u00f3veis", bold: false }
      ]),
      bullet([
        { text: "Estruturei r\u00e9gua de onboarding e processo de SDR, atuando como arquiteto da \u00e1rea de CS que escalou para 91 pessoas", bold: false }
      ]),
      bullet([
        { text: "Alcancei churn abaixo de 3%/m\u00eas, NPS de 80% e convers\u00e3o inbound de ", bold: false },
        { text: "18% para 50%", bold: true },
        { text: " com redu\u00e7\u00e3o de 40% no custo de vendas", bold: false }
      ]),

      espaco(6),

      // 6. Trifil S&OP
      cargoParagraph("Coordenador de S&OP", "Scalina (Trifil)", "Jan 2010 \u2013 Set 2014"),
      bullet([
        { text: "Fui responsável por criar a \u00e1rea de S&OP do zero, gerenciando 40K SKUs e coordenando planejamento de demanda, supply e capacidade", bold: false }
      ]),
      bullet([
        { text: "Implantei ciclo de melhoria cont\u00ednua com PDCA, KPIs de OTIF e fill rate, al\u00e9m de simulador de S&OP em Excel/VBA", bold: false }
      ]),
      bullet([
        { text: "Reduzi ", bold: false },
        { text: "R$8M de GGF", bold: true },
        { text: " do P&L com projeto de redu\u00e7\u00e3o de custos e mantive a meta com economia de R$4,6M acima do or\u00e7amento", bold: false }
      ]),

      espaco(8),

      // FORMACAO
      secao("Forma\u00e7\u00e3o"),
      bullet([{ text: "MBA Corporate Strategy \u2014 BSP Business School S\u00e3o Paulo (2017)", bold: false }]),
      bullet([{ text: "Engenharia Qu\u00edmica \u2014 Faculdades Oswaldo Cruz (2014)", bold: false }]),
      bullet([{ text: "Six Sigma Green Belt \u2014 Setec Consulting (2020)", bold: false }]),
      bullet([{ text: "Programa ILead (lideran\u00e7a para l\u00edderes de l\u00edderes) \u2014 Funda\u00e7\u00e3o Dom Cabral (2021)", bold: false }]),

      espaco(8),

      // STACK TECNICA
      secao("Stack t\u00e9cnica"),
      new Paragraph({
        children: [new TextRun({
          text: "Python \u00b7 SQL \u00b7 Databricks \u00b7 Tableau \u00b7 Grafana \u00b7 Metabase \u00b7 Excel/VBA \u00b7 Zendesk \u00b7 Salesforce \u00b7 ERP Infor LN",
          size: pt(9), font: "Arial"
        })],
        spacing: { after: 0 }
      }),

      espaco(8),

      // IDIOMAS
      secao("Idiomas"),
      bullet([{ text: "Portugu\u00eas \u2014 Nativo", bold: false }]),
      bullet([{ text: "Ingl\u00eas \u2014 Avan\u00e7ado", bold: false }])
    ]
  }]
});

Packer.toBuffer(doc).then(buffer => {
  const outPath = "/Users/mac/llm server/projetos/candidaturas/outputs/_tmp/cv_diretor_operacoes_amg_group.docx";
  fs.writeFileSync(outPath, buffer);
  console.log("ok");
});
