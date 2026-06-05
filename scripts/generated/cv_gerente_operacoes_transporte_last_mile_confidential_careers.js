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

const pt = n => n * 2; // half-points — NUNCA n * 20

const workspace = process.env.CAREER_WORKSPACE || process.cwd();
const outputDir = process.env.CAREER_OUTPUTS || path.join(workspace, "outputs");
const OUTPUT_NAME = "felipe_armel_cv_gerente_operacoes_transporte_last_mile_confidential_careers.docx";

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

const experiences = [
  {
    cargo: "Head de Operações",
    empresa: "wehandle",
    periodo: "Mai 2024 – Fev 2026",
    bullets: [
      [
        { text: "Fui responsável por liderar a operação com " },
        { text: "time de 30 pessoas", bold: true },
        { text: ", conectando " },
        { text: "Experiência do Cliente", bold: true },
        { text: ", suporte e backoffice em um ambiente de " },
        { text: "Maturidade Digital", bold: true },
        { text: " com foco em eficiência e escala." },
      ],
      [
        { text: "Implementei " },
        { text: "Automação de Processos", bold: true },
        { text: ", " },
        { text: "Integrações", bold: true },
        { text: " via API e monitoramento por " },
        { text: "Dados", bold: true },
        { text: " com Zendesk, Metabase, Python e SQL para dar visibilidade operacional em tempo real." },
      ],
      [
        { text: "Reduzi custo por atendimento de " },
        { text: "R$ 4,14 para R$ 3,61 (-13%)", bold: true },
        { text: ", elevei CSAT de " },
        { text: "85% para 92%", bold: true },
        { text: ", reduzi TME de 20 para 8 minutos e impactei a margem bruta em " },
        { text: "15%", bold: true },
        { text: "." },
      ],
    ],
  },
  {
    cargo: "Diretor de Operações",
    empresa: "iFood",
    periodo: "Abr 2022 – Mar 2024",
    bullets: [
      [
        { text: "Fui responsável por " },
        { text: "Operações Logísticas", bold: true },
        { text: ", " },
        { text: "Transporte", bold: true },
        { text: ", " },
        { text: "Gestão de Parceiros Logísticos", bold: true },
        { text: " e S&OP executivo no iFood, com equipe de " },
        { text: "240 pessoas", bold: true },
        { text: " e budget de " },
        { text: "R$ 300 MM/ano", bold: true },
        { text: "." },
      ],
      [
        { text: "Conduzi planejamento por cidade com SQL, Python, Databricks, Tableau e capacity planning, integrando marketing, frota, supply e operação em ritos executivos mensais." },
      ],
      [
        { text: "Reduzi custo logístico comparável em " },
        { text: "3% YoY", bold: true },
        { text: ", ampliei cobertura de " },
        { text: "400 para 800 cidades", bold: true },
        { text: ", levei pedidos agrupados de " },
        { text: "12% para 25%", bold: true },
        { text: " e sustentei " },
        { text: "Cost Reduction", bold: true },
        { text: " com " },
        { text: "Eficiência Operacional", bold: true },
        { text: "." },
      ],
    ],
  },
  {
    cargo: "Head de Operações",
    empresa: "iFood",
    periodo: "Nov 2018 – Mar 2022",
    bullets: [
      [
        { text: "Fui responsável por estruturar " },
        { text: "Last Mile", bold: true },
        { text: ", pricing, liveOps e planejamento de frota com time de 28 pessoas em uma operação digital de alto volume." },
      ],
      [
        { text: "Criei monitoramento em Grafana e modelei " },
        { text: "Dados", bold: true },
        { text: " com SQL e Databricks para balanceamento por cidade, restrição de raio e simulador de nível de serviço." },
      ],
      [
        { text: "Gerei saving de " },
        { text: "R$ 70 MM/ano", bold: true },
        { text: ", reduzi indisponibilidade de frota de " },
        { text: "5% para 1%", bold: true },
        { text: " no Brasil e de " },
        { text: "5,4% para 0,5%", bold: true },
        { text: " nas top 6 cidades, além de reduzir custo de distribuição de MPOS em " },
        { text: "80%", bold: true },
        { text: "." },
      ],
    ],
  },
  {
    cargo: "Gerente de Customer Success",
    empresa: "Renault do Brasil",
    periodo: "Jan 2018 – Out 2018",
    bullets: [
      [
        { text: "Fui responsável por internalizar a operação de conversão de leads e atendimento comercial, substituindo 2 BPOs e redesenhando o fluxo digital com foco em velocidade e controle." },
      ],
      [
        { text: "Estruturei governança com Excel, VBA e Power BI, defini metodologia de qualificação baseada em dados e direcionei o uso das ferramentas de discagem por capacidade operacional." },
      ],
      [
        { text: "Elevei conversão de vendas de leads de " },
        { text: "24% para 46%", bold: true },
        { text: " e reduzi a estrutura de " },
        { text: "40 PAs para 8 pessoas", bold: true },
        { text: " com ganho de eficiência." },
      ],
    ],
  },
  {
    cargo: "Gerente de Planejamento Comercial e Operações",
    empresa: "VivaReal",
    periodo: "Mai 2015 – Dez 2017",
    bullets: [
      [
        { text: "Fui responsável por planejamento comercial, operações e qualidade, liderando 33 pessoas e atuando como " },
        { text: "arquiteto da área de CS", bold: true },
        { text: ", nunca como gestor formal de CS." },
      ],
      [
        { text: "Estruturei SDR, onboarding, telefonia digital, pricing e dashboards diários com SQL e Excel automatizado, além de coordenar priorização de roadmap com produto." },
      ],
      [
        { text: "Elevei conversão inbound de " },
        { text: "18% para 50%", bold: true },
        { text: ", reduzi custo de vendas em " },
        { text: "40%", bold: true },
        { text: ", recuperei " },
        { text: "R$ 1 MM", bold: true },
        { text: " e sustentei NPS de " },
        { text: "80%", bold: true },
        { text: " com CSAT acima de 92%." },
      ],
    ],
  },
  {
    cargo: "Coordenador de S&OP",
    empresa: "Scalina (Trifil)",
    periodo: "Jan 2010 – Set 2014",
    bullets: [
      [
        { text: "Fui responsável por criar a área de " },
        { text: "Supply Chain", bold: true },
        { text: " e S&OP do zero, gerenciando " },
        { text: "40K SKUs", bold: true },
        { text: " e o Projeto Entrega Certa com OTIF e fill rate como KPIs centrais." },
      ],
      [
        { text: "Criei simulador de MRP em Excel/VBA, coordenei S&OE, estoque de segurança, capacity planning e outsourcing, além de governança por indicadores e calendário executivo." },
      ],
      [
        { text: "Reduzi " },
        { text: "R$ 8 MM", bold: true },
        { text: " de GGF do P&L, entreguei economia real de " },
        { text: "R$ 4,6 MM", bold: true },
        { text: " vs meta até agosto e mantive " },
        { text: "Cost Reduction", bold: true },
        { text: " com disciplina financeira." },
      ],
    ],
  },
  {
    cargo: "Coordenador de Inteligência Comercial",
    empresa: "Scalina (Trifil)",
    periodo: "Jan 2009 – Dez 2009",
    bullets: [
      [
        { text: "Fui responsável por criar a área de inteligência comercial com 2 pessoas, apoiando vendas, preços, franquias e visão de estoque com dados consolidados." },
      ],
      [
        { text: "Desenvolvi BI, automações em Excel/VBA e algoritmos para normalizar dados do ERP e melhorar a decisão de alocação de pedidos e margem." },
      ],
      [
        { text: "Reduzi o tempo de geração de relatórios de " },
        { text: "4 horas para 14 minutos", bold: true },
        { text: " e levei o faturamento de " },
        { text: "R$ 80 MM para R$ 120 MM/ano", bold: true },
        { text: "." },
      ],
    ],
  },
  {
    cargo: "Coordenador de Planejamento de Materiais",
    empresa: "Scalina (Trifil)",
    periodo: "Nov 2007 – Dez 2008",
    bullets: [
      [
        { text: "Fui responsável por planejamento de materiais, compras e regras do plano de produção, implantando Strategic Sourcing em mais de " },
        { text: "150 mil SKUs", bold: true },
        { text: "." },
      ],
      [
        { text: "Conduzi projeto de aquisição de 24 teares automatizados, defini planejamento de aviamentos, embalagens e fios e reestruturei parâmetros de abastecimento." },
      ],
      [
        { text: "Reduzi custo de compras em " },
        { text: "27%", bold: true },
        { text: ", diminui falta de estoque em " },
        { text: "40%", bold: true },
        { text: ", melhorei giro de " },
        { text: "8 para 6 meses", bold: true },
        { text: " e reduzi em " },
        { text: "15%", bold: true },
        { text: " o custo total de fabricação." },
      ],
    ],
  },
  {
    cargo: "Coordenador de Expedição",
    empresa: "Scalina (Trifil)",
    periodo: "Jan 2007 – Out 2007",
    bullets: [
      [
        { text: "Fui responsável por " },
        { text: "Process Improvement", bold: true },
        { text: " na operação física de expedição, com picking, packing, armazenagem, devoluções e controle de qualidade da entrega." },
      ],
      [
        { text: "Implementei WMS, coletores RF e wi-fi, inventário rotativo, endereçamento de estoque e layout operacional para elevar controle e fluidez do processo." },
      ],
      [
        { text: "Elevei acurácia de estoque de " },
        { text: "85% para 98%", bold: true },
        { text: ", aumentei " },
        { text: "Produtividade", bold: true },
        { text: " em " },
        { text: "35%", bold: true },
        { text: ", reduzi perdas em " },
        { text: "30%", bold: true },
        { text: " e cortei em " },
        { text: "50%", bold: true },
        { text: " o preparo de pedidos customizados." },
      ],
    ],
  },
  {
    cargo: "Analista de Processos e Sistemas",
    empresa: "Scalina (Trifil)",
    periodo: "Jan 2006 – Dez 2006",
    bullets: [
      [
        { text: "Fui responsável por implantar " },
        { text: "Process Improvement", bold: true },
        { text: " com PDCA, KPIs e planos de ação em toda a área produtiva da planta Guarulhos." },
      ],
      [
        { text: "Conduzi a seleção e implantação da automação da tinturaria e criei controles de capacidade e eficiência em Excel para suportar melhoria contínua." },
      ],
      [
        { text: "Reduzi custos de produção em " },
        { text: "40%", bold: true },
        { text: ", alcancei payback real de " },
        { text: "1,5 anos", bold: true },
        { text: " e aumentei eficiência das máquinas em " },
        { text: "12%", bold: true },
        { text: "." },
      ],
    ],
  },
  {
    cargo: "Coordenador de Produção - Químico",
    empresa: "VitaLabor Cosméticos",
    periodo: "Ago 2005 – Dez 2005",
    bullets: [
      [
        { text: "Fui responsável por produção, qualidade, compras e planejamento em uma empresa pequena de cosméticos, com atuação direta na rotina operacional." },
      ],
      [
        { text: "Criei sistema automatizado em Excel para estoque, receitas de fabricação e geração de lotes, além de dimensionar expansão e controlar documentação regulatória." },
      ],
      [
        { text: "Reduzi em " },
        { text: "80%", bold: true },
        { text: " as paradas por falta de produto e aumentei em " },
        { text: "80%", bold: true },
        { text: " a utilização da capacidade instalada, além de dimensionar expansão de " },
        { text: "40%", bold: true },
        { text: " da produção." },
      ],
    ],
  },
  {
    cargo: "Supervisor de Produção: Manipulação e Pesagem",
    empresa: "Pierre Alexander Cosméticos (SEBECO)",
    periodo: "Ago 2003 – Jul 2005",
    bullets: [
      [
        { text: "Fui responsável pela supervisão de produção e almoxarifado de matérias-primas, com " },
        { text: "time de 10 pessoas", bold: true },
        { text: " e controle FEFO, abastecimento e ordens de fabricação." },
      ],
      [
        { text: "Atuei como key user da implantação do ERP Logix, criei sistema de inventário em Excel e desenvolvi algoritmo de programação diária dos misturadores." },
      ],
      [
        { text: "Aumentei a " },
        { text: "Produtividade", bold: true },
        { text: " em " },
        { text: "13%", bold: true },
        { text: ", reduzi perdas por contaminação cruzada e bacteriana em " },
        { text: "20%", bold: true },
        { text: " e reduzi em " },
        { text: "1 dia", bold: true },
        { text: " o tempo de inventário." },
      ],
    ],
  },
  {
    cargo: "Coordenador do Sistema de Garantia da Qualidade",
    empresa: "Resinor",
    periodo: "Mai 2002 – Jul 2003",
    bullets: [
      [
        { text: "Fui responsável sozinho pelo sistema de garantia da qualidade, representando a diretoria e assegurando conformidade documental e operacional." },
      ],
      [
        { text: "Migrei a versão da norma, desenvolvi controle documental em Access, validei calibração de instrumentos e atuei como auditor líder." },
      ],
      [
        { text: "Concluí a migração com " },
        { text: "0 não conformidades", bold: true },
        { text: " e mantive conformidade em " },
        { text: "mais de 300 documentos", bold: true },
        { text: "." },
      ],
    ],
  },
  {
    cargo: "Analista de Negócios",
    empresa: "Essencis",
    periodo: "Nov 2001 – Abr 2002",
    bullets: [
      [
        { text: "Fui responsável por apoiar o superintendente de novos negócios na avaliação de expansão, M&A e construção de plantas para aprovação em conselho." },
      ],
      [
        { text: "Modelei planos de negócio e análises de viabilidade com DCF, VPL e Payback para projetos de aterros, incineradores e remediação." },
      ],
      [
        { text: "Aprovei " },
        { text: "1 projeto de aquisição", bold: true },
        { text: " em estágio de engenharia e consolidei a base financeira que depois sustentou decisões executivas de investimento e saving." },
      ],
    ],
  },
  {
    cargo: "Analista de Controle em Processo | Inspetor de Qualidade",
    empresa: "Nycomed",
    periodo: "Jul 2000 – Nov 2001",
    bullets: [
      [
        { text: "Fui responsável por liberações de linha, inspeções em plantas terceirizadas e controle em processo de produtos farmacêuticos acabados e semiacabados." },
      ],
      [
        { text: "Estruturei o playbook de implantação de torquímetro digital, revisei POPs e acompanhei estabilidade, secagem e qualificação de equipamentos." },
      ],
      [
        { text: "Assumi temporariamente a equipe do terceiro turno por " },
        { text: "3 meses", bold: true },
        { text: " durante a transição para Jaguariúna e ajudei a implantar parâmetros de controle da nova planta." },
      ],
    ],
  },
  {
    cargo: "Operador de Produção",
    empresa: "Sanofi-Aventis",
    periodo: "Fev 1998 – Jun 2000",
    bullets: [
      [
        { text: "Fui responsável por operar e liberar etapas da produção de sólidos, incluindo compressão, testes em processo, limpeza, montagem e controle ambiental." },
      ],
      [
        { text: "Escrevi POPs, participei da validação de processos e equipamentos e implantei controles de produtividade e eficiência da área." },
      ],
      [
        { text: "Fui efetivado em " },
        { text: "5 meses", bold: true },
        { text: " em um programa de estágio de " },
        { text: "1 ano", bold: true },
        { text: " por desempenho e redigi " },
        { text: "mais de 180 POPs", bold: true },
        { text: "." },
      ],
    ],
  },
];

