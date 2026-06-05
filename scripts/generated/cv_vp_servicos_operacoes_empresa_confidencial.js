// CV - Felipe Armel Dias da Silva
// Vaga: VP de Serviços & Operações - Empresa Confidencial
// Datas validadas em autoconhecimento.md:
//   wehandle        Head de Operações                              Mai 2024 - Fev 2026
//   iFood           Diretor de Operações                           Abr 2022 - Mar 2024
//   iFood           Head de Operações                              Nov 2018 - Mar 2022
//   VivaReal        Gerente de Planejamento Comercial e Operações  Mai 2015 - Dez 2017
//   Scalina/Trifil  Coordenador de S&OP                            Jan 2010 - Set 2014

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

const pt = n => n * 2; // half-points. NUNCA n * 20.

const workspace = process.env.CAREER_WORKSPACE || process.cwd();
const tmpDir = path.join(workspace, "outputs", "_tmp");
const outputPath = path.join(tmpDir, "cv_vp_servicos_operacoes_empresa_confidencial.docx");

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
    children: runs.map(r => new TextRun({
      text: r.text,
      bold: r.bold || false,
      size: pt(9),
      font: "Arial",
    })),
    spacing: { after: pt(2) },
  });
}

function paragrafo(text, options = {}) {
  return new Paragraph({
    children: [new TextRun({
      text,
      size: pt(options.size || 9),
      bold: !!options.bold,
      font: "Arial",
    })],
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
          text: "•",
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
          "Executivo Sênior em gestão de operações, serviços ao cliente e eficiência operacional. No iFood, como Diretor de Operações, liderei 240 pessoas e budget de R$300MM/ano. Na wehandle, como Head de Operações, reduzi custo por atendimento em 13%, com SLA 95%. Busco posição de VP de Serviços & Operações."
        ),

        espaco(8),

        secao("Experiência"),
        espaco(3),
        cargoParagraph("Head de Operações", "wehandle", "Mai 2024 – Fev 2026"),
        bullet([
          { text: "Fui responsável por liderar a operação de suporte e " },
          { text: "Customer Service", bold: true },
          { text: " da wehandle, com time de 30 pessoas, gestão de " },
          { text: "Service Delivery", bold: true },
          { text: ", SLA, CSAT, TME, custo de atendimento e interface com Produto para priorização de bugs e melhorias." },
        ]),
        bullet([
          { text: "Estruturei " },
          { text: "Operational Transformation", bold: true },
          { text: " com migração para Zendesk, automação com chatbot/IA, canal WhatsApp e dados via API/Metabase, conduzindo gestão de mudança sem depender integralmente da área de dados." },
        ]),
        bullet([
          { text: "Reduzi o custo por atendimento de R$ 4,14 para " },
          { text: "R$ 3,61 (−13%)", bold: true },
          { text: ", elevei CSAT de 85% para " },
          { text: "92%", bold: true },
          { text: ", mantive " },
          { text: "SLA Management", bold: true },
          { text: " em 95% dos tickets e impactei a margem bruta em " },
          { text: "15%", bold: true },
          { text: "." },
        ]),

        espaco(6),

        cargoParagraph("Diretor de Operações", "iFood", "Abr 2022 – Mar 2024"),
        bullet([
          { text: "Fui responsável por FieldOps, Meios de Pagamento e Novos Negócios, liderando até " },
          { text: "240 pessoas", bold: true },
          { text: " e gestão orçamentária de " },
          { text: "R$300MM/ano", bold: true },
          { text: " na linha de custo das entregas." },
        ]),
        bullet([
          { text: "Conduzi S&OP executivo mensal, governança com C-level, leitura de DRE executiva e decisões de custo, nível de serviço, disponibilidade de frota, cobertura e expansão." },
        ]),
        bullet([
          { text: "Ampliei a cobertura logística de 400 para " },
          { text: "800 cidades", bold: true },
          { text: ", conduzi redução de custos com ganho comparável de " },
          { text: "3% YoY", bold: true },
          { text: ", aumentei entregas agrupadas de 12% para " },
          { text: "25%", bold: true },
          { text: " e mantive estabilidade de SLA." },
        ]),

        espaco(6),

        cargoParagraph("Head de Operações", "iFood", "Nov 2018 – Mar 2022"),
        bullet([
          { text: "Fui responsável por liveOps, regionalOps, pricing, modelagem de dados e planejamento de frota, liderando " },
          { text: "28 pessoas", bold: true },
          { text: " em operação logística de alta escala e tomada de decisão em tempo real." },
        ]),
        bullet([
          { text: "Criei simuladores, dashboards em Grafana e modelos com SQL, Databricks, Python e Tableau para capacity planning, balanceamento de frota e gestão de nível de serviço." },
        ]),
        bullet([
          { text: "Gerei saving de " },
          { text: "R$70MM/ano", bold: true },
          { text: " com simulador proprietário, reduzi cancelamentos no México em " },
          { text: "60%", bold: true },
          { text: " e reduzi custo de distribuição de MPOS em " },
          { text: "80%", bold: true },
          { text: ", com prazo de 14 para 2 dias." },
        ]),

        espaco(6),

        cargoParagraph("Gerente de Planejamento Comercial e Operações", "VivaReal", "Mai 2015 – Dez 2017"),
        bullet([
          { text: "Fui responsável por planejamento comercial, operações e qualidade no VivaReal, liderando " },
          { text: "33 pessoas", bold: true },
          { text: " e 5 lideranças em qualidade, SDR e cadastro, com interface direta com CFO, Comercial e Produto." },
        ]),
        bullet([
          { text: "Desenhei a jornada e a régua de onboarding, fui arquiteto da área de CS que escalou para " },
          { text: "91 pessoas", bold: true },
          { text: " sob gestão de outros e estruturei indicadores, cadências e priorização de roadmap com Produto." },
        ]),
        bullet([
          { text: "Elevei a conversão SDR inbound de 18% para " },
          { text: "50%", bold: true },
          { text: ", reduzi custo de vendas em " },
          { text: "40%", bold: true },
          { text: ", mantive churn abaixo de 3% ao mês, NPS em 80 e CSAT acima de 92%." },
        ]),

        espaco(6),

        cargoParagraph("Coordenador de S&OP", "Scalina (Trifil)", "Jan 2010 – Set 2014"),
        bullet([
          { text: "Fui responsável por criar e sustentar a área de S&OP por " },
          { text: "4 anos", bold: true },
          { text: ", gerindo 40K SKUs em duas marcas, OTIF, fill rate, forecast, MRP, S&OE, outsourcing e indicadores executivos reportados ao CEO." },
        ]),
        bullet([
          { text: "Implantei governança de KPIs, simuladores em Excel/VBA, análise de capacidade, cenários de abastecimento e ritos entre comercial, PCP, compras e diretoria para decisões de custo e atendimento." },
        ]),
        bullet([
          { text: "Reduzi " },
          { text: "R$8MM", bold: true },
          { text: " de GGF, gerei economia real de " },
          { text: "R$4,6MM", bold: true },
          { text: " acima da meta até agosto e sustentei o Projeto Entrega Certa com OTIF, fill rate, giro de estoque e produtividade da expedição." },
        ]),

        espaco(8),

        secao("Formação"),
        espaco(3),
        paragrafo("ILead Liderança para Líder de Líderes — Fundação Dom Cabral (2021)"),
        paragrafo("Six Sigma Green Belt — Setec Consulting (2020)"),
        paragrafo("MBA Corporate Strategy — BSP Business School São Paulo (2016–2017)"),
        paragrafo("Engenheiro Químico — Faculdades Oswaldo Cruz (2014)"),

        espaco(8),

        secao("Stack técnica"),
        espaco(3),
        paragrafo("SQL · Python · Databricks · Tableau · Metabase · Zendesk · Salesforce · Power BI · Excel/VBA · WMS · ERP Infor LN"),

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
