const fs = require("fs");
const path = require("path");
const { spawnSync } = require("child_process");
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
const outputDir = process.env.CAREER_OUTPUTS || path.join(workspace, "outputs");

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
      new TextRun({ text: `${cargo} \u2014 ${empresa}`, bold: true, size: pt(9), font: "Arial" }),
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

function paragraph(text, options = {}) {
  return new Paragraph({
    children: [new TextRun({ text, size: pt(options.size || 9), bold: !!options.bold, font: "Arial" })],
    spacing: { after: 0 },
  });
}

function hyperlink(text, url) {
  return new Paragraph({
    children: [
      new ExternalHyperlink({
        link: url,
        children: [new TextRun({ text, style: "Hyperlink", size: pt(9), font: "Arial" })],
      }),
    ],
    spacing: { after: 0 },
  });
}

async function main() {
  const outputName = "felipe_armel_cv_coordenador_operacoes_cx_flash.docx";
  fs.mkdirSync(path.join(outputDir, "_tmp"), { recursive: true });

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
          margin: { top: 720, right: 504, bottom: 720, left: 504 },
        },
      },
      children: [
        paragraph("Felipe Armel Dias da Silva", { size: 12, bold: true }),
        hyperlink("linkedin.com/in/felipearmel", "https://linkedin.com/in/felipearmel"),
        paragraph("S\u00e3o Paulo, SP"),
        hyperlink("(11) 98674-8218", "https://wa.me/5511986748218"),
        hyperlink("armelfelipe@gmail.com", "mailto:armelfelipe@gmail.com"),

        espaco(8),
        secao("Resumo"),
        paragraph("Engenheiro Qu\u00edmico com MBA em Corporate Strategy. Executivo com 27 anos de carreira, sendo os \u00faltimos dois anos dedicados a opera\u00e7\u00f5es de atendimento ao cliente. Na WeHandle, como Head de Opera\u00e7\u00f5es, reestruturei a opera\u00e7\u00e3o de suporte com m\u00e9tricas de CSAT, SLA e contact rate, elevando a satisfa\u00e7\u00e3o de 85% para 92%. No iFood, como Diretor de Opera\u00e7\u00f5es, geri budget de R$300MM/ano e ampliei a opera\u00e7\u00e3o de 400 para 800 cidades. Busco posi\u00e7\u00e3o de Coordenador de Opera\u00e7\u00f5es CX."),
        espaco(8),

        secao("Experi\u00eancia"),
        espaco(3),

        // WeHandle
        cargoParagraph("Head de Opera\u00e7\u00f5es", "WeHandle", "Mai 2024 \u2013 Fev 2026"),
        bullet([
          { text: "Fui respons\u00e1vel por liderar a opera\u00e7\u00e3o de atendimento ao cliente com equipe de 30 pessoas, definindo metas de CSAT, SLA, contact rate e TME, e criando a \u00e1rea de Experi\u00eancia do Cliente com board de prioriza\u00e7\u00e3o e governan\u00e7a de melhoria cont\u00ednua junto ao time de produto." },
        ]),
        bullet([
          { text: "Estruturei a opera\u00e7\u00e3o com carteiriza\u00e7\u00e3o de clientes, automa\u00e7\u00e3o com IA humanizada e implanta\u00e7\u00e3o de WhatsApp, conectando dados das plataformas de atendimento via API para an\u00e1lise de causa raiz." },
        ]),
        bullet([
          { text: "Elevei o CSAT de " },
          { text: "85% para 92%", bold: true },
          { text: ", reduzi o TME de 20 para 8 minutos e o custo por atendimento de R$4,14 para R$3,61, com redu\u00e7\u00e3o de 8% no contact rate." },
        ]),
        espaco(6),

        // iFood Diretor
        cargoParagraph("Diretor de Opera\u00e7\u00f5es", "iFood", "Abr 2022 \u2013 Mar 2024"),
        bullet([
          { text: "Fui respons\u00e1vel por gerir as opera\u00e7\u00f5es log\u00edsticas com equipe de 240 pessoas e budget de " },
          { text: "R$300MM/ano", bold: true },
          { text: ", liderando S&OP executivo mensal que conectava marketing, opera\u00e7\u00e3o e finan\u00e7as." },
        ]),
        bullet([
          { text: "Liderei iniciativas de efici\u00eancia com modelagem em Python, SQL e Databricks, capacity planning por cluster de cidades e testes de modelos de incentivo para a frota de entregadores." },
        ]),
        bullet([
          { text: "Ampliei a cobertura de " },
          { text: "400 para 800 cidades", bold: true },
          { text: " e reduzi a indisponibilidade de frota de 5,4% para 0,5% nas seis maiores cidades, mantendo SLA est\u00e1vel em opera\u00e7\u00e3o de 30M pedidos/m\u00eas." },
        ]),
        espaco(6),

        // iFood Head
        cargoParagraph("Head de Opera\u00e7\u00f5es", "iFood", "Nov 2018 \u2013 Mar 2022"),
        bullet([
          { text: "Fui respons\u00e1vel por estruturar a \u00e1rea de liveOps e modelagem de dados com equipe de 28 pessoas, atuando em pricing de frota, planejamento e intelig\u00eancia operacional em tempo real." },
        ]),
        bullet([
          { text: "Criei dashboards no Grafana, modelei dados com SQL, Databricks e Tableau e desenvolvi um simulador de n\u00edvel de servi\u00e7o para decis\u00f5es de trade-off entre custo e SLA." },
        ]),
        bullet([
          { text: "Gerei " },
          { text: "saving de R$70M/ano", bold: true },
          { text: " com o simulador e implementei a distribui\u00e7\u00e3o de MPOS em 352 cidades com zero perda financeira." },
        ]),
        espaco(6),

        // VivaReal
        cargoParagraph("Gerente de Planejamento Comercial e Opera\u00e7\u00f5es", "VivaReal", "Mai 2015 \u2013 Dez 2017"),
        bullet([
          { text: "Fui respons\u00e1vel por arquitetar a \u00e1rea de Customer Success, desenhando processos, r\u00e9gua de onboarding e indicadores de qualidade \u2014 a \u00e1rea escalou para " },
          { text: "91 pessoas", bold: true },
          { text: " sob supervis\u00e3o indireta." },
        ]),
        bullet([
          { text: "Apliquei SQL, Excel automatizado e dashboards para monitorar churn, CSAT e NPS em tempo real, direcionando decis\u00f5es com dados dispon\u00edveis diariamente." },
        ]),
        bullet([
          { text: "Alcancei " },
          { text: "CSAT acima de 92%", bold: true },
          { text: ", churn abaixo de 3% ao m\u00eas e NPS de 80%, al\u00e9m de reduzir o custo de vendas em 40% com otimiza\u00e7\u00e3o do funil de SDR." },
        ]),
        espaco(8),

        secao("Forma\u00e7\u00e3o"),
        bullet([{ text: "Engenharia Qu\u00edmica \u2014 Faculdades Oswaldo Cruz (2014)" }]),
        bullet([{ text: "MBA Corporate Strategy \u2014 BSP Business School S\u00e3o Paulo (2017)" }]),
        espaco(8),

        secao("Stack t\u00e9cnica"),
        paragraph("Zendesk \u00b7 SQL \u00b7 Python \u00b7 Excel/VBA \u00b7 Grafana \u00b7 Metabase \u00b7 APIs de integra\u00e7\u00e3o"),
        espaco(8),

        secao("Idiomas"),
        bullet([{ text: "Portugu\u00eas \u2014 Nativo" }]),
        bullet([{ text: "Ingl\u00eas \u2014 Avan\u00e7ado" }]),
      ],
    }],
  });

  const buffer = await Packer.toBuffer(doc);
  const tmpPath = path.join(outputDir, "_tmp", outputName);
  fs.writeFileSync(tmpPath, buffer);
  console.log("ok");
}

main().catch(error => {
  console.error(error);
  process.exit(1);
});
