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
const outputDir = path.join(workspace, "outputs", "_tmp");
const outputPath = path.join(
  outputDir,
  "cv_gerencia_geral_coordenacao_geral_operacional_pimp_my_carroca.docx"
);

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
  const children = runs.map(r =>
    new TextRun({ text: r.text, bold: r.bold || false, size: pt(9), font: "Arial" })
  );
  return new Paragraph({
    numbering: { reference: "bullets", level: 0 },
    children,
    spacing: { after: pt(2) },
  });
}

function paragrafo(text, options = {}) {
  return new Paragraph({
    children: [
      new TextRun({
        text,
        size: pt(options.size || 9),
        bold: !!options.bold,
        font: "Arial",
      }),
    ],
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
          size: { width: 11906, height: 16838 },
          margin: { top: 720, right: 504, bottom: 720, left: 504 },
        },
      },
      children: [
        paragrafo("Felipe Armel Dias da Silva", { size: 12, bold: true }),
        hyperlink("linkedin.com/in/felipearmel", "https://linkedin.com/in/felipearmel"),
        paragrafo("São Paulo, SP"),
        hyperlink("(11) 98674-8218", "https://wa.me/5511986748218"),
        hyperlink("armelfelipe@gmail.com", "mailto:armelfelipe@gmail.com"),

        espaco(8),

        secao("Resumo"),
        espaco(3),
        paragrafo(
          "Executivo sênior de operações, planejamento estratégico e gestão operacional. Na wehandle, reduzi o custo por atendimento em 13% e gerei 15% de impacto na margem bruta. No iFood, conduzi governança logística com budget de R$300MM/ano e expansão de 400 para 800 cidades. Busco posição de Gerência Geral em ambiente colaborativo, com forte integração entre áreas, inclusive em oportunidades no terceiro setor."
        ),

        espaco(8),

        secao("Experiência"),
        espaco(3),

        cargoParagraph("Head de Operações", "wehandle", "Mai 2024 – Fev 2026"),
        bullet([
          { text: "Fui responsável pela " },
          { text: "gestão de processos", bold: true },
          { text: " e pela organização interna da operação de suporte e CX da wehandle, liderando um time de 30 pessoas com foco em " },
          { text: "comunicação interna", bold: true },
          { text: ", SLA e alinhamento entre suporte, produto e dados." },
        ]),
        bullet([
          { text: "Estruturei " },
          { text: "comunicação interna", bold: true },
          { text: ", atendimento via WhatsApp e automação com IA, conectando APIs, Zendesk e Metabase para dar visibilidade em tempo real e melhorar a " },
          { text: "integração entre áreas", bold: true },
          { text: " em ambiente colaborativo." },
        ]),
        bullet([
          { text: "Reduzi o custo por atendimento de " },
          { text: "R$4,14 para R$3,61", bold: true },
          { text: ", elevei o CSAT de 85% para " },
          { text: "92%", bold: true },
          { text: ", mantive SLA em 95% dos tickets e gerei impacto de " },
          { text: "15%", bold: true },
          { text: " na margem bruta." },
        ]),

        espaco(6),

        cargoParagraph("Diretor de Operações", "iFood", "Abr 2022 – Mar 2024"),
        bullet([
          { text: "Fui responsável pela " },
          { text: "gestão operacional", bold: true },
          { text: " da logística do iFood, com budget de " },
          { text: "R$300MM/ano", bold: true },
          { text: ", liderança de cerca de 240 pessoas e " },
          { text: "governança", bold: true },
          { text: " de operações, FieldOps, Meios de Pagamento e Novos Negócios." },
        ]),
        bullet([
          { text: "Liderei " },
          { text: "governança", bold: true },
          { text: ", " },
          { text: "integração entre áreas", bold: true },
          { text: " e " },
          { text: "tomada de decisão", bold: true },
          { text: " no S&OP executivo, conectando marketing, produto, supply, frota e financeiro em um único processo de " },
          { text: "planejamento estratégico", bold: true },
          { text: "." },
        ]),
        bullet([
          { text: "Reduzi o custo logístico comparável em " },
          { text: "3% YoY", bold: true },
          { text: ", ampliei a cobertura de " },
          { text: "400 para 800 cidades", bold: true },
          { text: " e mantive aderência ao plano financeiro com leitura recorrente de variação vs meta." },
        ]),

        espaco(6),

        cargoParagraph("Head de Operações", "iFood", "Nov 2018 – Mar 2022"),
        bullet([
          { text: "Fui responsável por " },
          { text: "equipes multidisciplinares", bold: true },
          { text: " de liveOps, regionalOps, pricing, modelagem de dados e planejamento de frota, liderando 28 pessoas em operação de alta complexidade." },
        ]),
        bullet([
          { text: "Desenvolvi " },
          { text: "liderança colaborativa", bold: true },
          { text: " com SQL, Databricks, Tableau e capacity planning para integrar dados, precificação, disponibilidade de frota e nível de serviço em tempo real." },
        ]),
        bullet([
          { text: "Gerei " },
          { text: "R$70MM/ano", bold: true },
          { text: " de saving com simulador de nível de serviço, reduzi em " },
          { text: "80%", bold: true },
          { text: " o custo de distribuição de MPOS e reduzi o prazo de entrega de " },
          { text: "14 para 2 dias", bold: true },
          { text: "." },
        ]),

        espaco(6),

        cargoParagraph("Gerente de Planejamento Comercial e Operações", "VivaReal", "Mai 2015 – Dez 2017"),
        bullet([
          { text: "Fui responsável por " },
          { text: "planejamento estratégico", bold: true },
          { text: ", " },
          { text: "metas e cronogramas", bold: true },
          { text: " e operações com 33 pessoas nas áreas de Qualidade, SDR e cadastro, apoiando a " },
          { text: "organização interna", bold: true },
          { text: " e o " },
          { text: "fortalecimento institucional", bold: true },
          { text: " da empresa." },
        ]),
        bullet([
          { text: "Conduzi " },
          { text: "mediação", bold: true },
          { text: " e articulação entre áreas com SQL, dashboards diários e interface direta com CFO, produto e lideranças comerciais para garantir execução, reestruturação e priorização de entregas." },
        ]),
        bullet([
          { text: "Aumentei a conversão de SDR inbound de " },
          { text: "18% para 50%", bold: true },
          { text: ", recuperei " },
          { text: "R$1MM", bold: true },
          { text: " em inadimplência e ajudei a estruturar a área de CS que escalou para " },
          { text: "91 pessoas", bold: true },
          { text: "." },
        ]),

        espaco(8),

        secao("Formação"),
        espaco(3),
        bullet([{ text: "ILead Liderança para Líder de Líderes — Fundação Dom Cabral (2021)" }]),
        bullet([{ text: "Six Sigma Green Belt — Setec Consulting (2020)" }]),
        bullet([{ text: "MBA Corporate Strategy — BSP Business School São Paulo (2016–2017)" }]),
        bullet([{ text: "Engenheiro Químico — Faculdades Oswaldo Cruz (2014)" }]),

        espaco(8),

        secao("Stack técnica"),
        espaco(3),
        paragrafo("SQL · Python · Databricks · Zendesk · Metabase · Tableau · Power BI"),

        espaco(8),

        secao("Idiomas"),
        espaco(3),
        bullet([{ text: "Português — Nativo" }]),
        bullet([{ text: "Inglês — Avançado" }]),
      ],
    }],
  });

  const buffer = await Packer.toBuffer(doc);
  fs.writeFileSync(outputPath, buffer);
  console.log("ok");
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
