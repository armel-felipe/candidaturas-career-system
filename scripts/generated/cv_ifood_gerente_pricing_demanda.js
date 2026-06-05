const fs = require("fs");
const { Packer, Document, Paragraph, TextRun, BorderStyle, AlignmentType, TabStopType, TabStopPosition, LevelFormat } = require("docx");

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
  numbering: {
    config: [{
      reference: "bullets",
      levels: [{
        level: 0,
        format: LevelFormat.BULLET,
        text: "\u2022",
        alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 360, hanging: 180 } } }
      }]
    }]
  },
  styles: {
    default: { document: { run: { font: "Arial", size: pt(9) } } },
    paragraphStyles: [
      {
        id: "Normal",
        name: "Normal",
        quickFormat: true,
        run: { font: "Arial", size: pt(9) },
        paragraph: { spacing: { after: 0 } }
      },
      {
        id: "ListParagraph",
        name: "List Paragraph",
        basedOn: "Normal",
        quickFormat: true,
        run: { font: "Arial", size: pt(9) },
        paragraph: { spacing: { after: 0 } }
      }
    ]
  },
  sections: [{
    properties: {
      page: { margin: { top: 720, right: 504, bottom: 720, left: 504 } }
    },
    children: [
      // Header
      new Paragraph({
        children: [
          new TextRun({ text: "Felipe Armel Dias da Silva", bold: true, size: pt(12), font: "Arial" })
        ],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [
          new TextRun({
            text: "linkedin.com/in/felipearmel",
            size: pt(9),
            font: "Arial",
            link: { external: "https://linkedin.com/in/felipearmel" }
          })
        ],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [
          new TextRun({ text: "São Paulo, SP", size: pt(9), font: "Arial" })
        ],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [
          new TextRun({
            text: "(11) 98674-8218",
            size: pt(9),
            font: "Arial",
            link: { external: "https://wa.me/5511986748218" }
          })
        ],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [
          new TextRun({
            text: "armelfelipe@gmail.com",
            size: pt(9),
            font: "Arial",
            link: { external: "mailto:armelfelipe@gmail.com" }
          })
        ],
        spacing: { after: pt(6) }
      }),

      // Resumo
      secao("Resumo"),
      espaco(3),
      bullet([{
        text: "Executivo sênior com passagem por iFood e WeHandle, lidando com precificação e otimização de receita em hiperescala. No iFood, como Diretor de Operações, reduzi custo logístico comparável em 3% YoY e ampliei cobertura de 400 para 800 cidades com budget de R$300MM/ano. Como Head, gerei saving de R$70MM/ano com modelagem de preços e precificação dinâmica. Busco posição de Gerente Pricing Demanda para aplicar yield management em plataforma B2C de marketplace."
      }]),
      espaco(8),

      // Experiência
      secao("Experiência"),
      espaco(3),

      // WeHandle
      cargoParagraph("Head de Operações", "WeHandle", "Mai 2024 – Fev 2026"),
      espaco(3),
      bullet([{ text: "Fui responsável por operações de atendimento e CX com time de 30 pessoas, reportando diretamente à liderança e gerenciando budget de custos com impacto direto na margem bruta em empresa de marketplace." }]),
      bullet([{ text: "Liderei automação com IA e chatbot, implantação de canal WhatsApp e integração de dados via API ao datalake, aplicando dynamic pricing de custos por canal." }]),
      bullet([{ text: "Reduzi custo por atendimento de " }, { text: "R$4,14 para R$3,61 (-13%)", bold: true }, { text: " e impactei " }, { text: "15% na margem bruta", bold: true }, { text: ", com CSAT de 85% para 92%." }]),
      espaco(6),

      // iFood Diretor
      cargoParagraph("Diretor de Operações", "iFood", "Abr 2022 – Mar 2024"),
      espaco(3),
      bullet([{ text: "Fui responsável pela linha de P&L de custo das entregas com budget de R$300MM/ano, liderando ~240 pessoas em FieldOps, Pagamentos e Novos Negócios em operações de marketplace, com S&OP executivo mensal e leitura semanal de DRE para EBITDA." }]),
      bullet([{ text: "Conduzi revenue optimization com precificação por zona, capacity planning de frota em SQL/Python/Databricks e expansão de cobertura de 400 para 800 cidades com precificação dinâmica adaptada por região." }]),
      bullet([{ text: "Ampliei cobertura de " }, { text: "400 para 800 cidades", bold: true }, { text: ", reduzi custo logístico comparável em " }, { text: "3% YoY", bold: true }, { text: " e alcancei " }, { text: "breakeven com 25% de pedidos agrupados", bold: true }, { text: "." }]),
      espaco(6),

      // iFood Head
      cargoParagraph("Head de Operações", "iFood", "Nov 2018 – Mar 2022"),
      espaco(3),
      bullet([{ text: "Fui responsável por pricing da operação logística em marketplace, definindo arquitetura de remuneração por zona e modelo de serviço, com time de 28 pessoas em liveOps, pricing e Business Intelligence." }]),
      bullet([{ text: "Modelei precificação com simulador de nível de serviço em Python/SQL/Grafana, conduzi testes controlados de elasticidade de preço e yield management com promoção por zona e priorização por entregador." }]),
      bullet([{ text: "Gerei " }, { text: "saving de R$70MM/ano", bold: true }, { text: ", reduzi cancelamentos em " }, { text: "60% no México", bold: true }, { text: " ajustando raios por bairro e diminui custo de distribuição de MPOS em " }, { text: "80%", bold: true }, { text: "." }]),
      espaco(6),

      // VivaReal
      cargoParagraph("Gerente de Planejamento Comercial e Operações", "VivaReal", "Mai 2015 – Dez 2017"),
      espaco(3),
      bullet([{ text: "Fui responsável por planejamento comercial, precificação de produtos e operações de lançamentos e usados com 33 pessoas, incluindo áreas de Qualidade, SDR e cadastro de imóveis." }]),
      bullet([{ text: "Apliquei data analysis para precificação por mix e margem, criei área de recuperação de inadimplentes e estruturei processos de SDR com segmentação de carteira." }]),
      bullet([{ text: "Recuperei " }, { text: "R$1MM em receita", bold: true }, { text: " e aumentei conversão SDR inbound de " }, { text: "18% para 50%", bold: true }, { text: ", com churn abaixo de " }, { text: "3%/mês", bold: true }, { text: "." }]),
      espaco(6),

      // Trifil S&OP
      cargoParagraph("Coordenador de S&OP", "Trifil", "Jan 2010 – Set 2014"),
      espaco(3),
      bullet([{ text: "Fui responsável pelo S&OP corporativo, MRP, planejamento de materiais e gestão de 40K SKUs em duas marcas, definindo política de safety stock e estoques de segurança." }]),
      bullet([{ text: "Implantei strategic sourcing em 150K+ SKUs com SKU management avançado, análise de custo total e precificação de materiais com Excel/VBA e simuladores de cenários." }]),
      bullet([{ text: "Reduzi " }, { text: "27% no custo de compras", bold: true }, { text: ", eliminei " }, { text: "40% de falta de estoque", bold: true }, { text: " e reduzi " }, { text: "R$8MM de GGF", bold: true }, { text: " do P&L." }]),
      espaco(6),

      // Trifil Expedição
      cargoParagraph("Coordenador de Expedição", "Trifil", "Jan 2007 – Out 2007"),
      espaco(3),
      bullet([{ text: "Fui responsável por expedição, picking, packing e armazenagem, implantando WMS, inventário rotativo e endereçamento de estoque com coletores RF." }]),
      bullet([{ text: "Apliquei cost reduction com redesenho de layout, otimização de picking e redução de perdas via endereçamento e inventário rotativo." }]),
      bullet([{ text: "Elevei acurácia de estoque de " }, { text: "85% para 98%", bold: true }, { text: ", aumentei produtividade em " }, { text: "35%", bold: true }, { text: " e reduzi perdas em " }, { text: "30%", bold: true }, { text: "." }]),
      espaco(8),

      // Formação
      secao("Formação"),
      espaco(3),
      bullet([{ text: "MBA Corporate Strategy — BSP Business School São Paulo (2016–2017)" }]),
      bullet([{ text: "Engenharia Química — Faculdades Oswaldo Cruz (2014)" }]),
      bullet([{ text: "Six Sigma Green Belt — Setec Consulting (2020)" }]),
      espaco(8),

      // Stack técnica
      secao("Stack técnica"),
      espaco(3),
      bullet([{ text: "SQL · Python · Databricks · Tableau · Grafana · Power BI · Metabase · Excel/VBA · Salesforce · Zendesk · ERP Infor LN · WMS" }]),
      espaco(8),

      // Idiomas
      secao("Idiomas"),
      espaco(3),
      bullet([{ text: "Português — Nativo" }]),
      bullet([{ text: "Inglês — Avançado" }]),
      espaco(8)
    ]
  }]
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync("outputs/_tmp/cv_ifood_gerente_pricing_demanda.docx", buffer);
  console.log("ok");
}).catch(err => {
  console.error(err);
  process.exit(1);
});
