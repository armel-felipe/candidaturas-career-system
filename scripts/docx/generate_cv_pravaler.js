const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, ExternalHyperlink,
  TabStopType, TabStopPosition, AlignmentType,
  LevelFormat, BorderStyle, HeadingLevel, PageBreak
} = require("docx");

// half-points: 9pt = 18, 12pt = 24
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
      new TextRun({ text: `${cargo} \u2014 ${empresa}`, bold: true, size: pt(9), font: "Arial" }),
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

function linkParagraph(url, label) {
  return new Paragraph({
    children: [
      new ExternalHyperlink({
        children: [new TextRun({ text: label, style: "Hyperlink", size: pt(9), font: "Arial" })],
        link: url
      })
    ],
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
      linkParagraph("https://linkedin.com/in/felipearmel", "linkedin.com/in/felipearmel"),
      new Paragraph({
        children: [new TextRun({ text: "São Paulo, SP", size: pt(9), font: "Arial" })],
        spacing: { after: 0 }
      }),
      linkParagraph("https://wa.me/5511986748218", "(11) 98674-8218"),
      linkParagraph("mailto:armelfelipe@gmail.com", "armelfelipe@gmail.com"),

      espaco(8),

      // Resume
      secao("Resumo"),
      espaco(3),
      new Paragraph({
        children: [new TextRun({
          text: "Executivo com 20 anos em operações digitais e transformação de negócios em marketplace e tecnologia. No iFood, como Diretor de Operações, liderei 240 pessoas com budget de R$ 300 MM/ano e expandi a logística de 400 para 800 cidades (30 milhões de pedidos/mês), conectando planejamento estratégico, pricing e eficiência para proteger EBITDA. Como Head na WeHandle, reestruturei operação do zero com impacto de 15% na margem bruta conectando dados via API própria. Busco posição de Gerente de Planejamento Comercial.",
          size: pt(9), font: "Arial"
        })],
        spacing: { after: 0 }
      }),

      espaco(8),

      // Experience
      secao("Experiência"),
      espaco(3),

      // WeHandle
      cargoParagraph("Head de Operações", "wehandle", "Mai 2024 – Fev 2026"),
      bullet([
        { text: "Fui responsável por liderar a operação de suporte com time de 30 pessoas, reestruturando processos com impacto de 15% na margem bruta por meio de automação, segmentação de clientes e novos canais digitais." }
      ]),
      bullet([
        { text: "Conectei API própria nas plataformas de atendimento (Movidesk, CloudHumans, Zendesk), ficando 3 meses à frente da área de dados com indicadores em tempo real usando SQL e Python." }
      ]),
      bullet([
        { text: "Reduzi o custo por atendimento de R$ 4,14 para R$ 3,61 (−13%) ao implantar WhatsApp como canal principal, elevando o CSAT de 85% para ", bold: false },
        { text: "92%", bold: true },
        { text: " e o SLA para 95% dos tickets." }
      ]),
      espaco(6),

      // iFood Diretor
      cargoParagraph("Diretor de Operações", "iFood", "Abr 2022 – Mar 2024"),
      bullet([
        { text: "Fui responsável por gerir operações logísticas com equipe de 240 pessoas e budget de ", bold: false },
        { text: "R$ 300 MM/ano", bold: true },
        { text: ", conduzindo S&OP executivo mensal consolidando demanda, custos e trade-offs de EBITDA." }
      ]),
      bullet([
        { text: "Liderei o planejamento estratégico com Databricks, SQL e Tableau, conectando expansão geográfica, pricing de frota e disponibilidade de meios de pagamento em um processo único de governança." }
      ]),
      bullet([
        { text: "Ampliei cobertura de 400 para 800 cidades, implantei meios de pagamento (MPOS) em 352 cidades com zero perda financeira e reduzi custo logístico comparável em ", bold: false },
        { text: "3% YoY", bold: true },
        { text: "." }
      ]),
      espaco(6),

      // iFood Head
      cargoParagraph("Head de Operações", "iFood", "Nov 2018 – Mar 2022"),
      bullet([
        { text: "Fui responsável por estruturar as áreas de liveOps, regionalOps, pricing e modelagem de dados com equipe de 28 pessoas, criando a inteligência operacional da logística do iFood." }
      ]),
      bullet([
        { text: "Modelei dados com SQL, Databricks e Grafana, criando métricas em tempo real que correlacionavam saturação logística com metas de entrega e disponibilidade de frota." }
      ]),
      bullet([
        { text: "Criei simulador de nível de serviço que gerou saving de ", bold: false },
        { text: "R$ 70 MM/ano", bold: true },
        { text: " e expandi a distribuição de MPOS reduzindo custo em 80% e tempo de entrega de 14 para 2 dias." }
      ]),
      espaco(6),

      // VivaReal
      cargoParagraph("Gerente de Planejamento Comercial e Operações", "VivaReal", "Mai 2015 – Dez 2017"),
      bullet([
        { text: "Fui business partner da diretoria comercial: desdobramento de metas, precificação, comissionamento e gestão de carteiras de clientes, com interface direta com CFO." }
      ]),
      bullet([
        { text: "Estruturei dashboards em SQL e Excel automatizado para monitorar churn, NPS e CSAT, suportando decisões de produto e vendas com dados atualizados diariamente." }
      ]),
      bullet([
        { text: "Aumentei a conversão SDR inbound de ", bold: false },
        { text: "18% para 50%", bold: true },
        { text: " e fui arquiteto da área de CS que escalou para 91 pessoas, mantendo churn abaixo de 3% ao mês." }
      ]),
      espaco(6),

      // Trifil
      cargoParagraph("Coordenador de S&OP", "Trifil (Scalina)", "Jan 2010 – Set 2014"),
      bullet([
        { text: "Fui responsável por criar e sustentar a área de S&OP por 4 anos, gerenciando 40 mil SKUs com coordenação entre comercial e fabricação, e redução de ", bold: false },
        { text: "R$ 8 MM em GGF", bold: true },
        { text: "." }
      ]),
      bullet([
        { text: "Modelei simuladores de MRP em Excel VBA para validação de cenários de S&OP, otimizando estoques de segurança com trade-offs entre liquidez e nível de serviço." }
      ]),
      bullet([
        { text: "Criei a área de Inteligência Comercial do zero, reduzindo relatórios de vendas de 4h para 14min e suportando aumento de faturamento de ", bold: false },
        { text: "R$ 80 MM para R$ 120 MM/ano", bold: true },
        { text: "." }
      ]),

      espaco(8),

      // Education
      secao("Formação"),
      espaco(3),
      bullet([
        { text: "MBA Corporate Strategy — BSP Business School São Paulo (2017)" }
      ]),
      bullet([
        { text: "Engenharia Química — Faculdades Oswaldo Cruz (2014)" }
      ]),

      espaco(8),

      // Technical Stack
      secao("Stack técnica"),
      espaco(3),
      new Paragraph({
        children: [new TextRun({
          text: "Excel/VBA · SQL · Python · PySpark · Databricks · Grafana · Power BI · Tableau · Metabase · Salesforce · Zendesk · ERP Infor LN",
          size: pt(9), font: "Arial"
        })],
        spacing: { after: 0 }
      }),

      espaco(8),

      // Skills
      secao("Competências"),
      espaco(3),
      new Paragraph({
        children: [new TextRun({
          text: "Planejamento Estratégico · Business Partners · BI/Dados · Soluções Comerciais · Produtos Financeiros · Inteligência Comercial · KPI · Análise de Dados · Gestão de Carteiras · Performance Comercial · Liderança de Equipe · S&OP · Power BI · SQL · Comunicação com Liderança",
          size: pt(9), font: "Arial"
        })],
        spacing: { after: 0 }
      }),

      espaco(8),

      // Languages
      secao("Idiomas"),
      espaco(3),
      bullet([
        { text: "Português — Nativo" }
      ]),
      bullet([
        { text: "Inglês — Avançado" }
      ])
    ]
  }]
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync("outputs/_tmp/cv_pravaler.docx", buffer);
  console.log("ok");
});
