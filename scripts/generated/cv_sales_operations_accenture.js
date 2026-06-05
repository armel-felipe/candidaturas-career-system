const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, ExternalHyperlink,
  TabStopType, TabStopPosition, LevelFormat, AlignmentType,
  BorderStyle
} = require("docx");

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
    children: [new TextRun({ text: "", size: pt(ptSize), font: "Arial" })],
    spacing: { after: 0 }
  });
}

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
      new Paragraph({
        children: [
          new ExternalHyperlink({
            children: [new TextRun({ text: "linkedin.com/in/felipearmel", size: pt(9), font: "Arial", style: "Hyperlink" })],
            link: "https://linkedin.com/in/felipearmel"
          })
        ],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [new TextRun({ text: "São Paulo, SP", size: pt(9), font: "Arial" })],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [
          new ExternalHyperlink({
            children: [new TextRun({ text: "(11) 98674-8218", size: pt(9), font: "Arial", style: "Hyperlink" })],
            link: "https://wa.me/5511986748218"
          })
        ],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [
          new ExternalHyperlink({
            children: [new TextRun({ text: "armelfelipe@gmail.com", size: pt(9), font: "Arial", style: "Hyperlink" })],
            link: "mailto:armelfelipe@gmail.com"
          })
        ],
        spacing: { after: 0 }
      }),

      espaco(8),

      // Section: Resumo (≤480 chars)
      secao("Resumo"),
      espaco(3),
      new Paragraph({
        children: [
          new TextRun({
            text: "Executivo sênior com 20+ anos em operações e transformação. No iFood, como Diretor, liderei 240 pessoas e budget de R$300MM — reduzi custo em 3% YoY e conduzi o S&OP executivo com C-level. Gerei saving de R$70MM/ano com simulador proprietário. Na WeHandle, reestruturei a operação com 15% de impacto na margem bruta. Busco posição de Sales Operations.",
            size: pt(9), font: "Arial"
          })
        ],
        spacing: { after: 0 }
      }),

      espaco(8),

      // Section: Experiência
      secao("Experiência"),
      espaco(3),

      // --- WeHandle ---
      cargoParagraph("Head de Operações", "wehandle", "Mai 2024 – Fev 2026"),
      bullet([
        { text: "Fui responsável por reestruturar a operação de suporte com time de 30 pessoas, liderando duas migrações de plataforma e implantando automação com IA e eficiência operacional em toda a cadeia de atendimento." }
      ]),
      bullet([
        { text: "Estruturei processos de segmentação de carteira, canais omnichannel e integração de dados via API com Python e SQL, conectando atendimento ao datalake e reduzindo backlog em 60%." }
      ]),
      bullet([
        { text: "Reduzi custo por atendimento em ", bold: false },
        { text: "13% (R$4,14 para R$3,61)", bold: true },
        { text: ", gerei ", bold: false },
        { text: "15% de impacto na margem bruta", bold: true },
        { text: " e elevei CSAT de 85% para 92% com SLA em 95% dos tickets." }
      ]),
      espaco(6),

      // --- iFood Diretor ---
      cargoParagraph("Diretor de Operações", "iFood", "Abr 2022 – Mar 2024"),
      bullet([
        { text: "Fui responsável pela gestão de operações logísticas com equipe de ~240 pessoas e budget de ", bold: false },
        { text: "R$300MM/ano", bold: true },
        { text: ", liderando a revisão de negócios mensal (S&OP executivo) com C-level e trade-offs entre custo e nível de serviço." }
      ]),
      bullet([
        { text: "Conduzi o planejamento integrado com forecast de demanda, conectando marketing, promoções, frota e supply com modelagem em Python e Databricks para tomada de decisão baseada em dados." }
      ]),
      bullet([
        { text: "Ampliei cobertura de 400 para 800 cidades, reduzi custo comparável em ", bold: false },
        { text: "3% YoY", bold: true },
        { text: ", indisponibilidade de frota de 5% para 1% e pedidos agrupados de 12% para 25%." }
      ]),
      espaco(6),

      // --- iFood Head ---
      cargoParagraph("Head de Operações", "iFood", "Nov 2018 – Mar 2022"),
      bullet([
        { text: "Fui responsável por liderar equipe de 28 pessoas nas áreas de liveOps, pricing, modelagem de dados e planejamento de frota, estruturando operação para escala de marketplace com melhoria contínua dos processos." }
      ]),
      bullet([
        { text: "Desenvolvi simulador proprietário de nível de serviço e ferramentas de restrição de raio por bairro, combinando métricas em tempo real no Grafana com análise em SQL e Databricks." }
      ]),
      bullet([
        { text: "Gerei ", bold: false },
        { text: "saving de R$70MM/ano", bold: true },
        { text: " com o simulador, reduzi custo de distribuição de MPOS em 80% e prazo de 14 para 2 dias, e implementei torre de operações no México reduzindo cancelamentos em 60%." }
      ]),
      espaco(6),

      // --- VivaReal ---
      cargoParagraph("Gerente de Planejamento Comercial e Operações", "VivaReal", "Mai 2015 – Dez 2017"),
      bullet([
        { text: "Fui responsável pela gestão de 33 pessoas com 5 lideranças diretas nas áreas de SDR e qualidade, e arquiteto da área de Customer Success que escalou para 91 pessoas, com treinamento e capacitação contínua das equipes." }
      ]),
      bullet([
        { text: "Estruturei a esteira de leads inbound definindo tempo ideal de contato, integrei Salesforce para gestão de pipeline de vendas e implantei processo de SDR com métricas de conversão." }
      ]),
      bullet([
        { text: "Ampliei conversão inbound de ", bold: false },
        { text: "18% para 50%", bold: true },
        { text: ", reduzindo custo de vendas em 40%, e recuperei R$1M em inadimplentes com campanha estruturada." }
      ]),
      espaco(6),

      // --- Trifil ---
      cargoParagraph("Coordenador de S&OP | Supply Chain", "Scalina (Trifil)", "Jan 2006 – Set 2014"),
      bullet([
        { text: "Criei a área de S&OP do zero e sustentei os ritos por 4 anos com gestão de processos e melhoria contínua, gerenciando 40 mil SKUs em duas marcas com reporte direto ao CEO." }
      ]),
      bullet([
        { text: "Desenvolvi sistemas em Excel e VBA para alocação de estoque, simulação de MRP e análise de cenários; automatizei relatórios que passaram de 4h para 14min de produção." }
      ]),
      bullet([
        { text: "Reduzi ", bold: false },
        { text: "R$8MM em Gastos Gerais de Fabricação", bold: true },
        { text: ", implantei Strategic Sourcing em 150 mil SKUs com -27% no custo de compras e elevei acurácia de estoque de 85% para 98%." }
      ]),
      espaco(8),

      // Section: Formação
      secao("Formação"),
      espaco(3),
      new Paragraph({
        children: [
          new TextRun({ text: "MBA Corporate Strategy — BSP Business School São Paulo (2017)", size: pt(9), font: "Arial" }),
        ],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [
          new TextRun({ text: "Engenharia Química — Faculdades Oswaldo Cruz (2014)", size: pt(9), font: "Arial" }),
        ],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [
          new TextRun({ text: "Six Sigma Green Belt — Setec Consulting (2020)", size: pt(9), font: "Arial" }),
        ],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [
          new TextRun({ text: "Liderança para Líder de Líderes — Fundação Dom Cabral (2021)", size: pt(9), font: "Arial" }),
        ],
        spacing: { after: 0 }
      }),

      espaco(8),

      // Section: Stack Técnica
      secao("Stack técnica"),
      espaco(3),
      new Paragraph({
        children: [
          new TextRun({ text: "Excel/VBA · SQL · Python · Databricks · Grafana · Salesforce · Zendesk · Power BI · Tableau", size: pt(9), font: "Arial" }),
        ],
        spacing: { after: 0 }
      }),

      espaco(8),

      // Section: Idiomas
      secao("Idiomas"),
      espaco(3),
      bullet([{ text: "Português — Nativo" }]),
      bullet([{ text: "Inglês — Avançado" }]),
    ]
  }]
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync("outputs/_tmp/cv_sales_operations_accenture.docx", buffer);
  console.log("ok");
});
