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
      new Paragraph({
        children: [
          new TextRun({ text: "Felipe Armel Dias da Silva", bold: true, size: pt(12), font: "Arial" })
        ],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [
          new ExternalHyperlink({
            link: "https://linkedin.com/in/felipearmel",
            children: [new TextRun({ text: "linkedin.com/in/felipearmel", size: pt(9), font: "Arial", style: "Hyperlink" })]
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
            link: "https://wa.me/5511986748218",
            children: [new TextRun({ text: "(11) 98674-8218", size: pt(9), font: "Arial", style: "Hyperlink" })]
          })
        ],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [
          new ExternalHyperlink({
            link: "mailto:armelfelipe@gmail.com",
            children: [new TextRun({ text: "armelfelipe@gmail.com", size: pt(9), font: "Arial", style: "Hyperlink" })]
          })
        ],
        spacing: { after: 0 }
      }),

      espaco(8),
      secao("Resumo"),
      espaco(3),
      new Paragraph({
        children: [new TextRun({
          text: "Engenheiro Químico com MBA Corporate Strategy e +20 anos de experiência em operações logísticas, governança e gestão executiva. Como Diretor de Operações no iFood, liderei orçamento de R$300MM/ano e equipe de 240 pessoas, estruturei governança com S&OP executivo mensal e reduzi custos em 3% YoY. Na Trifil, criei a área de S&OP do zero com KPIs logísticos (OTIF, fill rate, giro) e reduzi R$8MM em GGF. Na WeHandle, liderei profissionalização de operações com transição cultural para gestão data-driven. Busco posição de Diretor de Operações em empresa de logística e transporte.",
          size: pt(9), font: "Arial"
        })],
        spacing: { after: 0 }
      }),

      espaco(8),
      secao("Experiência"),
      espaco(3),

      cargoParagraph("Head de Operações", "WeHandle", "Mai 2024 – Fev 2026"),
      bullet([
        { text: "Responsável pela operação de suporte e CX de plataforma B2B SaaS, liderando time de 30 pessoas e reestruturando processos, métricas e cultura de gestão para profissionalizar a operação em ambiente early-stage." }
      ]),
      bullet([
        { text: "Liderei duas migrações de plataforma de atendimento para arquitetura IA first (Zendesk, chatbot), conectei dados via API para dashboards em tempo real e implantei automação com IA humanizada visando +25% de produtividade." }
      ]),
      bullet([
        { text: "Elevei CSAT de 85% para 92%, atingi 95% de SLA, reduzi TME de 20 para 8 minutos, cortei custo total por atendimento de R$4,14 para R$3,61 (−13%) com rigorosa " },
        { text: "gestão de custos", bold: true },
        { text: " e reduzi o backlog de produto em 60% com loop estruturado de CX-para-produto." }
      ]),

      espaco(6),
      cargoParagraph("Diretor de Operações", "iFood", "Abr 2022 – Mar 2024"),
      bullet([
        { text: "Responsável pela linha de custo de entregas com orçamento de R$300MM/ano, liderando organização de 240 pessoas nas áreas de Operações de Campo, Meios de Pagamento e Novos Negócios — com reporte direto a VP-level e interface com CFO." }
      ]),
      bullet([
        { text: "Liderei o rito executivo mensal de S&OP consolidando demanda, supply, custo logístico, nível de serviço e cenários — traduzindo dados operacionais em direcionais estratégicos para C-level, com trade-offs entre custo e SLA em cenários normal e crítico." }
      ]),
      bullet([
        { text: "Reduzi custo logístico comparável em 3% YoY, expandi cobertura de 400 para 800 cidades, reduzi indisponibilidade de frota de 5% para 1% (top 6 cidades: 5,4% para 0,5%), aumentei entregas agrupadas de 12% para 25% e mantive a operação dentro da meta de EBITDA." }
      ]),

      espaco(6),
      cargoParagraph("Head de Operações", "iFood", "Nov 2018 – Mar 2022"),
      bullet([
        { text: "Liderei equipe multidisciplinar de 28 pessoas em LiveOps, Pricing, Modelagem de Dados e Planejamento de Frota — estruturei a operação que escalou de 800K para 30M pedidos/mês." }
      ]),
      bullet([
        { text: "Construí simulador de nível de serviço com SQL, Python e Databricks que gerou saving de R$70MM/ano otimizando disponibilidade de frota e raios de entrega — criei dashboards em tempo real no Grafana para tomada de decisão em LiveOps." }
      ]),
      bullet([
        { text: "Reduzi custo de distribuição de MPOS em 80% e prazo de 14 para 2 dias, elevei disponibilidade de 70% para 97%, implantei torre de operações no México reduzindo cancelamentos em 60%, e estabeleci planejamento de frota com balanceamento entre cidades e modelos nuvem." }
      ]),

      espaco(6),
      cargoParagraph("Gerente de Planejamento Comercial e Operações", "VivaReal", "Mai 2015 – Dez 2017"),
      bullet([
        { text: "Fui o arquiteto da área de Customer Success — desenhei processos, defini régua de onboarding, jornada do cliente e contratei a liderança que escalou a operação para 91 pessoas (nunca fui gestor de CS; fui seu criador e projetista de processos)." }
      ]),
      bullet([
        { text: "Estruturei funil de SDR elevando conversão inbound de 18% para 50% (−40% custo de vendas), criei régua de onboarding, segmentei base de clientes e implantei Salesforce para pipeline, pricing, pagamentos e renovação automatizada." }
      ]),
      bullet([
        { text: "Reduzi churn da BU de usados para abaixo de 3%/mês, atingi NPS de 80% e CSAT acima de 92%, recuperei R$1M em inadimplentes e entreguei o planejamento estratégico de 2018 durante a fusão com ZAP." }
      ]),

      espaco(6),
      cargoParagraph("Coordenador de S&OP", "Trifil (Scalina)", "Jan 2010 – Set 2014"),
      bullet([
        { text: "Criei a área de S&OP do zero e sustentei rituais e operação por 4 anos — conectando demanda, supply, capacidade produtiva, estoques e Trade-offs financeiros, gerenciando 40K SKUs em duas marcas e todos os canais de distribuição." }
      ]),
      bullet([
        { text: "Implantei KPIs logísticos (OTIF, fill rate, acurácia de produção, giro de estoque) no Projeto Entrega Certa — criei simulador de MRP e cenários com Excel VBA, defini política de safety stock e liderei o planejamento de capacidade com MRP corporativo e MPS." }
      ]),
      bullet([
        { text: "Reduzi R$8 milhões de GGF do P&L otimizando energia, gás, manutenção e embalagens — economia real de R$4,6M acima da meta até agosto e R$8,6M vs mesmo período de 2013." }
      ]),

      espaco(8),
      secao("Formação"),
      espaco(3),
      bullet([{ text: "MBA Corporate Strategy — BSP Business School São Paulo (2017)" }]),
      bullet([{ text: "Engenharia Química — Faculdades Oswaldo Cruz (2014)" }]),
      bullet([{ text: "Six Sigma Green Belt — Setec Consulting (2020)" }]),

      espaco(8),
      secao("Stack Técnica"),
      espaco(3),
      new Paragraph({
        children: [new TextRun({
          text: "SQL · Python · Databricks · Grafana · Salesforce · Zendesk · Power BI · Tableau · Metabase · CRM · ERP Infor LN · Excel/VBA",
          size: pt(9), font: "Arial"
        })],
        spacing: { after: 0 }
      }),

      espaco(8),
      secao("Idiomas"),
      espaco(3),
      bullet([{ text: "Português — Nativo" }]),
      bullet([{ text: "Inglês — Avançado" }])
    ]
  }]
});

const outPath = "/Users/mac/llm server/projetos/candidaturas/outputs/_tmp/cv_diretor_operacoes_lemartransportes.docx";
Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync(outPath, buffer);
  console.log("ok");
});