const body = [
  paragrafo("Felipe Armel Dias da Silva", { size: 12, bold: true }),
  hyperlink("linkedin.com/in/felipearmel", "https://linkedin.com/in/felipearmel"),
  paragrafo("São Paulo, SP"),
  hyperlink("(11) 98674-8218", "https://wa.me/5511986748218"),
  hyperlink("armelfelipe@gmail.com", "mailto:armelfelipe@gmail.com"),
  espaco(8),
  secao("Resumo"),
  espaco(3),
  new Paragraph({
    children: [
      new TextRun({ text: "Executivo Sênior em ", size: pt(9), font: "Arial" }),
      new TextRun({ text: "Operações Logísticas", bold: true, size: pt(9), font: "Arial" }),
      new TextRun({ text: ", ", size: pt(9), font: "Arial" }),
      new TextRun({ text: "Transporte", bold: true, size: pt(9), font: "Arial" }),
      new TextRun({ text: " e ", size: pt(9), font: "Arial" }),
      new TextRun({ text: "Last Mile", bold: true, size: pt(9), font: "Arial" }),
      new TextRun({ text: ". No iFood, como Diretor de Operações, geri ", size: pt(9), font: "Arial" }),
      new TextRun({ text: "R$ 300 MM/ano", bold: true, size: pt(9), font: "Arial" }),
      new TextRun({ text: " e ampliei cobertura de ", size: pt(9), font: "Arial" }),
      new TextRun({ text: "400 para 800 cidades", bold: true, size: pt(9), font: "Arial" }),
      new TextRun({ text: "; como Head, gerei ", size: pt(9), font: "Arial" }),
      new TextRun({ text: "R$ 70 MM/ano", bold: true, size: pt(9), font: "Arial" }),
      new TextRun({ text: ". Atuei em ", size: pt(9), font: "Arial" }),
      new TextRun({ text: "Order to Delivery", bold: true, size: pt(9), font: "Arial" }),
      new TextRun({ text: ", ", size: pt(9), font: "Arial" }),
      new TextRun({ text: "Cost Reduction", bold: true, size: pt(9), font: "Arial" }),
      new TextRun({ text: ", ", size: pt(9), font: "Arial" }),
      new TextRun({ text: "Produtividade", bold: true, size: pt(9), font: "Arial" }),
      new TextRun({ text: ", ", size: pt(9), font: "Arial" }),
      new TextRun({ text: "Automação de Processos", bold: true, size: pt(9), font: "Arial" }),
      new TextRun({ text: ", ", size: pt(9), font: "Arial" }),
      new TextRun({ text: "Experiência do Cliente", bold: true, size: pt(9), font: "Arial" }),
      new TextRun({ text: " e ", size: pt(9), font: "Arial" }),
      new TextRun({ text: "Gestão de Parceiros Logísticos", bold: true, size: pt(9), font: "Arial" }),
      new TextRun({ text: " com apoio de ", size: pt(9), font: "Arial" }),
      new TextRun({ text: "Dados", bold: true, size: pt(9), font: "Arial" }),
      new TextRun({ text: ". Busco posição de Gerente de Operações.", size: pt(9), font: "Arial" }),
    ],
    spacing: { after: 0 },
  }),
  espaco(8),
  secao("Experiência"),
  espaco(3),
];

