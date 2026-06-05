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
const rawOutput = path.join(tempDir, "cv_diretor_operacional_coo_ocean_drop.docx");

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
  const children = runs.map(r => new TextRun({ text: r.text, bold: r.bold || false, size: pt(9), font: "Arial" }));
  return new Paragraph({
    numbering: { reference: "bullets", level: 0 },
    children,
    spacing: { after: pt(2) },
  });
}

function paragraphRuns(runs) {
  return new Paragraph({
    children: runs.map(r => new TextRun({ text: r.text, bold: r.bold || false, size: pt(9), font: "Arial" })),
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
  sections: [{
    properties: {
      page: {
        margin: { top: 720, right: 504, bottom: 720, left: 504 },
      },
    },
    children: [
      new Paragraph({
        children: [new TextRun({ text: "Felipe Armel Dias da Silva", bold: true, size: pt(12), font: "Arial" })],
        spacing: { after: 0 },
      }),
      new Paragraph({
        children: [
          new ExternalHyperlink({
            link: "https://linkedin.com/in/felipearmel",
            children: [new TextRun({ text: "linkedin.com/in/felipearmel", style: "Hyperlink", size: pt(9), font: "Arial" })],
          }),
        ],
        spacing: { after: 0 },
      }),
      new Paragraph({
        children: [new TextRun({ text: "São Paulo, SP", size: pt(9), font: "Arial" })],
        spacing: { after: 0 },
      }),
      new Paragraph({
        children: [
          new ExternalHyperlink({
            link: "https://wa.me/5511986748218",
            children: [new TextRun({ text: "(11) 98674-8218", style: "Hyperlink", size: pt(9), font: "Arial" })],
          }),
        ],
        spacing: { after: 0 },
      }),
      new Paragraph({
        children: [
          new ExternalHyperlink({
            link: "mailto:armelfelipe@gmail.com",
            children: [new TextRun({ text: "armelfelipe@gmail.com", style: "Hyperlink", size: pt(9), font: "Arial" })],
          }),
        ],
        spacing: { after: 0 },
      }),

      espaco(8),
      secao("Resumo"),
      espaco(3),
      paragraphRuns([
        { text: "Executivo sênior em operações, Engenheiro Químico com MBA Corporate Strategy — BSP. No iFood, como Diretor de Operações, gerenciei " },
        { text: "R$300MM/ano", bold: true },
        { text: ", reduzi custo logístico em " },
        { text: "3% YoY", bold: true },
        { text: " e ampliei a cobertura de " },
        { text: "400 para 800 cidades", bold: true },
        { text: ". Na Trifil, liderei supply chain, estoque e S&OP com " },
        { text: "40K SKUs", bold: true },
        { text: ". Busco posição de Diretor Operacional/COO em empresa em crescimento." },
      ]),

      espaco(8),
      secao("Experiência"),
      espaco(3),

      cargoParagraph("Head de Operações", "wehandle", "Mai 2024 – Fev 2026"),
      bullet([
        { text: "Fui responsável por liderar a operação de suporte com time de " },
        { text: "30 pessoas", bold: true },
        { text: ", orçamento de custos e interface diária com produto e dados, profissionalizando a execução em ambiente early-stage." },
      ]),
      bullet([
        { text: "Estruturei a operação com automação, APIs, Zendesk e rituais de priorização com foco em " },
        { text: "Operational Excellence", bold: true },
        { text: ", reduzindo gargalos e ampliando a visibilidade em tempo real." },
      ]),
      bullet([
        { text: "Reduzi o custo por atendimento de " },
        { text: "R$ 4,14 para R$ 3,61 (-13%)", bold: true },
        { text: ", elevei o " },
        { text: "CSAT de 85% para 92%", bold: true },
        { text: " e reduzi o " },
        { text: "TME de 20 para 8 minutos", bold: true },
        { text: "." },
      ]),

      espaco(6),

      cargoParagraph("Diretor de Operações", "iFood", "Abr 2022 – Mar 2024"),
      bullet([
        { text: "Fui responsável por " },
        { text: "Executive Governance", bold: true },
        { text: " e " },
        { text: "OPEX Management", bold: true },
        { text: " da operação logística, com budget de " },
        { text: "R$300MM/ano", bold: true },
        { text: ", equipe de " },
        { text: "240 pessoas", bold: true },
        { text: " e escopo sobre FieldOps, Meios de Pagamento e Novos Negócios." },
      ]),
      bullet([
        { text: "Conduzi " },
        { text: "S&OP", bold: true },
        { text: ", planejamento de frota, leitura semanal de DRE e fóruns cross-functional com produto, marketing e finanças para alinhar demanda, custo e nível de serviço." },
      ]),
      bullet([
        { text: "Reduzi o custo comparável em " },
        { text: "3% YoY", bold: true },
        { text: ", ampliei a cobertura de " },
        { text: "400 para 800 cidades", bold: true },
        { text: " e mantive a operação aderente ao target de EBITDA." },
      ]),

      espaco(6),

      cargoParagraph("Head de Operações", "iFood", "Nov 2018 – Mar 2022"),
      bullet([
        { text: "Fui responsável por " },
        { text: "E-commerce Operations", bold: true },
        { text: " e " },
        { text: "Capacity Planning", bold: true },
        { text: " da logística de última milha, liderando time de " },
        { text: "28 pessoas", bold: true },
        { text: " em liveOps, pricing, modelagem e planejamento de frota." },
      ]),
      bullet([
        { text: "Modelei dados com SQL, Databricks e Grafana para acompanhar saturação logística, oferta, prazo de entrega e decisões operacionais em tempo real." },
      ]),
      bullet([
        { text: "Gerei saving de " },
        { text: "R$70MM/ano", bold: true },
        { text: ", reduzi cancelamentos em " },
        { text: "60%", bold: true },
        { text: " no México e reduzi o prazo de distribuição de MPOS de " },
        { text: "14 para 2 dias", bold: true },
        { text: "." },
      ]),

      espaco(6),

      cargoParagraph("Gerente de Planejamento Comercial e Operações", "VivaReal", "Mai 2015 – Dez 2017"),
      bullet([
        { text: "Fui responsável por planejamento estratégico, operações de onboarding, SDR e cadastro para campanhas de lançamentos, liderando estrutura com " },
        { text: "33 pessoas", bold: true },
        { text: " e " },
        { text: "5 lideranças diretas", bold: true },
        { text: "." },
      ]),
      bullet([
        { text: "Estruturei processos, dados e rotinas com SQL, dashboards e integração com produto para dar previsibilidade à operação e sustentar a execução comercial." },
      ]),
      bullet([
        { text: "Aumentei a conversão SDR inbound de " },
        { text: "18% para 50%", bold: true },
        { text: ", reduzi o custo de vendas em " },
        { text: "40%", bold: true },
        { text: " e recuperei " },
        { text: "R$1M", bold: true },
        { text: " em campanhas de inadimplência." },
      ]),

      espaco(6),

      cargoParagraph("Coordenador de S&OP | Expedição | Supply Chain", "Scalina (Trifil)", "Jan 2006 – Set 2014"),
      bullet([
        { text: "Fui responsável por " },
        { text: "Supply Chain Management", bold: true },
        { text: ", " },
        { text: "Inventory Management", bold: true },
        { text: " e operação física fim a fim, cobrindo " },
        { text: "40K SKUs", bold: true },
        { text: ", MRP corporativo, expedição, OTIF e interface entre comercial, planejamento e fábrica." },
      ]),
      bullet([
        { text: "Implantei " },
        { text: "Strategic Sourcing", bold: true },
        { text: ", política de estoque de segurança, WMS, inventário rotativo e redesenho de processos para elevar controle, produtividade e previsibilidade operacional." },
      ]),
      bullet([
        { text: "Entreguei " },
        { text: "Cost Reduction", bold: true },
        { text: " de " },
        { text: "27%", bold: true },
        { text: " em compras, reduzi a falta de estoque em " },
        { text: "40%", bold: true },
        { text: ", elevei a acurácia para " },
        { text: "98%", bold: true },
        { text: " e reduzi " },
        { text: "R$8M", bold: true },
        { text: " de GGF." },
      ]),

      espaco(8),
      secao("Formação"),
      espaco(3),
      bullet([{ text: "ILEad — Liderança para Líder de Líderes — Fundação Dom Cabral (2021)" }]),
      bullet([{ text: "Six Sigma Green Belt — Setec Consulting (2020)" }]),
      bullet([{ text: "MBA Corporate Strategy — BSP Business School São Paulo (2016–2017)" }]),
      bullet([{ text: "Engenheiro Químico — Faculdades Oswaldo Cruz (2014)" }]),

      espaco(8),
      secao("Stack técnica"),
      espaco(3),
      paragraphRuns([{ text: "SQL · Python · Databricks · Grafana · Zendesk · Metabase · Excel/VBA · ERP Infor LN · WMS" }]),

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
