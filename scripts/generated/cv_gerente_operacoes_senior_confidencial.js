const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, TabStopPosition, TabStopType,
  ExternalHyperlink, LevelFormat, AlignmentType, BorderStyle, PageOrientation
} = require("docx");

// Font helpers
const pt = n => n * 2;

// Section line with bottom border
function secao(text) {
  return new Paragraph({
    children: [new TextRun({ text, size: pt(12), font: "Arial" })],
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "000000", space: 1 } },
    spacing: { before: pt(6), after: pt(3) }
  });
}

// Spacer
function espaco(ptSize = 6) {
  return new Paragraph({
    children: [new TextRun({ text: "", size: pt(ptSize), font: "Arial" })],
    spacing: { after: 0 }
  });
}

// Cargo with right-aligned period via tab
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

// Bullet with array of runs [{ text, bold }]
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

// Header link function
function headerLink(text, url) {
  return new ExternalHyperlink({
    children: [new TextRun({ text, style: "Hyperlink", size: pt(9), font: "Arial" })],
    link: url
  });
}

// Header line with a single piece of inline content (link or text)
function headerLine(children) {
  return new Paragraph({
    children,
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
      // Header
      new Paragraph({
        children: [new TextRun({ text: "Felipe Armel Dias da Silva", bold: true, size: pt(12), font: "Arial" })],
        spacing: { after: 0 }
      }),
      headerLine([
        headerLink("linkedin.com/in/felipearmel", "https://linkedin.com/in/felipearmel")
      ]),
      headerLine([
        new TextRun({ text: "São Paulo, SP", size: pt(9), font: "Arial" })
      ]),
      headerLine([
        headerLink("(11) 98674-8218", "https://wa.me/5511986748218")
      ]),
      headerLine([
        headerLink("armelfelipe@gmail.com", "mailto:armelfelipe@gmail.com")
      ]),
      espaco(4),

      // Resumo (476 chars)
      secao("Resumo"),
      espaco(3),
      new Paragraph({
        children: [new TextRun({
          text: "Executivo sênior com formação em Engenharia Química e MBA em Corporate Strategy. No iFood, como Diretor de Operações, liderei orçamento de R$300MM/ano e 240 pessoas — P&L, SLAs e S&OP executivo. Como Head, criei simulador com saving de R$70MM/ano. Antes, estruturei centros de distribuição com gestão de estoques e KPIs logísticos. Busco posição de Gerente de Operações Sênior.",
          size: pt(9), font: "Arial"
        })],
        spacing: { after: 0 }
      }),
      espaco(8),

      // Experiência
      secao("Experiência"),
      espaco(3),

      // WeHandle
      cargoParagraph("Head de Operações", "WeHandle", "Mai 2024 – Fev 2026"),
      bullet([
        { text: "Fui responsável pela operação de suporte ao cliente com equipe de 30 pessoas, reestruturando processos e indicadores para escalar o atendimento com qualidade e eficiência de custos." }
      ]),
      bullet([
        { text: "Conduzi a migração para plataforma de atendimento IA first, implantei canal de WhatsApp (produtividade +25%) e integrei dados de atendimento ao datalake via API para dashboards em Metabase." }
      ]),
      bullet([
        { text: "Reduzi o custo por atendimento de R$4,14 para R$3,61, elevei o CSAT de " },
        { text: "85% para 92%", bold: true },
        { text: " e o SLA para " },
        { text: "95%", bold: true },
        { text: " dos tickets, e reduzi o TME de 20 para 8 minutos." }
      ]),
      espaco(6),

      // iFood Diretor
      cargoParagraph("Diretor de Operações", "iFood", "Abr 2022 – Mar 2024"),
      bullet([
        { text: "Fui responsável pela gestão de operações logísticas com orçamento de " },
        { text: "R$300MM/ano", bold: true },
        { text: " e equipe de 240 pessoas, acumulando FieldOps, Meios de Pagamento e Novos Negócios, com P&L e S&OP executivo mensal reportado ao C-level, assegurando a performance financeira das operações." }
      ]),
      bullet([
        { text: "Liderei o planejamento integrado com modelagem em Python, SQL e Databricks, capacity planning de frota por cidade e trade-offs entre custo logístico e SLAs para ~30M pedidos/mês." }
      ]),
      bullet([
        { text: "Ampliei a cobertura logística de " },
        { text: "400 para 800 cidades", bold: true },
        { text: ", reduzi o custo comparável em " },
        { text: "3% YoY", bold: true },
        { text: ", reduzi a indisponibilidade da frota de " },
        { text: "5% para 1%", bold: true },
        { text: " e mantive o controle de custos dentro do orçamento." }
      ]),
      espaco(6),

      // iFood Head
      cargoParagraph("Head de Operações", "iFood", "Nov 2018 – Mar 2022"),
      bullet([
        { text: "Fui responsável por equipe de 28 pessoas nas áreas de liveOps, pricing logístico e planejamento de frota, implementando processos também na subsidiária do México." }
      ]),
      bullet([
        { text: "Criei métricas em tempo real no Grafana, modelei dados com SQL e Databricks para decisões de pricing e projetei simulador de nível de serviço." }
      ]),
      bullet([
        { text: "Gerei saving de " },
        { text: "R$70MM/ano", bold: true },
        { text: " com o simulador de nível de serviço, reduzi o custo de distribuição de MPOS em " },
        { text: "80%", bold: true },
        { text: " (lead time 14→2 dias) e cortei cancelamentos em " },
        { text: "60%", bold: true },
        { text: " no México." }
      ]),
      espaco(6),

      // Trifil
      cargoParagraph("Coordenador de S&OP", "Trifil", "Jan 2006 – Set 2014"),
      bullet([
        { text: "Fui responsável pela gestão dos centros de distribuição e pela criação da área de S&OP do zero, gerenciando " },
        { text: "40K SKUs", bold: true },
        { text: " em duas marcas com reporte direto ao CEO." }
      ]),
      bullet([
        { text: "Estruturei o CD com endereçamento de estoque, coletores RF e WMS — elevando a acurácia de armazenagem de 85% para 98%, conduzi strategic sourcing de 150K+ SKUs (" },
        { text: "-27% compras", bold: true },
        { text: ") e implantei sistema de tinturaria automatizada (" },
        { text: "-40% custos", bold: true },
        { text: ")." }
      ]),
      bullet([
        { text: "Reduzi perdas e refugos em " },
        { text: "30%", bold: true },
        { text: ", aumentei a produtividade em " },
        { text: "35%", bold: true },
        { text: ", reduzi GGF em " },
        { text: "R$4,6M", bold: true },
        { text: " com controle de custos estruturado e implantei KPIs de OTIF e fill rate como indicadores logísticos reportados ao CEO." }
      ]),
      espaco(8),

      // Formação
      secao("Formação"),
      espaco(3),
      bullet([
        { text: "MBA Corporate Strategy — BSP Business School São Paulo (2017)" }
      ]),
      bullet([
        { text: "Engenharia Química — Faculdades Oswaldo Cruz (2014)" }
      ]),
      espaco(8),

      // Stack Técnica
      secao("Stack técnica"),
      espaco(3),
      new Paragraph({
        children: [new TextRun({
          text: "Python · SQL · Databricks · Grafana · Metabase · Excel/VBA · WMS · ERP Infor LN",
          size: pt(9), font: "Arial"
        })],
        spacing: { after: 0 }
      }),
      espaco(8),

      // Idiomas
      secao("Idiomas"),
      espaco(3),
      bullet([{ text: "Português — Nativo" }]),
      bullet([{ text: "Inglês — Avançado" }])
    ]
  }]
});

Packer.toBuffer(doc).then(buffer => {
  const outPath = "outputs/_tmp/cv_gerente_operacoes_senior_confidencial.docx";
  fs.writeFileSync(outPath, buffer);
  console.log("ok");
});