experiences.forEach((exp, index) => {
  body.push(cargoParagraph(exp.cargo, exp.empresa, exp.periodo));
  exp.bullets.forEach(runs => body.push(bullet(runs)));
  if (index < experiences.length - 1) {
    body.push(espaco(6));
  }
});

body.push(
  espaco(8),
  secao("Formação"),
  espaco(3),
  bullet([{ text: "ILead — Liderança para Líder de Líderes — Fundação Dom Cabral (2021)" }]),
  bullet([{ text: "Six Sigma Green Belt — Setec Consulting (2020)" }]),
  bullet([{ text: "MBA Corporate Strategy — BSP Business School São Paulo (2016–2017)" }]),
  bullet([{ text: "Engenheiro Químico — Faculdades Oswaldo Cruz (concluído 2014)" }]),
  bullet([{ text: "Técnico em Química — SENAI Mario Amato (concluído 1997)" }]),
  espaco(8),
  secao("Stack técnica"),
  espaco(3),
  paragrafo("Excel/VBA · SQL · Python · Databricks · Grafana · Tableau · Metabase · WMS · ERP Infor LN · Zendesk"),
  espaco(8),
  secao("Idiomas"),
  espaco(3),
  bullet([{ text: "Português — Nativo" }]),
  bullet([{ text: "Inglês — Avançado" }]),
);

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
      children: body,
    }],
  });

  const buffer = await Packer.toBuffer(doc);
  const outputPath = path.join(outputDir, OUTPUT_NAME);
  fs.writeFileSync(outputPath, buffer);
  console.log("ok");
  console.log(outputPath);
}

main().catch(error => {
  console.error(error);
  process.exit(1);
});
