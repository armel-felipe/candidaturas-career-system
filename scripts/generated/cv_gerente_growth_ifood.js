const fs = require("fs");
const path = require("path");
const {
  AlignmentType,
  BorderStyle,
  Document,
  ExternalHyperlink,
  LevelFormat,
  Packer,
  Paragraph,
  TabStopPosition,
  TabStopType,
  TextRun,
} = require("docx");

const pt = n => n * 2;

const workspace = process.env.CAREER_WORKSPACE || process.cwd();
const tmpDir = path.join(workspace, "outputs", "_tmp");
const outputPath = path.join(tmpDir, "felipe_armel_cv_gerente_growth_ifood.docx");

function secao(text) {
  return new Paragraph({
    children: [new TextRun({ text, size: pt(12), font: "Arial" })],
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "000000", space: 1 } },
    spacing: { before: pt(6), after: pt(3) },
  });
}

function espaco(ptSize = 6) {
  return new Paragraph({
    children: [new TextRun({ text: "", size: pt(ptSize), font: "Arial" })],
    spacing: { after: 0 },
  });
}

function cargoParagraph(cargo, empresa, periodo) {
  return new Paragraph({
    tabStops: [{ type: TabStopType.RIGHT, position: TabStopPosition.MAX }],
    children: [
      new TextRun({ text: `${cargo} — ${empresa}`, bold: true, size: pt(9), font: "Arial" }),
      new TextRun({ text: "\t" + periodo, size: pt(9), font: "Arial" }),
    ],
    spacing: { after: 0 },
  });
}

function bullet(runs) {
  return new Paragraph({
    numbering: { reference: "bullets", level: 0 },
    children: runs.map(run => new TextRun({
      text: run.text,
      bold: run.bold || false,
      size: pt(9),
      font: "Arial",
    })),
    spacing: { after: pt(2) },
  });
}

function paragraph(text) {
  return new Paragraph({
    children: [new TextRun({ text, size: pt(9), font: "Arial" })],
    spacing: { after: 0 },
  });
}

function hyperlink(text, url) {
  return new Paragraph({
    children: [new ExternalHyperlink({
      link: url,
      children: [new TextRun({ text, style: "Hyperlink", size: pt(9), font: "Arial" })],
    })],
    spacing: { after: 0 },
  });
}

