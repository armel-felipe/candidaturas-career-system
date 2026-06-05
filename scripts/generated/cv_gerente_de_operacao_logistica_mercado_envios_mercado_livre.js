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
const tempDir = path.join(workspace, "outputs", "_tmp");
const rawOutput = path.join(tempDir, "felipe_armel_cv_gerente_de_operacao_logistica_mercado_livre.docx");

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
    children: runs.map(run => new TextRun({ text: run.text, bold: !!run.bold, size: pt(9), font: "Arial" })),
    spacing: { after: pt(2) },
  });
}

function paragraphRuns(runs) {
  return new Paragraph({
    children: runs.map(run => new TextRun({ text: run.text, bold: !!run.bold, size: pt(9), font: "Arial" })),
    spacing: { after: 0 },
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
        style: { paragraph: { indent: { left: 360, hanging: 180 } } },
      }],
    }],
  },
  styles: {
    default: { document: { run: { font: "Arial", size: pt(9) } } },
    paragraphStyles: [
      { id: "Normal", name: "Normal", quickFormat: true, run: { font: "Arial", size: pt(9) }, paragraph: { spacing: { after: 0 } } },
      { id: "ListParagraph", name: "List Paragraph", basedOn: "Normal", quickFormat: true, run: { font: "Arial", size: pt(9) }, paragraph: { spacing: { after: 0 } } },
    ],
  },
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 720, right: 504, bottom: 720, left: 504 } } },
    children: [
      new Paragraph({ children: [new TextRun({ text: "Felipe Armel Dias da Silva", bold: true, size: pt(12), font: "Arial" })], spacing: { after: 0 } }),
      new Paragraph({ children: [new ExternalHyperlink({ link: "https://linkedin.com/in/felipearmel", children: [new TextRun({ text: "linkedin.com/in/felipearmel", style: "Hyperlink", size: pt(9), font: "Arial" })] })], spacing: { after: 0 } }),
      new Paragraph({ children: [new TextRun({ text: "São Paulo, SP", size: pt(9), font: "Arial" })], spacing: { after: 0 } }),
      new Paragraph({ children: [new ExternalHyperlink({ link: "https://wa.me/5511986748218", children: [new TextRun({ text: "(11) 98674-8218", style: "Hyperlink", size: pt(9), font: "Arial" })] })], spacing: { after: 0 } }),
      new Paragraph({ children: [new ExternalHyperlink({ link: "mailto:armelfelipe@gmail.com", children: [new TextRun({ text: "armelfelipe@gmail.com", style: "Hyperlink", size: pt(9), font: "Arial" })] })], spacing: { after: 0 } }),

      espaco(8),
      secao("Resumo"),
      espaco(3),
      paragraphRuns([
        { text: "Engenheiro Químico com MBA Corporate Strategy — BSP e carreira em operações de escala. No iFood, como Diretor de Operações, liderei " },
        { text: "Logistics Operations", bold: true },
        { text: " com " },
        { text: "Team Leadership", bold: true },
        { text: " de ~240 pessoas, budget de " },
        { text: "R$300MM/ano", bold: true },
        { text: " e cobertura de " },
        { text: "400 para 800 cidades", bold: true },
        { text: ". Na Trifil, estruturei " },
        { text: "Supply Chain Management", bold: true },
        { text: " e " },
        { text: "Warehouse Operations", bold: true },
        { text: ", reduzindo R$8M de GGF. Busco atuar em operações logísticas de alta complexidade." },
      ]),

      espaco(8),
      secao("Experiência"),
      espaco(3),

      cargoParagraph("Head de Operações", "wehandle", "Mai 2024 – Fev 2026"),
      bullet([
        { text: "Fui responsável por uma operação de suporte com time de 30 pessoas, orçamento de custos e foco em " },
        { text: "Operational Efficiency", bold: true },
        { text: ", CSAT e SLA, com impacto de 15% na margem bruta." },
      ]),
      bullet([
        { text: "Liderei migrações de plataforma, automação com IA, integração via API e " },
        { text: "Data-Driven Decision Making", bold: true },
        { text: " com Python, SQL, Metabase e Zendesk para operar com indicadores em tempo real." },
      ]),
      bullet([
        { text: "Reduzi o custo por atendimento de " },
        { text: "R$4,14 para R$3,61 (-13%)", bold: true },
        { text: ", elevei o CSAT de " },
        { text: "85% para 92%", bold: true },
        { text: " e reduzi o TME de " },
        { text: "20 para 8 minutos", bold: true },
        { text: "." },
      ]),

      espaco(6),

      cargoParagraph("Head e Diretor de Operações", "iFood", "Nov 2018 – Mar 2024"),
      bullet([
        { text: "Fui responsável por " },
        { text: "Logistics Operations", bold: true },
        { text: " em marketplace com " },
        { text: "Team Leadership", bold: true },
        { text: " de ~240 pessoas, budget de R$300MM/ano e gestão de FieldOps, pagamentos e novos negócios." },
      ]),
      bullet([
        { text: "Conduzi " },
        { text: "Capacity Planning", bold: true },
        { text: ", " },
        { text: "Supply Chain Management", bold: true },
        { text: " operacional e " },
        { text: "Data-Driven Decision Making", bold: true },
        { text: " com S&OP executivo, Python, SQL, Databricks e Grafana para equilibrar custo, cobertura e SLA." },
      ]),
      bullet([
        { text: "Ampliei a cobertura de " },
        { text: "400 para 800 cidades", bold: true },
        { text: ", reduzi o custo comparável em " },
        { text: "3% YoY", bold: true },
        { text: " e gerei saving de " },
        { text: "R$70MM/ano", bold: true },
        { text: " com simulador de nível de serviço." },
      ]),

      espaco(6),

      cargoParagraph("Coordenador de S&OP | Expedição | Supply Chain", "Trifil", "Jan 2006 – Set 2014"),
      bullet([
        { text: "Fui responsável por " },
        { text: "Supply Chain Management", bold: true },
        { text: " com 40K SKUs, MRP corporativo, S&OP e expedição, sustentando interface entre comercial, PCP e fabricação." },
      ]),
      bullet([
        { text: "Estruturei " },
        { text: "KPI Management", bold: true },
        { text: ", " },
        { text: "Continuous Improvement", bold: true },
        { text: ", WMS, coletores RF/wi-fi e inventário rotativo para elevar controle e fluidez da operação." },
      ]),
      bullet([
        { text: "Reduzi " },
        { text: "R$8M", bold: true },
        { text: " de GGF, elevei a acurácia de estoque de " },
        { text: "85% para 98%", bold: true },
        { text: " e levei o Projeto Entrega Certa ao reporte direto para o CEO." },
      ]),

      espaco(8),
      secao("Formação"),
      espaco(3),
      bullet([{ text: "MBA Corporate Strategy — BSP Business School São Paulo (2016–2017)" }]),
      bullet([{ text: "Engenheiro Químico — Faculdades Oswaldo Cruz (2014)" }]),
      bullet([{ text: "Six Sigma Green Belt — Setec Consulting (2020)" }]),
      bullet([{ text: "ILEad — Liderança para Líder de Líderes — Fundação Dom Cabral (2021)" }]),

      espaco(8),
      secao("Stack técnica"),
      espaco(3),
      paragraphRuns([{ text: "SQL · Python · Databricks · Grafana · Excel/VBA · WMS · ERP Infor LN · Metabase" }]),

      espaco(8),
      secao("Idiomas"),
      espaco(3),
      bullet([{ text: "Português — Nativo" }]),
      bullet([{ text: "Inglês — Avançado" }]),
    ],
  }],
});

Packer.toBuffer(doc).then(buffer => {
  fs.mkdirSync(tempDir, { recursive: true });
  fs.writeFileSync(rawOutput, buffer);
  console.log("ok");
});
