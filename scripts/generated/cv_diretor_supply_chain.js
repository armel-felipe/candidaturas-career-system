const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, ExternalHyperlink,
  TabStopType, TabStopPosition, BorderStyle,
  LevelFormat, AlignmentType
} = require("docx");

const pt = n => n * 2;
const workspace = process.cwd();

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
      new TextRun({ text: `\t${periodo}`, size: pt(9), font: "Arial" })
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
      // Nome
      new Paragraph({
        children: [new TextRun({ text: "Felipe Armel Dias da Silva", bold: true, size: pt(12), font: "Arial" })],
        spacing: { after: 0 }
      }),
      // Contatos
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

      espaco(6),

      // Resumo
      secao("Resumo"),
      espaco(3),
      new Paragraph({
        children: [new TextRun({
          text: "Executivo Sênior de Supply Chain e Operações com formação em Engenharia Química e MBA Corporate Strategy. No iFood, como Diretor de Operações, gerei budget logístico de R$300MM/ano com equipe de 240 pessoas, expandindo cobertura de 400 para 800 cidades. Na Trifil, criei a área de S&OP e implantei Strategic Sourcing com redução de 27% no custo de compras. Busco posição de Diretor de Supply Chain.",
          size: pt(9), font: "Arial"
        })],
        spacing: { after: 0 }
      }),

      espaco(8),

      // Experiência
      secao("Experiência"),
      espaco(3),

      // WeHandle
      cargoParagraph("Head de Operações", "WeHandle", "Mai 2024 – Fev 2026"),
      bullet([
        { text: "Fui responsável por liderar a operação de suporte e CX de SaaS B2B, com time de 30 pessoas, reestruturando processos para escalabilidade com impacto de ", bold: false },
        { text: "15% na margem bruta", bold: true },
        { text: ".", bold: false }
      ]),
      bullet([
        { text: "Liderei a transformação digital com automação via chatbot e IA, implantação de Zendesk como plataforma central, e integração de dados via API com Python, SQL e Metabase.", bold: false }
      ]),
      bullet([
        { text: "Reduzi o custo por atendimento de R$4,14 para ", bold: false },
        { text: "R$3,61 (−13%)", bold: true },
        { text: ", elevei o CSAT de 85% para 92% e reduzi o TME de 20 para 8 minutos.", bold: false }
      ]),

      espaco(6),

      // iFood Diretor
      cargoParagraph("Diretor de Operações", "iFood", "Abr 2022 – Mar 2024"),
      bullet([
        { text: "Fui responsável pelas operações logísticas com equipe de ~240 pessoas e budget de ", bold: false },
        { text: "R$300MM/ano", bold: true },
        { text: ", gerindo P&L da linha de custo das entregas e liderando o S&OP executivo mensal com KPIs de nível de serviço, lead time e custo logístico.", bold: false }
      ]),
      bullet([
        { text: "Conduzi o capacity planning de frota por cidade com modelagem em Python, SQL e Databricks, e estruturei governança de planejamento para eventos sazonais, clima e restrições operacionais.", bold: false }
      ]),
      bullet([
        { text: "Ampliei cobertura de 400 para ", bold: false },
        { text: "800 cidades", bold: true },
        { text: ", reduzi custos logísticos comparáveis em 3% YoY e gerei saving de ", bold: false },
        { text: "R$70M/ano", bold: true },
        { text: " com simulador de nível de serviço.", bold: false }
      ]),

      espaco(6),

      // iFood Head
      cargoParagraph("Head de Operações", "iFood", "Nov 2018 – Mar 2022"),
      bullet([
        { text: "Fui responsável por estruturar e liderar as áreas de liveOps, pricing, modelagem de dados e planejamento de frota com time de 28 pessoas, conectando dados, operação e produto.", bold: false }
      ]),
      bullet([
        { text: "Modelei dados logísticos com SQL, Databricks e Tableau, criei dashboards em tempo real no Grafana, e implementei torre de operações no México ajustando raios de entrega.", bold: false }
      ]),
      bullet([
        { text: "Reduzi o lead time de distribuição de MPOS de 14 para ", bold: false },
        { text: "2 dias (−85%)", bold: true },
        { text: ", diminui custo em 80% e reduzi cancelamentos no México em ", bold: false },
        { text: "60%", bold: true },
        { text: ".", bold: false }
      ]),

      espaco(6),

      // VivaReal
      cargoParagraph("Gerente de Planejamento Comercial e Operações", "VivaReal", "Mai 2015 – Dez 2017"),
      bullet([
        { text: "Fui responsável pelo planejamento estratégico e operações da unidade de imóveis usados, com equipe de 33 pessoas, e fui o arquiteto da área de Customer Success que ", bold: false },
        { text: "escalou para 91 pessoas", bold: true },
        { text: ".", bold: false }
      ]),
      bullet([
        { text: "Estruturei a régua de onboarding, implantei processo de SDR com análise de dados em SQL e dashboards, e integrei pricing, comissões e metas ao planejamento comercial.", bold: false }
      ]),
      bullet([
        { text: "Elevei a conversão SDR inbound de 18% para ", bold: false },
        { text: "50%", bold: true },
        { text: ", reduzi o custo de vendas em 40% e mantive churn abaixo de 3% ao mês com NPS de 80%.", bold: false }
      ]),

      espaco(6),

      // Trifil S&OP
      cargoParagraph("Coordenador de S&OP", "Trifil", "Jan 2010 – Set 2014"),
      bullet([
        { text: "Fui responsável por criar a área de S&OP do zero, sustentando os ritos por 4 anos com gestão de estoque e planejamento de 40K SKUs em duas marcas e todos os canais de distribuição.", bold: false }
      ]),
      bullet([
        { text: "Implantei Strategic Sourcing em 150K+ SKUs, defini políticas de estoque de segurança com trade-off financeiro, e criei simulador de MRP em Excel VBA para cenários do S&OP.", bold: false }
      ]),
      bullet([
        { text: "Reduzi custo de compras em ", bold: false },
        { text: "27%", bold: true },
        { text: ", diminui falta de estoque em 40%, melhorei giro de 8 para 6 meses e reduzi ", bold: false },
        { text: "R$8M de GGF", bold: true },
        { text: " do P&L.", bold: false }
      ]),

      espaco(8),

      // Formação
      secao("Formação"),
      espaco(3),
      bullet([
        { text: "MBA Corporate Strategy — BSP Business School São Paulo (2016–2017)", bold: false }
      ]),
      bullet([
        { text: "Engenharia Química — Faculdades Oswaldo Cruz (2014)", bold: false }
      ]),
      bullet([
        { text: "Six Sigma Green Belt — Setec Consulting (2020)", bold: false }
      ]),

      espaco(8),

      // Stack técnica
      secao("Stack técnica"),
      espaco(3),
      new Paragraph({
        children: [new TextRun({
          text: "Python · SQL · Databricks · Tableau · Grafana · Metabase · Excel/VBA · ERP Infor LN · Salesforce · Zendesk",
          size: pt(9), font: "Arial"
        })],
        spacing: { after: 0 }
      }),

      espaco(8),

      // Idiomas
      secao("Idiomas"),
      espaco(3),
      bullet([{ text: "Português — Nativo", bold: false }]),
      bullet([{ text: "Inglês — Avançado", bold: false }])
    ]
  }]
});

Packer.toBuffer(doc).then(buffer => {
  const outDir = `${workspace}/outputs/_tmp`;
  if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });
  fs.writeFileSync(`${outDir}/cv_diretor_supply_chain.docx`, buffer);
  console.log("ok");
});