async function main() {
  fs.mkdirSync(tmpDir, { recursive: true });

  const doc = new Document({
    styles: {
      default: { document: { run: { font: "Arial", size: pt(9) } } },
      paragraphStyles: [
        {
          id: "Normal",
          name: "Normal",
          quickFormat: true,
          run: { font: "Arial", size: pt(9) },
          paragraph: { spacing: { after: 0 } },
        },
        {
          id: "ListParagraph",
          name: "List Paragraph",
          basedOn: "Normal",
          quickFormat: true,
          run: { font: "Arial", size: pt(9) },
          paragraph: { spacing: { after: 0 } },
        },
      ],
    },
    numbering: {
      config: [{
        reference: "bullets",
        levels: [{
          level: 0,
          format: LevelFormat.BULLET,
          text: "\u2022",
          alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 360, hanging: 180 } } },
        }],
      }],
    },
    sections: [{
      properties: {
        page: {
          size: { width: 11906, height: 16838 },
          margin: { top: 720, right: 504, bottom: 720, left: 504 },
        },
      },
      children: [
        paragraph("Felipe Armel Dias da Silva"),
        hyperlink("linkedin.com/in/felipearmel", "https://linkedin.com/in/felipearmel"),
        paragraph("São Paulo, SP"),
        hyperlink("(11) 98674-8218", "https://wa.me/5511986748218"),
        hyperlink("armelfelipe@gmail.com", "mailto:armelfelipe@gmail.com"),
        espaco(8),

        secao("Resumo"),
        paragraph("Executivo sênior em operações, dados e automação, com atuação em marketplace, growth operacional e CX. Atuo em tomada de decisão orientada por dados, liderança transversal e escala operacional. No iFood, como Diretor de Operações, liderei 240 pessoas, budget de R$300MM/ano e expansão de 400 para 800 cidades. Na wehandle, reduzi custo por atendimento em 13% com automação e IA."),
        espaco(8),

        secao("Experiência"),

        cargoParagraph("Head de Operações", "wehandle", "Mai 2024 – Fev 2026"),
        bullet([{ text: "Fui responsável pela operação de suporte a clientes com 30 pessoas, reestruturando atendimento, automação e backoffice com foco em excelência operacional e IA aplicada à operação." }]),
        bullet([{ text: "Liderei duas migrações de plataforma e integrei Movidesk, CloudHumans, Zendesk e datalake via API para dar visibilidade em tempo real à operação e acelerar a automação da decisão operacional." }]),
        bullet([{ text: "Implementei WhatsApp, chatbot e IA humanizada, elevando produtividade em 25% e reduzindo o custo no canal de R$1,04 para R$0,56." }]),
        bullet([{ text: "Reduzi o custo por atendimento de R$4,14 para R$3,61, baixei o TME de 20 para 8 minutos e elevei o CSAT de 85% para 92%." }]),
        espaco(6),

        cargoParagraph("Diretor de Operações", "iFood", "Abr 2022 – Mar 2024"),
        bullet([{ text: "Fui responsável pela linha de custo das entregas e pela gestão de FieldOps, Meios de Pagamento e Novos Negócios, com budget de R$300MM/ano e equipe de 240 pessoas, coordenando stakeholders de negócio, produto, dados e operação." }]),
        bullet([{ text: "Liderei S&OP executivo, governança de processos, priorização com produto e modelagem em Python, SQL, Databricks e Tableau para conectar demanda, frota e nível de serviço." }]),
        bullet([{ text: "Reduzi o custo comparável em 3% YoY, ampliei a cobertura de 400 para 800 cidades e aumentei pedidos agrupados de 12% para 25%." }]),
        bullet([{ text: "Implantei pagamento em dinheiro em 352 cidades, elevei a disponibilidade de MPOS de 70% para 97% e reduzi a indisponibilidade da frota de 5% para 1%." }]),
        espaco(6),

        cargoParagraph("Head de Operações", "iFood", "Nov 2018 – Mar 2022"),
        bullet([{ text: "Fui responsável por liveOps, regionalOps, pricing, modelagem de dados e planejamento de frota com equipe de 28 pessoas, em interface direta com engenharia, produto e marketing." }]),
        bullet([{ text: "Estruturei métricas em tempo real no Grafana e modelei dados com SQL, Databricks e Tableau para acompanhar saturação logística e promessa de entrega." }]),
        bullet([{ text: "Conduzi experimentação em raios de entrega e modelos de incentivo na torre de operações do México, reduzindo cancelamentos em 60%." }]),
        bullet([{ text: "Criei o simulador de nível de serviço, gerei saving de R$70MM/ano e reduzi o custo de distribuição de MPOS em 80%." }]),
        espaco(6),

        cargoParagraph("Gerente de Planejamento Comercial e Operações", "VivaReal", "Mai 2015 – Dez 2017"),
        bullet([{ text: "Fui responsável por planejamento comercial e operações com 33 pessoas e 5 lideranças diretas, cobrindo qualidade, SDR e cadastro de imóveis." }]),
        bullet([{ text: "Estruturei processos de onboarding, métricas de CSAT e NPS, e usei Salesforce para pipeline, carteira, pricing e pagamentos com Power BI para inteligência de dados e priorização de roadmap com Produto." }]),
        bullet([{ text: "A área de CS escalou para 91 pessoas, com churn abaixo de 3% ao mês e NPS de 80." }]),
        bullet([{ text: "Aumentei a conversão SDR inbound de 18% para 50%, reduzi custo de vendas em 40% e recuperei R$1M em receita." }]),
        espaco(6),

        secao("Formação"),
        bullet([{ text: "MBA Corporate Strategy — BSP Business School São Paulo (2017)" }]),
        bullet([{ text: "Engenharia Química — Faculdades Oswaldo Cruz (2014)" }]),
        bullet([{ text: "Six Sigma Green Belt — Setec Consulting (2020)" }]),
        bullet([{ text: "ILEad — Fundação Dom Cabral (2021)" }]),
        espaco(6),

        secao("Stack técnica"),
        paragraph("Excel/VBA · SQL · Python · Databricks · Grafana · Tableau · Metabase · Salesforce · Zendesk · WMS"),
        espaco(6),

        secao("Idiomas"),
        bullet([{ text: "Português — Nativo" }]),
        bullet([{ text: "Inglês — Avançado" }]),
      ],
    }],
  });

  const buffer = await Packer.toBuffer(doc);
  fs.writeFileSync(outputPath, buffer);
  console.log("ok");
}

main().catch(error => {
  console.error(error);
  process.exit(1);
});
