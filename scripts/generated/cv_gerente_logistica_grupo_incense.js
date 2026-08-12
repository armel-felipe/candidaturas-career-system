const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, ExternalHyperlink,
  TabStopType, TabStopPosition, LevelFormat, AlignmentType,
  BorderStyle, Numbering
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
function espaco(ptSize = 6) {
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

// Link clicável
function link(text, url) {
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
      // === CABEÇALHO ===
      new Paragraph({
        children: [new TextRun({ text: "Felipe Armel Dias da Silva", bold: true, size: pt(12), font: "Arial" })],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [link("linkedin.com/in/felipearmel", "https://linkedin.com/in/felipearmel")],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [new TextRun({ text: "São Paulo, SP", size: pt(9), font: "Arial" })],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [link("(11) 98674-8218", "https://wa.me/5511986748218")],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [link("armelfelipe@gmail.com", "mailto:armelfelipe@gmail.com")],
        spacing: { after: 0 }
      }),

      espaco(8),

      // === RESUMO ===
      secao("Resumo"),
      espaco(3),
      new Paragraph({
        children: [new TextRun({
          text: "Engenheiro Químico com MBA Corporate Strategy e 20+ anos de experiência em gestão de operações logísticas e cadeia de suprimentos. No iFood, como Diretor de Operações, geri budget de R$300MM/ano e reduzi custo logístico comparável em 3% YoY. Como Head, criei simulador que gerou saving de R$70MM/ano. Na Trifil, estruturei centro de expedição com acurácia de estoque de 98% e implantei WMS com coletores. Busco posição de Gerente de Logística.",
          size: pt(9), font: "Arial"
        })],
        spacing: { after: 0 }
      }),

      espaco(8),

      // === EXPERIÊNCIA ===
      secao("Experiência"),
      espaco(3),

      // --- WeHandle ---
      cargoParagraph("Head de Operações", "WeHandle", "Mai 2024 – Fev 2026"),
      bullet([
        { text: "Fui responsável pela operação de suporte com time de 30 pessoas, reestruturando processos e impactando ", bold: false },
        { text: "15% na margem bruta", bold: true },
        { text: " da companhia.", bold: false }
      ]),
      bullet([
        { text: "Liderei duas migrações de plataforma de atendimento, implantei automação com IA e canal WhatsApp, integrando dados via API para dashboards em tempo real.", bold: false }
      ]),
      bullet([
        { text: "Reduzi o custo por atendimento de ", bold: false },
        { text: "R$4,14 para R$3,61 (−13%)", bold: true },
        { text: " e elevei o CSAT de 85% para 92%.", bold: false }
      ]),

      espaco(6),

      // --- iFood Diretor ---
      cargoParagraph("Diretor de Operações", "iFood", "Abr 2022 – Mar 2024"),
      bullet([
        { text: "Fui responsável pelas operações logísticas com equipe de ~240 pessoas e budget de ", bold: false },
        { text: "R$300MM/ano", bold: true },
        { text: ", cobrindo FieldOps, Meios de Pagamento e Novos Negócios.", bold: false }
      ]),
      bullet([
        { text: "Conduzi o S&OP executivo mensal com modelagem em Python, SQL e Databricks, conectando marketing, frota e operação em planejamento integrado.", bold: false }
      ]),
      bullet([
        { text: "Ampliei a cobertura de 400 para ", bold: false },
        { text: "800 cidades", bold: true },
        { text: ", reduzi o custo logístico comparável em 3% YoY e aumentei pedidos agrupados de 12% para 25%.", bold: false }
      ]),

      espaco(6),

      // --- iFood Head ---
      cargoParagraph("Head de Operações", "iFood", "Nov 2018 – Mar 2022"),
      bullet([
        { text: "Fui responsável pelas áreas de liveOps, pricing e planejamento de frota com equipe de 28 pessoas, estruturando indicadores em tempo real.", bold: false }
      ]),
      bullet([
        { text: "Criei o roteirizador logístico (TMS proprietário) com restrição de raio por bairro e dashboards no Grafana para monitoramento de entregas.", bold: false }
      ]),
      bullet([
        { text: "Gerei saving de ", bold: false },
        { text: "R$70MM/ano", bold: true },
        { text: " com simulador de nível de serviço e reduzi cancelamentos em 60% no México ajustando raios de entrega.", bold: false }
      ]),

      espaco(6),

      // --- VivaReal ---
      cargoParagraph("Gerente de Planejamento Comercial e Operações", "VivaReal", "Mai 2015 – Dez 2017"),
      bullet([
        { text: "Fui responsável por equipes de planejamento comercial, SDR e qualidade, totalizando 33 pessoas e 5 lideranças diretas.", bold: false }
      ]),
      bullet([
        { text: "Estruturei a área de CS como arquiteto — desenhei processos, defini onboarding e contratei liderança; a área escalou para ", bold: false },
        { text: "91 pessoas", bold: true },
        { text: ".", bold: false }
      ]),
      bullet([
        { text: "Elevei a conversão de SDR inbound de 18% para ", bold: false },
        { text: "50%", bold: true },
        { text: ", reduzindo o custo de vendas em 40%, e mantive churn abaixo de 3% ao mês.", bold: false }
      ]),

      espaco(6),

      // --- Trifil S&OP ---
      cargoParagraph("Coordenador de S&OP", "Trifil (Scalina)", "Jan 2010 – Set 2014"),
      bullet([
        { text: "Fui responsável por criar a área de S&OP do zero, gerenciando ", bold: false },
        { text: "40K SKUs", bold: true },
        { text: " em duas marcas e todos os canais de distribuição.", bold: false }
      ]),
      bullet([
        { text: "Apliquei GPD, PDCA e melhoria contínua para definir políticas de safety stock e Strategic Sourcing em 150K+ SKUs.", bold: false }
      ]),
      bullet([
        { text: "Reduzi ", bold: false },
        { text: "R$8MM de GGF", bold: true },
        { text: " do P&L e melhorei o giro de estoque de 8 para 6 meses.", bold: false }
      ]),

      espaco(6),

      // --- Trifil Expedição ---
      cargoParagraph("Coordenador de Expedição", "Trifil (Scalina)", "Jan 2007 – Out 2007"),
      bullet([
        { text: "Fui responsável pelo centro de expedição com operações de inbound, armazenagem, picking, packing e outbound.", bold: false }
      ]),
      bullet([
        { text: "Implantei WMS com coletores RF e wi-fi, endereçamento de estoque e inventário rotativo.", bold: false }
      ]),
      bullet([
        { text: "Elevei a acurácia de estoque de 85% para ", bold: false },
        { text: "98%", bold: true },
        { text: ", aumentei a produtividade em 35% e reduzi perdas em 30%.", bold: false }
      ]),

      espaco(8),

      // === FORMAÇÃO ===
      secao("Formação"),
      espaco(3),
      bullet([{ text: "MBA Corporate Strategy — BSP Business School São Paulo (2017)", bold: false }]),
      bullet([{ text: "Engenharia Química — Faculdades Oswaldo Cruz (2014)", bold: false }]),
      bullet([{ text: "Six Sigma Green Belt — Setec Consulting (2020)", bold: false }]),

      espaco(8),

      // === STACK TÉCNICA ===
      secao("Stack técnica"),
      espaco(3),
      new Paragraph({
        children: [new TextRun({
          text: "Excel/VBA · SQL · Python · Databricks · Grafana · WMS · TMS · ERP Infor LN · Power BI · Tableau · Metabase",
          size: pt(9), font: "Arial"
        })],
        spacing: { after: 0 }
      }),

      espaco(8),

      // === IDIOMAS ===
      secao("Idiomas"),
      espaco(3),
      bullet([{ text: "Português — Nativo", bold: false }]),
      bullet([{ text: "Inglês — Avançado", bold: false }])
    ]
  }]
});

const outputPath = "outputs/_tmp/cv_gerente_logistica_grupo_incense.docx";
Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync(outputPath, buffer);
  console.log("ok");
});
