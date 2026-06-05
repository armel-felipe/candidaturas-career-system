const docx = require("docx");
const fs = require("fs");
const path = require("path");

const {
  Document, Packer, Paragraph, TextRun, ExternalHyperlink,
  TabStopType, TabStopPosition, AlignmentType,
  BorderStyle, LevelFormat, HeadingLevel
} = docx;

// half-points — NUNCA n * 20
const pt = n => n * 2;

function secao(text) {
  return new Paragraph({
    children: [new TextRun({ text, size: pt(12), font: "Arial" })],
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "000000", space: 1 } },
    spacing: { before: pt(6), after: pt(3) }
  });
}

function espaco(ptSize = 6) {
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

function headerLink(text, url) {
  return new ExternalHyperlink({
    children: [new TextRun({ text, style: "Hyperlink", size: pt(9), font: "Arial" })],
    link: url
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
      // === HEADER ===
      new Paragraph({
        children: [new TextRun({ text: "Felipe Armel Dias da Silva", bold: true, size: pt(12), font: "Arial" })],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [headerLink("linkedin.com/in/felipearmel", "https://linkedin.com/in/felipearmel")],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [new TextRun({ text: "São Paulo, SP", size: pt(9), font: "Arial" })],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [headerLink("(11) 98674-8218", "https://wa.me/5511986748218")],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [headerLink("armelfelipe@gmail.com", "mailto:armelfelipe@gmail.com")],
        spacing: { after: 0 }
      }),
      espaco(8),

      // === RESUMO ===
      new Paragraph({
        children: [new TextRun({
          text: "Executivo sênior com mais de 6 anos de experiência em direção de operações logísticas em marketplace de tecnologia. No iFood, como Diretor de Operações, liderei equipe de 240 pessoas com budget de R$ 300 milhões/ano, expandi cobertura de 400 para 800 cidades e reduzi custo logístico comparável em 3% YoY. Como Head de Operações na WeHandle, liderei transformação organizacional que impactou 15% na margem bruta. Engenheiro Químico com MBA em Corporate Strategy. Busco posição de Diretor de Operações.",
          size: pt(9), font: "Arial"
        })],
        spacing: { after: 0 }
      }),
      espaco(8),

      // === EXPERIÊNCIA ===
      secao("Experiência"),
      espaco(3),

      // --- WeHandle ---
      cargoParagraph("Head de Operações", "wehandle", "Mai 2024 – Fev 2026"),
      bullet([
        { text: "Fui responsável por liderar a operação de suporte com time de 30 pessoas e conduzir a transformação organizacional da área, com impacto de ", bold: false },
        { text: "15% na margem bruta", bold: true },
        { text: " da companhia — resultado da reestruturação de processos, automação e canais.", bold: false }
      ]),
      bullet([
        { text: "Estruturei a área de CX integrando dados de atendimento ao datalake via API, implantei automação com IA e criei indicadores em tempo real com Metabase e Python para direcionar decisões de produto.", bold: false }
      ]),
      bullet([
        { text: "Reduzi o custo por atendimento de R$ 4,14 para R$ 3,61 (−13%), alcancei CSAT de 92% e SLA de 95%, reduzi o TME de 20 para 8 minutos e direcionei insights que reduziram o contact rate em 8%.", bold: false }
      ]),
      espaco(6),

      // --- iFood Diretor ---
      cargoParagraph("Diretor de Operações", "iFood", "Abr 2022 – Mar 2024"),
      bullet([
        { text: "Fui responsável pelo P&L de custo logístico com budget de ", bold: false },
        { text: "R$ 300 milhões/ano", bold: true },
        { text: " e liderança de equipe de ~240 pessoas, cobrindo FieldOps, Meios de Pagamento e Novos Negócios.", bold: false }
      ]),
      bullet([
        { text: "Liderei o S&OP executivo mensal de logística conectando marketing, promoções, clima, frota e operação em processo único de planejamento, com modelagem em Python, SQL e Databricks e indicadores em tempo real.", bold: false }
      ]),
      bullet([
        { text: "Ampliei cobertura de 400 para 800 cidades com expansão geográfica controlada, reduzi custo comparável em 3% YoY com ganho de eficiência operacional sustentável, elevei pedidos agrupados de 12% para 25% (breakeven) e reduzi indisponibilidade de frota de 5% para 1% (top 6 cidades: 5,4% para 0,5%).", bold: false }
      ]),
      espaco(6),

      // --- iFood Head ---
      cargoParagraph("Head de Operações", "iFood", "Nov 2018 – Mar 2022"),
      bullet([
        { text: "Fui responsável pela estruturação do planejamento de frota e pricing logístico, com equipe de 28 pessoas nas áreas de liveOps, modelagem de dados, regionalOps e planejamento.", bold: false }
      ]),
      bullet([
        { text: "Criei simulador de nível de serviço que gerou saving de ", bold: false },
        { text: "R$ 70 milhões/ano", bold: true },
        { text: " e implantei métricas em tempo real no Grafana correlacionando saturação logística, SLA e custo operacional.", bold: false }
      ]),
      bullet([
        { text: "Reduzi indisponibilidade de frota de 5,4% para 0,5% nas top 6 cidades, distribui MPOS em 352 cidades com zero perda financeira, e reduzi lead time de distribuição de 14 para 2 dias (−85%).", bold: false }
      ]),
      espaco(6),

      // --- VivaReal ---
      cargoParagraph("Gerente de Planejamento Comercial e Operações", "VivaReal", "Mai 2015 – Dez 2017"),
      bullet([
        { text: "Fui responsável pelas áreas de Qualidade, SDR e cadastro de imóveis com equipe de 33 pessoas, além do planejamento estratégico da empresa durante a fusão com o ZAP.", bold: false }
      ]),
      bullet([
        { text: "Fui arquiteto da área de CS: idealizei, desenhei processos, defini régua de onboarding e contratei liderança — a área escalou para ", bold: false },
        { text: "91 pessoas", bold: true },
        { text: " sob gestão de outros.", bold: false }
      ]),
      bullet([
        { text: "Aumentei conversão de SDR inbound de 18% para 50% (−40% custo de vendas), recuperei R$ 1 milhão em inadimplentes e mantive NPS de 80% com CSAT acima de 92%.", bold: false }
      ]),
      espaco(6),

      // --- Trifil ---
      cargoParagraph("Coordenador de S&OP", "Scalina (Trifil)", "Jan 2010 – Set 2014"),
      bullet([
        { text: "Fui responsável por criar a área de S&OP do zero, sustentando ritos por 4 anos com gestão de 40 mil SKUs em duas marcas (Trifil e Scala) e todos os canais de distribuição.", bold: false }
      ]),
      bullet([
        { text: "Estruturei o Projeto Entrega Certa com KPIs de OTIF, fill rate e acurácia de produção, e implantei simulador de MRP em Excel/VBA para validação de cenários e tomada de decisão.", bold: false }
      ]),
      bullet([
        { text: "Reduzi R$ 8 milhões de GGF do P&L otimizando energia, gás, manutenção e embalagens, e implantei Strategic Sourcing em 150 mil SKUs com redução de 27% no custo de compras e melhoria de giro de 8 para 6 meses.", bold: false }
      ]),
      espaco(8),

      // === FORMAÇÃO ===
      secao("Formação"),
      espaco(3),
      new Paragraph({
        children: [new TextRun({ text: "MBA Corporate Strategy — BSP Business School São Paulo (2017)", size: pt(9), font: "Arial" })],
        spacing: { after: pt(2) }
      }),
      new Paragraph({
        children: [new TextRun({ text: "Engenharia Química — Faculdades Oswaldo Cruz (2014)", size: pt(9), font: "Arial" })],
        spacing: { after: pt(2) }
      }),
      new Paragraph({
        children: [new TextRun({ text: "Six Sigma Green Belt — Setec Consulting (2020)", size: pt(9), font: "Arial" })],
        spacing: { after: 0 }
      }),
      espaco(8),

      // === STACK TÉCNICA ===
      secao("Stack técnica"),
      espaco(3),
      new Paragraph({
        children: [new TextRun({ text: "Python · SQL · PySpark · Databricks · Grafana · Metabase · Power BI · Tableau · Excel/VBA · ERP Infor LN · Salesforce · Zendesk", size: pt(9), font: "Arial" })],
        spacing: { after: 0 }
      }),
      espaco(8),

      // === IDIOMAS ===
      secao("Idiomas"),
      espaco(3),
      bullet([
        { text: "Português — Nativo", bold: false }
      ]),
      bullet([
        { text: "Inglês — Avançado", bold: false }
      ])
    ]
  }]
});

const outPath = "/Users/mac/llm server/projetos/candidaturas/outputs/_tmp/cv_diretor_operacoes_confidencial.docx";
Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync(outPath, buffer);
  console.log("ok");
});
