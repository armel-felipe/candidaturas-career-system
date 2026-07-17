const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, ExternalHyperlink,
  TabStopType, TabStopPosition, LevelFormat, AlignmentType,
  BorderStyle, Numbering
} = require("docx");

// --- helpers ---
const pt = n => n * 2; // half-points — NUNCA n * 20

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

// --- header helper ---
function headerLink(text, url) {
  return new ExternalHyperlink({
    children: [new TextRun({ text, style: "Hyperlink", size: pt(9), font: "Arial" })],
    link: url
  });
}

// --- build document ---
const doc = new Document({
  styles: {
    default: { document: { run: { font: "Arial", size: pt(9) } } },
    paragraphStyles: [
      { id: "Normal", name: "Normal", quickFormat: true,
        run: { font: "Arial", size: pt(9) },
        paragraph: { spacing: { after: 0 } } },
      { id: "ListParagraph", name: "List Paragraph", basedOn: "Normal", quickFormat: true,
        run: { font: "Arial", size: pt(9) },
        paragraph: { spacing: { after: 0 } } }
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
      // --- HEADER ---
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

      // --- RESUMO ---
      espaco(8),
      secao("Resumo"),
      espaco(3),
      new Paragraph({
        children: [
          new TextRun({
            text: "Engenheiro Químico com MBA Corporate Strategy e Green Belt, com mais de 20 anos de carreira em operações — dos últimos 12 em posições executivas. Fui Diretor de Operações no iFood (budget R$300MM/ano, 240 pessoas, escala de 30M pedidos/mês), Head de Operações na WeHandle (transformação de atendimento com IA) e liderei S&OP, supply chain e CS em empresas como Trifil, VivaReal e Renault. Busco posição de Gerente de Operações onde possa aplicar gestão de processos, pessoas, KPIs e finanças para gerar eficiência e resultado.",
            size: pt(9), font: "Arial"
          })
        ],
        spacing: { after: 0 }
      }),

      // --- EXPERIÊNCIA ---
      espaco(8),
      secao("Experiência"),
      espaco(3),

      // 1. WeHandle
      cargoParagraph("Head de Operações", "wehandle", "Mai 2024 – Fev 2026"),
      espaco(2),
      bullet([
        { text: "Fui responsável pela operação de suporte ao cliente, liderando um time de 30 pessoas e estruturando a transformação do atendimento com dados, automação e novos canais — reduzindo custos e elevando a qualidade." }
      ]),
      bullet([
        { text: "Liderei duas migrações de plataforma e implantei Zendesk como central de atendimento IA first, integrei dados via API com três plataformas de atendimento e direcionei insights ao time de produto reduzindo o contact rate." }
      ]),
      bullet([
        { text: "Reduzi o custo por atendimento de R$4,14 para R$3,61 (−13%), elevei o CSAT de 85% para 92%, cortei o TME de 20 para 8 minutos e impactei " },
        { text: "15%", bold: true },
        { text: " na margem bruta." }
      ]),
      espaco(6),

      // 2. iFood — Diretor
      cargoParagraph("Diretor de Operações", "iFood", "Abr 2022 – Mar 2024"),
      espaco(2),
      bullet([
        { text: "Fui responsável pela gestão financeira e operacional da logística em escala nacional, com equipe de ~240 pessoas, budget de " },
        { text: "R$300MM/ano", bold: true },
        { text: " e P&L de custo das entregas — reportando ao C-level." }
      ]),
      bullet([
        { text: "Liderei o S&OP executivo mensal consolidando demanda, frota, custo e nível de serviço; modelei dados com Python, SQL e Databricks para decisão em tempo real." }
      ]),
      bullet([
        { text: "Ampliei a cobertura de 400 para 800 cidades, reduzi o custo logístico comparável em 3% YoY e mantive SLA em operação de " },
        { text: "30M pedidos/mês", bold: true },
        { text: "." }
      ]),
      espaco(6),

      // 3. iFood — Head
      cargoParagraph("Head de Operações", "iFood", "Nov 2018 – Mar 2022"),
      espaco(2),
      bullet([
        { text: "Fui responsável por equipe de 28 pessoas nas áreas de liveOps, pricing, modelagem de dados e planejamento de frota — estruturando a operação com dashboards e simuladores." }
      ]),
      bullet([
        { text: "Criei indicadores em tempo real no Grafana, desenvolvi simulador de nível de serviço e implantei balanceamento de frota por cidade com restrição de raio por bairro." }
      ]),
      bullet([
        { text: "Gerei saving de " },
        { text: "R$70M/ano", bold: true },
        { text: " com o simulador de nível de serviço, reduzi cancelamentos em 60% no México e cortei custo de distribuição de MPOS em 80%." }
      ]),
      espaco(6),

      // 4. Renault
      cargoParagraph("Gerente de Customer Success", "Renault do Brasil", "Jan 2018 – Out 2018"),
      espaco(2),
      bullet([
        { text: "Fui responsável pela operação de CS da Renault, conduzindo a migração de dois BPOs com 40 pessoas para uma estrutura própria de 8 pessoas — com dados e tecnologia." }
      ]),
      bullet([
        { text: "Estruturei metodologia de qualificação baseada em dados, implantei governança de SLA de retorno em tempo real e direcionei discadores com análise de performance." }
      ]),
      bullet([
        { text: "Elevei a conversão de vendas de " },
        { text: "24% para 46%", bold: true },
        { text: " e criei modelo escalável de CS com maior controle de qualidade." }
      ]),
      espaco(6),

      // 5. VivaReal
      cargoParagraph("Gerente de Planejamento Comercial e Operações", "VivaReal", "Mai 2015 – Dez 2017"),
      espaco(2),
      bullet([
        { text: "Fui responsável pelo planejamento estratégico, desdobramento de metas e gestão de 33 pessoas em Qualidade, SDR e operações — fui arquiteto da área de CS que escalou para " },
        { text: "91 pessoas", bold: true },
        { text: "." }
      ]),
      bullet([
        { text: "Criei processo de esteira de SDR com tempo ideal de contato, implantei Salesforce e integrei dados com SQL e dashboards automatizados." }
      ]),
      bullet([
        { text: "Aumentei a conversão inbound de " },
        { text: "18% para 50%", bold: true },
        { text: ", reduzi o custo de vendas em 40% e recuperei R$1M de inadimplentes." }
      ]),
      espaco(6),

      // 6. Trifil
      cargoParagraph("Coordenador de S&OP", "Trifil", "Jan 2010 – Set 2014"),
      espaco(2),
      bullet([
        { text: "Fui responsável pela criação da área de S&OP do zero, gerenciando 40K SKUs em duas marcas e todos os canais de distribuição — conectando planejamento de demanda, produção e finanças." }
      ]),
      bullet([
        { text: "Apliquei melhoria contínua com GPD e PDCA, desenvolvi simulador de MRP e S&OP em Excel VBA e coordenei o planejamento de capacidade e outsourcing." }
      ]),
      bullet([
        { text: "Reduzi " },
        { text: "R$8M", bold: true },
        { text: " de GGF do P&L, mantive acurácia de estoque em 98% com gestão da qualidade ISO 9001 e implantei Strategic Sourcing reduzindo custo de compras em 27%." }
      ]),

      // --- FORMAÇÃO ---
      espaco(8),
      secao("Formação"),
      espaco(3),
      bullet([{ text: "MBA Corporate Strategy — BSP Business School São Paulo (2017)" }]),
      bullet([{ text: "Engenharia Química — Faculdades Oswaldo Cruz (2014)" }]),
      bullet([{ text: "Six Sigma Green Belt — Setec Consulting (2020)" }]),
      bullet([{ text: "ILEad Liderança para Líder de Líderes — Fundação Dom Cabral (2021)" }]),

      // --- STACK TÉCNICA ---
      espaco(8),
      secao("Stack técnica"),
      espaco(3),
      new Paragraph({
        children: [new TextRun({
          text: "SQL · Python · Databricks · Grafana · Salesforce · Zendesk · Power BI · Tableau · Metabase · Excel/VBA · ERP Infor LN · WMS",
          size: pt(9), font: "Arial"
        })],
        spacing: { after: 0 }
      }),

      // --- IDIOMAS ---
      espaco(8),
      secao("Idiomas"),
      espaco(3),
      bullet([{ text: "Português — Nativo" }]),
      bullet([{ text: "Inglês — Avançado" }]),

      // --- COMPETÊNCIAS (tags ATS) ---
      espaco(8),
      secao("Competências"),
      espaco(3),
      new Paragraph({
        children: [new TextRun({
          text: "Gestão de Operações · Otimização de Processos · Liderança de Equipes · Melhoria Contínua · Gestão de KPIs · P&L · Gestão Financeira · Qualidade · Planejamento Estratégico · S&OP · Eficiência Operacional · Redução de Custos · Tomada de Decisão Orientada por Dados",
          size: pt(9), font: "Arial"
        })],
        spacing: { after: 0 }
      }),
    ]
  }]
});

// --- output ---
const workspace = path.resolve(__dirname, "..", "..");
const outPath = path.join(workspace, "outputs", "_tmp", "cv_gerente_operacoes_grupo_easy.docx");
Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync(outPath, buffer);
  console.log("ok");
});
