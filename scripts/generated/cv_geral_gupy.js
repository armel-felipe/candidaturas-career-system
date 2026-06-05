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

const workspace = process.env.CAREER_WORKSPACE || process.cwd();
const outputDir = process.env.CAREER_OUTPUTS || path.join(workspace, "outputs");
const tmpDir = path.join(outputDir, "_tmp");
const fitMapPath = path.join(workspace, ".career-state", "fit_map.json");

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

function linkParagraph(text, url) {
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

function textRunsFromMarkdown(text) {
  const runs = [];
  const parts = String(text).split("**");
  for (let i = 0; i < parts.length; i += 1) {
    if (!parts[i]) continue;
    runs.push({ text: parts[i], bold: i % 2 === 1 });
  }
  return runs;
}

function bulletText(text) {
  return bullet(textRunsFromMarkdown(text));
}

function stripSnake(text) {
  return String(text || "")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

const experiences = [
  {
    cargo: "Head de Operações",
    empresa: "wehandle",
    periodo: "Mai 2024 – Fev 2026",
    bullets: [
      "Fui responsável por **30** pessoas em suporte, Customer Experience e integrações, além de migração de plataformas e organização do backoffice.",
      "Implementei WhatsApp, Zendesk, automação com IA e integrações via API com Movidesk, CloudHumans e Zendesk, além de um board no ClickUp que reduziu o backlog de cards em **60%**.",
      "Reduzi o custo por atendimento de **R$4,14 para R$3,61**, gerei impacto de **15%** na margem bruta, elevei o CSAT de **85% para 92%**, mantive SLA de **95%** e reduzi o TME de **20 para 8 minutos**.",
    ],
  },
  {
    cargo: "Diretor de Operações",
    empresa: "iFood",
    periodo: "Abr 2022 – Mar 2024",
    bullets: [
      "Fui responsável por uma equipe de **240** pessoas entre FieldOps, Meios de Pagamento e Novos Negócios, com budget de **R$300MM/ano**.",
      "Liderei S&OP executivo, governança de planejamento, capacity planning, pricing logístico e Eficiência Operacional, com interface com produto, engenharia e marketing usando Python, SQL, Databricks e Tableau para suportar a decisão.",
      "Ampliei a cobertura de **400 para 800 cidades**, reduzi o custo comparável em **3% YoY**, reduzi a indisponibilidade da frota de **5% para 1%** e aumentei pedidos agrupados de **12% para 25%**.",
    ],
  },
  {
    cargo: "Head de Operações",
    empresa: "iFood",
    periodo: "Nov 2018 – Mar 2022",
    bullets: [
      "Fui responsável por uma equipe de **28** pessoas em liveOps, regionalOps, pricing, modelagem de dados e planejamento de frota.",
      "Estruturei Grafana, SQL, Databricks, Tableau, simulador de nível de serviço e planejamento de frota por cidade, conectando operação, dados e governança em tempo real.",
      "Reduzi cancelamentos em **60%** no México, gerei saving de **R$70MM/ano** e reduzi o custo de distribuição de MPOS em **80%** com prazo de **14 para 2 dias**.",
    ],
  },
  {
    cargo: "Gerente de Customer Success",
    empresa: "Renault do Brasil",
    periodo: "Jan 2018 – Out 2018",
    bullets: [
      "Fui responsável pela operação de CS e pela transição de **2 BPOs** com **40 PAs** para uma estrutura interna com **8** pessoas.",
      "Usei discadores, Excel/VBA e Power BI para qualificação, governança de SLA e plano de ação, com leitura objetiva de ROI e produtividade.",
      "Elevei a conversão de leads de **24% para 46%** e apresentei o projeto em **2 reuniões**, com ROI corretamente calculado e aprovado pela liderança.",
    ],
  },
  {
    cargo: "Gerente de Planejamento Comercial e Operações",
    empresa: "VivaReal",
    periodo: "Mai 2015 – Dez 2017",
    bullets: [
      "Fui responsável por planejamento comercial e operacional, com **33** pessoas e **5** lideranças diretas em qualidade, SDR e cadastro.",
      "Estruturei pricing, comissionamento, dashboards em SQL/Excel e a arquitetura da área de CS, que foi desenhada por mim sem que eu fosse gestor de CS.",
      "Ampliei a conversão inbound de **18% para 50%**, reduzi o custo de vendas em **40%**, mantive o churn abaixo de **3%/mês** e o CSAT acima de **92%**; a área de CS escalou para **91** pessoas sob gestão de outros.",
    ],
  },
  {
    cargo: "Coordenador de S&OP",
    empresa: "Scalina (Trifil)",
    periodo: "Jan 2010 – Set 2014",
    bullets: [
      "Fui responsável por criar a área de S&OP do zero e sustentar os ritos por **4** anos, gerenciando **40K** SKUs em **2** marcas e todos os canais, com forte Supply Chain Management.",
      "Estruturei MRP corporativo, safety stock, S&OE, outsourcing, capacity planning e um simulador em Excel/VBA para cenários de planejamento e execução.",
      "Reduzi **R$8MM** de GGF, gerei economia de **R$4,6MM** vs meta até agosto e sustentei o projeto Entrega Certa com OTIF e fill rate.",
    ],
  },
  {
    cargo: "Coordenador de Inteligência Comercial",
    empresa: "Scalina (Trifil)",
    periodo: "Jan 2009 – Dez 2009",
    bullets: [
      "Fui responsável por criar a área de inteligência comercial com **2** pessoas, tendências de mercado, oportunidades e indicadores para diretoria.",
      "Automatizei Business Intelligence, normalização de dados e precificação por mix, margem e alçadas, apoiando o planejamento comercial e a governança das vendas.",
      "Reduzi relatórios de **4h para 14min** e ampliei a receita de **R$80MM para R$120MM/ano** com alocação de estoque e apoio à tabela de preços.",
    ],
  },
  {
    cargo: "Coordenador de Planejamento de Materiais",
    empresa: "Scalina (Trifil)",
    periodo: "Nov 2007 – Dez 2008",
    bullets: [
      "Fui responsável por planejamento de materiais, strategic sourcing de **150K+** SKUs e compras de aviamentos, embalagens e fios.",
      "Dimensionei e conduzi a aquisição de **24** teares circulares automatizados, além de regras para o plano de produção e o período congelado.",
      "Reduzi o custo de compras em **27%**, a falta de produto em **40%**, o giro de estoque de **8 para 6 meses** e o custo total de fabricação em **15%**.",
    ],
  },
  {
    cargo: "Coordenador de Expedição",
    empresa: "Scalina (Trifil)",
    periodo: "Jan 2007 – Out 2007",
    bullets: [
      "Fui responsável pelo centro de expedição com picking, packing, armazenagem, devoluções e interface com Qualidade.",
      "Gerenciei o projeto Entrega Certa e implantei coletores RF e wi-fi, inventário rotativo, endereçamento, layout e módulo de expedição do ERP LN.",
      "Atingi **98%** de acuracidade de estoque, **35%** de ganho de produtividade, **30%** de redução de perdas e **50%** de redução no preparo de pedidos customizados.",
    ],
  },
  {
    cargo: "Analista de Processos e Sistemas",
    empresa: "Scalina (Trifil)",
    periodo: "Jan 2006 – Dez 2006",
    bullets: [
      "Fui responsável por implantar GPD com PDCA, KPIs, Automação de Processos, Melhoria Contínua e planos de ação em toda a planta Guarulhos.",
      "Conduzi a Gestão de Projetos da automação da tinturaria com estudo de viabilidade, seleção de fornecedor e implantação, usando análise financeira para sustentar a decisão.",
      "Reduzi **40%** dos custos de produção, gerei payback real de **1,5 ano** e melhorei a eficiência em **12%**.",
    ],
  },
  {
    cargo: "Coordenador de Produção - Químico",
    empresa: "VitaLabor Cosméticos",
    periodo: "Ago 2005 – Dez 2005",
    bullets: [
      "Fui responsável por qualidade, garantia da qualidade, compras e planejamento da produção em empresa de menor porte.",
      "Criei sistema automatizado em Excel para estoque, emissão de receitas e geração de lotes.",
      "Reduzi **80%** das paradas por falta de produto e ampliei em **80%** a utilização da capacidade instalada.",
    ],
  },
  {
    cargo: "Supervisor de Produção: Manipulação e Pesagem",
    empresa: "Pierre Alexander Cosméticos",
    periodo: "Ago 2003 – Jul 2005",
    bullets: [
      "Fui responsável por time de **10** pessoas na manipulação e pesagem e pelo almoxarifado de matérias-primas.",
      "Implantei ERP Logix, sistema de inventário em Excel e algoritmo de programação diária dos misturadores.",
      "Aumentei a produtividade em **13%**, reduzi perdas por contaminação em **20%** e cortei **1 dia** do inventário.",
    ],
  },
  {
    cargo: "Coordenador do Sistema de Garantia da Qualidade",
    empresa: "Resinor",
    periodo: "Mai 2002 – Jul 2003",
    bullets: [
      "Fui responsável sozinho pelo sistema de garantia da qualidade e por mais de **300** documentos sob conformidade.",
      "Migrei a norma com **0 não conformidades**, mantendo controle documental, treinamento e rotina de auditoria líder.",
      "Desenvolvi sistema em Access para distribuição online e validação de calibração de instrumentos.",
    ],
  },
  {
    cargo: "Analista de Negócios",
    empresa: "Essencis",
    periodo: "Nov 2001 – Abr 2002",
    bullets: [
      "Fui responsável por projetos de expansão com o superintendente de novos negócios, montando planos de negócio para o conselho.",
      "Modelei viabilidade com DCF, VPL e Payback para aterros, incineradores, remediação e M&A.",
      "Aprovei **1** aquisição em estágio de engenharia e consolidei a disciplina de investimento orientada por valor.",
    ],
  },
  {
    cargo: "Analista de Controle em Processo",
    empresa: "Nycomed",
    periodo: "Jul 2000 – Nov 2001",
    bullets: [
      "Fui responsável pelas liberações de linha, análises de lotes acabados e semiacabados e inspeções em plantas terceirizadas.",
      "Estruturei playbook para torquímetro digital, parâmetros de controle, Resolução de Problemas e qualificação do equipamento em ambiente regulado.",
      "Assumi temporariamente o terceiro turno por **3 meses** durante a transição da fábrica e sustentei a operação sem perda de controle de qualidade.",
    ],
  },
  {
    cargo: "Professor PEBII",
    empresa: "Estado de São Paulo",
    periodo: "Jun 1999 – Mar 2000 (paralelo à Sanofi)",
    bullets: [
      "Fui responsável por aulas eventuais e por **1** projeto de recuperação no ensino médio, em paralelo à atuação na Sanofi.",
      "Estruturei conteúdo, acompanhamento e condução da turma em contexto de aprendizado e reforço escolar.",
      "Desenvolvi comunicação didática e capacidade de explicar temas técnicos com clareza para perfis diversos.",
    ],
  },
  {
    cargo: "Operador de produção",
    empresa: "Sanofi-Aventis",
    periodo: "Fev 1998 – Jun 2000",
    bullets: [
      "Fui responsável por atuar como estagiário técnico e operador de produção na área de sólidos, assumindo rotinas de engenharia e liberação de linha.",
      "Implementei controles operacionais, participei da validação de processos e equipamentos e organizei registros de temperatura e umidade do estoque intermediário.",
      "Escrevi e padronizei **180+ POPs**, consolidando minha base em qualidade, processo e disciplina operacional.",
    ],
  },
];

const formação = [
  "Engenheiro Químico — Faculdades Oswaldo Cruz (2014)",
  "MBA Corporate Strategy — BSP Business School São Paulo (2016–2017)",
  "Planejamento e Orçamento — Saint Paul Escola de Negócios (2016)",
  "Six Sigma Green Belt — Setec Consulting (2020)",
  "Problem Solving — Ventus Consulting (2020)",
  "ILead liderança para líder de líderes — Fundação Dom Cabral (2021)",
  "Técnico em Química — SENAI Mario Amato (1997)",
];

const stack = [
  "Excel avançado + VBA",
  "SQL",
  "Python",
  "PySpark",
  "Databricks",
  "Grafana",
  "Tableau",
  "Power BI",
  "Metabase",
  "Salesforce",
  "Zendesk",
  "WMS",
  "ERP Infor LN",
  "BAAN IV",
  "Totvs Logix",
  "MS-Project",
  "Access",
];

const fitMap = JSON.parse(fs.readFileSync(fitMapPath, "utf8"));
const fileBase = `felipe_armel_cv_${stripSnake(fitMap.cargo)}_${stripSnake(fitMap.empresa)}`;
const tmpOutputPath = path.join(tmpDir, `${fileBase}.docx`);

async function main() {
  fs.mkdirSync(tmpDir, { recursive: true });

  const children = [
    new Paragraph({
      children: [new TextRun({ text: "Felipe Armel Dias da Silva", bold: true, size: pt(12), font: "Arial" })],
      spacing: { after: 0 },
    }),
    linkParagraph("linkedin.com/in/felipearmel", "https://linkedin.com/in/felipearmel"),
    new Paragraph({ children: [new TextRun({ text: "São Paulo, SP", size: pt(9), font: "Arial" })], spacing: { after: 0 } }),
    linkParagraph("(11) 98674-8218", "https://wa.me/5511986748218"),
    linkParagraph("armelfelipe@gmail.com", "mailto:armelfelipe@gmail.com"),
    espaco(8),
    secao("Resumo"),
    bulletText("Executivo sênior em **Operações Logísticas**, **Planejamento Estratégico** e **Growth Strategy**, com forte **Liderança**, **Gestão Operacional**, **Gestão de Performance**, **Gestão de Pessoas**, **Gestão de Projetos** e **Tomada de Decisão Baseada em Dados**. No iFood, como Diretor de Operações, administrei budget de **R$300MM/ano** e gerei saving de **R$70MM/ano**. Na wehandle, reduzi o custo por atendimento de **R$4,14 para R$3,61**. Na VivaReal, ampliei a conversão inbound de **18% para 50%**."),
    espaco(8),
    secao("Experiência"),
  ];

  for (const exp of experiences) {
    children.push(cargoParagraph(exp.cargo, exp.empresa, exp.periodo));
    for (const bulletTextValue of exp.bullets) {
      children.push(bulletText(bulletTextValue));
    }
    children.push(espaco(6));
  }

  children.push(secao("Formação"));
  for (const item of formação) {
    children.push(bullet([{ text: item }]));
  }

  children.push(secao("Stack técnica"));
  children.push(new Paragraph({
    children: [new TextRun({ text: stack.join(" · "), size: pt(9), font: "Arial" })],
    spacing: { after: 0 },
  }));

  children.push(secao("Idiomas"));
  children.push(bullet([{ text: "Português — Nativo" }]));
  children.push(bullet([{ text: "Inglês — Avançado" }]));

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
      children,
    }],
  });

  const buffer = await Packer.toBuffer(doc);
  fs.writeFileSync(tmpOutputPath, buffer);
  console.log(tmpOutputPath);
}

main().catch(error => {
  console.error(error);
  process.exit(1);
});
