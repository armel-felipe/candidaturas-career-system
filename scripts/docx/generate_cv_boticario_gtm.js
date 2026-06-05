const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, ExternalHyperlink,
  TabStopType, TabStopPosition, AlignmentType,
  LevelFormat, BorderStyle
} = require("docx");

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
          text: "Executivo com 20 anos em operações digitais, planejamento estratégico e gestão de canais em marketplace e indústria de grande escala. No iFood, como Diretor de Operações, liderei o S&OP executivo com budget de R$300MM/ano e 240 pessoas, conectando estratégia, operação e trade-offs em escala regional. Na Trifil, gerenciei 40 mil SKUs em 4 canais de distribuição com inteligência comercial e S&OP. Busco posição de Gerente de Planejamento e Execução GTM.",
          size: pt(9), font: "Arial"
        })],
        spacing: { after: 0 }
      }),

      espaco(8),

      // Experience
      secao("Experiência"),
      espaco(3),

      // WeHandle
      cargoParagraph("Head de Operações", "wehandle", "Mai 2024 \u2013 Fev 2026"),
      bullet([
        { text: "Fui responsável por liderar a operação de suporte com time de 30 pessoas, reestruturando processos com impacto de 15% na margem bruta por meio de automação, segmentação de clientes e novos canais digitais." }
      ]),
      bullet([
        { text: "Conectei API própria nas plataformas de atendimento (Movidesk, CloudHumans, Zendesk), ficando 3 meses à frente da área de dados com indicadores em tempo real usando SQL e Python." }
      ]),
      bullet([
        { text: "Reduzi o custo por atendimento de R$ 4,14 para R$ 3,61 (\u221213%) ao implantar WhatsApp como canal principal, elevando o CSAT de 85% para ", bold: false },
        { text: "92%", bold: true },
        { text: "." }
      ]),
      espaco(6),

      // iFood Diretor
      cargoParagraph("Diretor de Operações", "iFood", "Abr 2022 \u2013 Mar 2024"),
      bullet([
        { text: "Fui responsável por gerir operações logísticas com equipe de 240 pessoas e budget de ", bold: false },
        { text: "R$ 300 MM/ano", bold: true },
        { text: ", conduzindo S&OP executivo mensal consolidando demanda, custos e trade-offs de EBITDA." }
      ]),
      bullet([
        { text: "Liderei o planejamento estratégico com Databricks, SQL e Tableau, conectando expansão geográfica, pricing de frota e canais de distribuição em visão única de governança." }
      ]),
      bullet([
        { text: "Ampliei cobertura de 400 para 800 cidades, implantei meios de pagamento em 352 cidades com zero perda financeira e reduzi custo logístico comparável em ", bold: false },
        { text: "3% YoY", bold: true },
        { text: "." }
      ]),
      espaco(6),

      // iFood Head
      cargoParagraph("Head de Operações", "iFood", "Nov 2018 \u2013 Mar 2022"),
      bullet([
        { text: "Fui responsável por estruturar as áreas de liveOps, regionalOps, pricing e modelagem de dados com equipe de 28 pessoas, criando a inteligência operacional da logística com métricas em tempo real." }
      ]),
      bullet([
        { text: "Modelei dados com SQL, Databricks e Grafana, correlacionando saturação logística com metas de entrega e disponibilidade de frota por região." }
      ]),
      bullet([
        { text: "Criei simulador de nível de serviço que gerou saving de ", bold: false },
        { text: "R$ 70 MM/ano", bold: true },
        { text: " e otimizei a distribuição de MPOS reduzindo custo em 80% e tempo de entrega de 14 para 2 dias." }
      ]),
      espaco(6),

      // VivaReal
      cargoParagraph("Gerente de Planejamento Comercial e Operações", "VivaReal", "Mai 2015 \u2013 Dez 2017"),
      bullet([
        { text: "Fui business partner da diretoria comercial: desdobramento de metas, precificação, comissionamento e gestão de carteiras de clientes, com interface direta com CFO." }
      ]),
      bullet([
        { text: "Estruturei dashboards em SQL e Excel automatizado para monitorar churn, NPS e CSAT, suportando decisões de produto e vendas com dados atualizados diariamente." }
      ]),
      bullet([
        { text: "Aumentei a conversão SDR inbound de ", bold: false },
        { text: "18% para 50%", bold: true },
        { text: " e mantive churn abaixo de 3% ao mês, estruturando métricas de performance comercial por canal." }
      ]),
      espaco(6),

      // Trifil
      cargoParagraph("Coordenador de S&OP", "Trifil (Scalina)", "Jan 2010 \u2013 Set 2014"),
      bullet([
        { text: "Fui responsável por criar e sustentar a área de S&OP por 4 anos, gerenciando 40 mil SKUs em canais de distribuidor, varejo, Key Accounts e franquias com coordenação entre comercial e fabricação." }
      ]),
      bullet([
        { text: "Modelei simuladores de MRP em Excel VBA e defini estoques de segurança por canal com trade-offs entre liquidez e nível de serviço, otimizando a disponibilidade multicanal." }
      ]),
      bullet([
        { text: "Criei a área de Inteligência Comercial do zero, reduzindo relatórios de vendas de 4h para 14min, e reduzi ", bold: false },
        { text: "R$ 8 MM em GGF", bold: true },
        { text: " com governança de planejamento." }
      ]),

      espaco(8),

      // Education
      secao("Formação"),
      espaco(3),
      bullet([{ text: "MBA Corporate Strategy \u2014 BSP Business School São Paulo (2017)" }]),
      bullet([{ text: "Engenharia Química \u2014 Faculdades Oswaldo Cruz (2014)" }]),

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
          text: "Go-to-Market (GTM) · Planejamento Estratégico · KPIs · Governança de Performance · Trade Canal · RGM (Revenue Growth Management) · Key Account · Canais Indiretos · Satisfação de Clientes · Relacionamento com Parceiros · Análise de Dados · Liderança de Times · Múltiplos Projetos · Políticas Comerciais · Metas e Resultados",
          size: pt(9), font: "Arial"
        })],
        spacing: { after: 0 }
      }),

      espaco(8),

      // Languages
      secao("Idiomas"),
      espaco(3),
      bullet([{ text: "Português — Nativo" }]),
      bullet([{ text: "Inglês — Avançado" }])
    ]
  }]
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync("outputs/_tmp/cv_boticario_gtm.docx", buffer);
  console.log("ok");
});
