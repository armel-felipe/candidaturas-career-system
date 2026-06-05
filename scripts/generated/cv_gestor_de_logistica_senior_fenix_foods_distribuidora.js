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
const workspace = process.cwd();
const tmpDir = path.join(workspace, "outputs", "_tmp");
const outputPath = path.join(tmpDir, "cv_gestor_de_logistica_senior_fenix_foods_distribuidora.docx");

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
        paragraph("Executivo sênior com experiência em Gestão Logística, Distribuição, Roteirização Urbana, Otimização de Rotas, Redução de Custos, Indicadores Logísticos, Nível de Serviço e Liderança de Equipe. No iFood, gerei saving de R$70MM/ano e expandi cobertura de 400 para 800 cidades. Na Trifil, elevei a acuracidade de estoque de 85% para 98% e a produtividade em 35%. Busco liderar a operação logística da Fenix Foods com disciplina e melhoria contínua."),

        espaco(8),
        secao("Experiência"),

        cargoParagraph("Head de Operações", "wehandle", "Mai 2024 – Fev 2026"),
        bullet([
          { text: "Fui responsável por liderar a operação de suporte e CX com " },
          { text: "30 pessoas", bold: true },
          { text: ", garantindo Liderança de Equipe, disciplina de execução, orçamento de custos, SLA de atendimento e interface direta com produto e dados." },
        ]),
        bullet([
          { text: "Estruturei processos, automação com chatbot e IA, canal de WhatsApp, Zendesk e integração via API para dar previsibilidade operacional e visão em tempo real da operação." },
        ]),
        bullet([
          { text: "Reduzi o custo total de atendimento de " },
          { text: "R$4,14 para R$3,61", bold: true },
          { text: ", elevei o " },
          { text: "CSAT de 85% para 92%", bold: true },
          { text: ", mantive " },
          { text: "SLA em 95%", bold: true },
          { text: " e impactei " },
          { text: "15% na margem bruta", bold: true },
          { text: "." },
        ]),

        espaco(6),
        cargoParagraph("Head e Diretor de Operações", "iFood", "Nov 2018 – Mar 2024"),
        bullet([
          { text: "Fui responsável por Gestão Logística e Distribuição em operação de última milha, com equipe de " },
          { text: "240 pessoas", bold: true },
          { text: ", budget de " },
          { text: "R$300MM/ano", bold: true },
          { text: ", planeamento de frota por cidade e interface executiva para nível Brasil e São Paulo." },
        ]),
        bullet([
          { text: "Conduzi Roteirização Urbana, Otimização de Rotas, Indicadores Logísticos e Nível de Serviço com simulador próprio, Grafana em tempo real, balanceamento de frota, ajuste de raios e testes de remuneração por zona." },
        ]),
        bullet([
          { text: "Gerei saving de " },
          { text: "R$70MM/ano", bold: true },
          { text: ", ampliei cobertura de " },
          { text: "400 para 800 cidades", bold: true },
          { text: ", reduzi custo comparável em " },
          { text: "3% YoY", bold: true },
          { text: ", elevei entregas agrupadas de " },
          { text: "12% para 25%", bold: true },
          { text: " e reduzi o custo de distribuição de MPOS em " },
          { text: "80%", bold: true },
          { text: "." },
        ]),

        espaco(6),
        cargoParagraph("Gerente de Planejamento Comercial e Operações", "VivaReal", "Mai 2015 – Dez 2017"),
        bullet([
          { text: "Fui responsável por liderar operações com " },
          { text: "33 pessoas e 5 lideranças diretas", bold: true },
          { text: ", cobrindo Qualidade, SDR, onboarding, cadastro de imóveis e planejamento operacional com foco em disciplina, padrão de serviço e integração entre áreas." },
        ]),
        bullet([
          { text: "Estruturei processos, dashboards e ritos de gestão para atendimento, onboarding e performance comercial, além de desenhar a área de CS e contratar sua liderança." },
        ]),
        bullet([
          { text: "Alcancei " },
          { text: "NPS 80%", bold: true },
          { text: ", " },
          { text: "CSAT acima de 92%", bold: true },
          { text: ", mantive churn abaixo de " },
          { text: "3% ao mês", bold: true },
          { text: " e aumentei a conversão SDR de " },
          { text: "18% para 50%", bold: true },
          { text: "." },
        ]),

        espaco(6),
        cargoParagraph("Coordenador de S&OP | Expedição | Supply Chain", "Scalina (Trifil)", "Jan 2006 – Set 2014"),
        bullet([
          { text: "Fui responsável por coordenar a operação física de expedição e supply chain, gerenciando " },
          { text: "40K SKUs", bold: true },
          { text: " em todos os canais de Distribuição, com foco em acuracidade, produtividade, OTIF, estoques de segurança e disciplina operacional." },
        ]),
        bullet([
          { text: "Estruturei melhoria contínua com MRP corporativo, WMS, inventário rotativo, endereçamento de estoque, coletores RF e Projeto Entrega Certa para maximizar OTIF, fill rate e produtividade." },
        ]),
        bullet([
          { text: "Elevei a acuracidade de estoque de " },
          { text: "85% para 98%", bold: true },
          { text: ", aumentei a produtividade em " },
          { text: "35%", bold: true },
          { text: ", reduzi perdas em " },
          { text: "30%", bold: true },
          { text: " e capturei " },
          { text: "R$8MM", bold: true },
          { text: " de redução de GGF." },
        ]),

        espaco(8),
        secao("Formação"),
        bullet([{ text: "MBA Corporate Strategy — BSP Business School São Paulo (2016–2017)" }]),
        bullet([{ text: "Engenheiro Químico — Faculdades Oswaldo Cruz (2014)" }]),
        bullet([{ text: "Técnico em Química — SENAI Mario Amato (1997)" }]),

        espaco(8),
        secao("Stack técnica"),
        paragraph("ERP Infor LN · WMS · Excel/VBA · SQL · Python · Databricks · Grafana · Power BI · Tableau"),

        espaco(8),
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
