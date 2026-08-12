const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, ExternalHyperlink,
  AlignmentType, BorderStyle, TabStopType, TabStopPosition,
  LevelFormat, Numbering
} = require("docx");

// half-points — NUNCA n * 20
const pt = n => n * 2;

// Linha de seção com borda inferior
function secao(text) {
  return new Paragraph({
    children: [new TextRun({ text, size: pt(12), font: "Arial" })],
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "000000", space: 1 } },
    spacing: { before: pt(6), after: pt(3) }
  });
}

// Espaçador
function espaco(ptSize) {
  return new Paragraph({
    children: [new TextRun({ text: "", size: pt(ptSize), font: "Arial" })],
    spacing: { after: 0 }
  });
}

// Cargo com período alinhado à direita
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

// Bullet com suporte a array de runs [{text, bold}]
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

// Parágrafo simples
function paragrafo(texto) {
  return new Paragraph({
    children: [new TextRun({ text: texto, size: pt(9), font: "Arial" })],
    spacing: { after: 0 }
  });
}

// Link no cabeçalho
function linkParagrafo(texto, url) {
  return new Paragraph({
    children: [
      new ExternalHyperlink({
        children: [new TextRun({ text: texto, size: pt(9), font: "Arial", style: "Hyperlink" })],
        link: url
      })
    ],
    spacing: { after: 0 }
  });
}

