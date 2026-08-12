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
  const outputName = process.argv[2] || "felipe_armel_cv_gerente_planejamento_otimizacao_adm.docx";
  fs.mkdirSync(outputDir, { recursive: true });

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
        paragraph("São Paulo, SP"),
        hyperlink("(11) 98674-8218", "https://wa.me/5511986748218"),
        hyperlink("armelfelipe@gmail.com", "mailto:armelfelipe@gmail.com"),
        espaco(8),
        secao("Resumo"),
        paragraph("Engenheiro Químico com MBA e 18 anos em supply chain, S&OP, otimização de processos e gestão operacional — iFood (Diretor de Operações, R$300MM de budget), Trifil (criação do S&OP), WeHandle (transformação digital). Liderei planejamento estratégico, governança de indicadores e análise de cenários conectando operações e finanças. Busco posição de Gerente de Planejamento e Otimização."),
        espaco(8),
        secao("Experiência"),
        cargoParagraph("Head de Operações", "wehandle", "Mai 2024 – Fev 2026"),
        bullet([
          { text: "Fui responsável por liderar a operação de suporte a clientes com time de 30 pessoas, reestruturando processos e conectando CX, dados e produto." },
        ]),
        bullet([
          { text: "Liderei duas migrações de plataforma com gestão de mudança organizacional, integrei dados via API a datalakes com BI (Metabase) e implantei chatbot humanizado e WhatsApp." },
        ]),
        bullet([
          { text: "Reduzi o custo por atendimento de R$4,14 para R$3,61 (−13%), elevei o CSAT de 85% para 92% e gerei impacto de 15% na margem bruta." },
        ]),
        espaco(6),
        cargoParagraph("Diretor de Operações", "iFood", "Abr 2022 – Mar 2024"),
        bullet([
          { text: "Fui responsável por gerir as operações logísticas com equipe de " },
          { text: "240 pessoas", bold: true },
          { text: " e budget de " },
          { text: "R$300MM/ano", bold: true },
          { text: ", conduzindo S&OP executivo mensal com foco em custo, nível de serviço e cobertura." },
        ]),
        bullet([
          { text: "Conduzi planejamento integrado conectando marketing, clima e frota com modelagem em Python, SQL e Databricks para capacity planning, análise de cenários e governança de indicadores." },
        ]),
        bullet([
          { text: "Ampliei a cobertura de " },
          { text: "400 para 800 cidades", bold: true },
          { text: ", reduzi o custo logístico comparável em 3% YoY e aumentei entregas agrupadas de 12% para 25%, alcançando o breakeven." },
        ]),
        espaco(6),
        cargoParagraph("Head de Operações", "iFood", "Nov 2018 – Mar 2022"),
        bullet([
          { text: "Fui responsável por estruturar o planejamento de frota e balanceamento por cidade, liderando equipe de 28 pessoas em liveOps, pricing, modelagem e otimização." },
        ]),
        bullet([
          { text: "Criei simulador de nível de serviço com dashboards em tempo real no Grafana, modelei dados em Databricks e desenvolvi ferramentas de restrição de raio." },
        ]),
        bullet([
          { text: "Gerei saving de " },
          { text: "R$70M/ano", bold: true },
          { text: " com o simulador de frota, reduzi cancelamentos no México em 60% ajustando raios de entrega e reduzi o prazo de distribuição de MPOS de 14 para 2 dias." },
        ]),
        espaco(6),
        cargoParagraph("Gerente de Planejamento Comercial e Operações", "VivaReal", "Mai 2015 – Dez 2017"),
        bullet([
          { text: "Fui responsável pelo planejamento estratégico e operacional, gerindo equipes de SDR, qualidade e cadastro com 33 pessoas e 5 lideranças diretas." },
        ]),
        bullet([
          { text: "Estruturei a área de CS como arquiteto — desenhei processos, régua de onboarding e contratei a liderança que escalou a operação para 91 pessoas." },
        ]),
        bullet([
          { text: "Elevei a conversão SDR inbound de 18% para 50%, reduzi o custo de vendas em 40%, mantive churn abaixo de 3% ao mês e recuperei R$1M em inadimplentes." },
        ]),
        espaco(6),
        cargoParagraph("Coordenador de S&OP", "Scalina (Trifil)", "Jan 2010 – Set 2014"),
        bullet([
          { text: "Fui responsável por criar a área de S&OP do zero, gerenciando " },
          { text: "40K SKUs", bold: true },
          { text: " em duas marcas com MRP corporativo e análise de capacidade produtiva." },
        ]),
        bullet([
          { text: "Implantei simulador de cenários para o S&OP com Excel VBA, defini política de estoque de segurança e liderei o Projeto Entrega Certa com OTIF e fill rate." },
        ]),
        bullet([
          { text: "Reduzi " },
          { text: "R$8M de GGF", bold: true },
          { text: " do P&L, aumentei o faturamento de R$80M para R$120M com algoritmo VBA de alocação de estoque e reduzi custo de compras em 27% com Strategic Sourcing." },
        ]),
        espaco(8),
        secao("Formação"),
        bullet([{ text: "MBA Corporate Strategy — BSP Business School São Paulo (2017)" }]),
        bullet([{ text: "Engenharia Química — Faculdades Oswaldo Cruz (2014)" }]),
        bullet([{ text: "Six Sigma Green Belt — Setec Consulting (2020)" }]),
        bullet([{ text: "Programa de Liderança ILead — Fundação Dom Cabral (2021)" }]),
        espaco(8),
        secao("Stack técnica"),
        paragraph("Excel/VBA · SQL · Python · PySpark · Databricks · Power BI · Grafana · Tableau · Metabase · Salesforce · ERP Infor LN"),
        espaco(8),
        secao("Idiomas"),
        bullet([{ text: "Português — Nativo" }]),
        bullet([{ text: "Inglês — Avançado" }]),
      ],
    }],
  });

  const buffer = await Packer.toBuffer(doc);
  const outputPath = path.join(outputDir, outputName);
  fs.writeFileSync(outputPath, buffer);
  const themeScript = path.join(workspace, "scripts", "docx", "inject_arial_theme.py");
  const themeResult = spawnSync(process.env.PYTHON || "python", [themeScript, outputPath], { stdio: "inherit" });
  if (themeResult.status !== 0) {
    process.exit(themeResult.status || 1);
  }
  console.log(outputPath);
}

main().catch(error => {
  console.error(error);
  process.exit(1);
});