// Bullet de idioma sem numbering (texto corrido com bullet unicode)
function bulletIdioma(texto) {
  return new Paragraph({
    children: [new TextRun({ text: `\u2022 ${texto}`, size: pt(9), font: "Arial" })],
    indent: { left: 360, hanging: 180 },
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
      // Nome
      new Paragraph({
        children: [new TextRun({ text: "Felipe Armel Dias da Silva", bold: true, size: pt(12), font: "Arial" })],
        spacing: { after: 0 }
      }),
      // Contato
      linkParagrafo("linkedin.com/in/felipearmel", "https://linkedin.com/in/felipearmel"),
      paragrafo("São Paulo, SP"),
      linkParagrafo("(11) 98674-8218", "https://wa.me/5511986748218"),
      linkParagrafo("armelfelipe@gmail.com", "mailto:armelfelipe@gmail.com"),
      espaco(6),

      // Resumo
      secao("Resumo"),
      espaco(3),
      new Paragraph({
        children: [new TextRun({
          text: "Engenheiro Químico com especialização em Corporate Strategy e 20+ anos de carreira em operações e supply chain. Como Diretor no iFood, liderei operação logística de R$300MM/ano e 800 cidades, reduzindo custos em 3% YoY. Como Head, estruturei planejamento de frota com saving de R$70M/ano. Na Trifil, criei e liderei área de S&OP por 4 anos, gerenciando MRP corporativo, MPS e estoques de 40K SKUs. Busco posição de Gerente de PCP e Logística onde minha combinação de planejamento industrial e operação logística em escala gere disponibilidade de recursos, eficiência financeira e indicadores de performance.",
          size: pt(9), font: "Arial"
        })],
        spacing: { after: 0 }
      }),
      espaco(8),

      // Experiência
      secao("Experiência"),
      espaco(3),

      // --- WeHandle ---
      cargoParagraph("Head de Operações", "WeHandle", "Mai 2024 – Fev 2026"),
      bullet([
        { text: "Fui responsável por liderar a operação de atendimento com equipe de 30 pessoas — combinando " },
        { text: "liderança de equipes", bold: false },
        { text: " com automação via chatbot, implantação de IA humanizada e migração para plataforma Zendesk com integração via API." }
      ]),
      bullet([
        { text: "Modelei dados com Python, SQL e Metabase conectando plataformas de atendimento ao datalake da empresa, criando indicadores em tempo real para subsidiar decisões de produto e operação." }
      ]),
      bullet([
        { text: "Reduzi o custo por atendimento de R$4,14 para " },
        { text: "R$3,61 (−13%)", bold: true },
        { text: " com abertura de canal WhatsApp (custo caiu para R$0,56), elevei o CSAT de 85% para 92% e reduzi o TME de 20 para 8 minutos." }
      ]),
      espaco(6),

      // --- iFood Diretor ---
      cargoParagraph("Diretor de Operações", "iFood", "Abr 2022 – Mar 2024"),
      bullet([
        { text: "Fui responsável pela gestão das operações logísticas com equipe de ~240 pessoas, budget de " },
        { text: "R$300MM/ano", bold: true },
        { text: " e interface direta com C-level no S&OP executivo mensal, conectando demanda, frota, supply e custo logístico." }
      ]),
      bullet([
        { text: "Conduzi S&OP executivo com modelagem em Python, SQL e Databricks, capacity planning de frota por cidade e leitura recorrente de P&L com alavancas operacionais para proteger o EBITDA — unindo " },
        { text: "gestão orçamentária", bold: false },
        { text: " à rotina operacional." }
      ]),
      bullet([
        { text: "Ampliei a cobertura de " },
        { text: "400 para 800 cidades", bold: true },
        { text: ", reduzi o custo logístico comparável em 3% YoY, elevei entregas agrupadas de 12% para 25% e diminuí a indisponibilidade de frota de 5% para 1% (top 6 cidades: 5,4% para 0,5%)." }
      ]),
      espaco(6),

      // --- iFood Head ---
      cargoParagraph("Head de Operações", "iFood", "Nov 2018 – Mar 2022"),
      bullet([
        { text: "Fui responsável por estruturar o planejamento e balanceamento de frota de entregadores (liveOps, pricing, modelagem de dados), liderando equipe de 28 pessoas em modelo de operação em tempo real." }
      ]),
      bullet([
        { text: "Criei simulador de nível de serviço com Excel VBA e métricas no Grafana, modelei capacidade e restrição de raio por bairro com SQL e Databricks, conduzindo " },
        { text: "melhoria contínua", bold: false },
        { text: " com dados em tempo real, e implantei processo de distribuição de MPOS com critérios de elegibilidade para 352 cidades." }
      ]),
      bullet([
        { text: "Gerei " },
        { text: "saving de R$70M/ano", bold: true },
        { text: " com o simulador de nível de serviço, reduzi o custo de distribuição de MPOS em 80% (prazo de 14 para 2 dias) e diminuí cancelamentos no México em 60% com ajuste de raios de entrega." }
      ]),
      espaco(6),

      // --- Trifil S&OP ---
      cargoParagraph("Coordenador de S&OP", "Trifil (Scalina)", "Jan 2010 – Set 2014"),
      bullet([
        { text: "Fui responsável por criar a área de S&OP do zero, gerenciando o " },
        { text: "MRP corporativo", bold: true },
        { text: ", o MPS e o planejamento de capacidade de produção de " },
        { text: "40K SKUs", bold: true },
        { text: " distribuídos em duas marcas e todos os canais — sustentando os ritos por 4 anos." }
      ]),
      bullet([
        { text: "Defini política de safety stock e estoque de segurança com " },
        { text: "previsão de demanda", bold: false },
        { text: " como KPI central, implantei OTIF, fill rate e acurácia de produção como " },
        { text: "indicadores de produção", bold: false },
        { text: " do Projeto Entrega Certa (reportados ao CEO), e reduzi R$8M de GGF com otimização de energia, gás, manutenção e embalagens." }
      ]),
      bullet([
        { text: "Aumentei o giro de estoque de 8 para 6 meses com " },
        { text: "gestão de estoques", bold: false },
        { text: " e Strategic Sourcing (−27% custo de compras, −40% falta de estoque) e elevei a acurácia de estoque para " },
        { text: "98%", bold: true },
        { text: " com inventário rotativo e endereçamento." }
      ]),
      espaco(6),

      // --- Trifil Expedição ---
      cargoParagraph("Coordenador de Expedição", "Trifil (Scalina)", "Jan 2007 – Out 2007"),
      bullet([
        { text: "Fui responsável por estruturar o centro de expedição com gestão completa de picking, packing, armazenamento e fluxo de devoluções, liderando a implantação de coletores RF e posteriormente wi-fi." }
      ]),
      bullet([
        { text: "Implantei endereçamento de estoque, inventário rotativo e sistema visual de abastecimento do picking, unindo separação e conferência em uma única operação com foco em " },
        { text: "qualidade", bold: false },
        { text: " e produtividade." }
      ]),
      bullet([
        { text: "Elevei a acurácia de estoque de 85% para " },
        { text: "98%", bold: true },
        { text: ", aumentei a produtividade dos colaboradores em 35%, reduzi perdas e refugos em 30% e reduzi o preparo de pedidos customizados em 50%." }
      ]),
      espaco(8),

      // Formação
      secao("Formação"),
      espaco(3),
      bullet([{ text: "MBA Corporate Strategy — BSP Business School São Paulo (2017)" }]),
      bullet([{ text: "Engenharia Química — Faculdades Oswaldo Cruz (2014)" }]),
      espaco(8),

      // Stack técnica
      secao("Stack técnica"),
      espaco(3),
      new Paragraph({
        children: [new TextRun({ text: "Excel Avançado · SQL · Python · Databricks · Grafana · Metabase · ERP Infor LN · WMS", size: pt(9), font: "Arial" })],
        spacing: { after: 0 }
      }),
      espaco(8),

      // Idiomas
      secao("Idiomas"),
      espaco(3),
      bulletIdioma("Português — Nativo"),
      bulletIdioma("Inglês — Avançado"),
    ]
  }]
});

Packer.toBuffer(doc).then(buffer => {
  const outPath = "outputs/_tmp/cv_gerente_pcp_logistica_kovi.docx";
  fs.writeFileSync(outPath, buffer);
  console.log("ok");
});
