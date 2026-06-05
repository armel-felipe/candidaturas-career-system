const { Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, TabStopType, TabStopPosition, BorderStyle, NumberingFormat, LevelFormat } = require("docx");
const fs = require("fs");

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
      espaco(3),
      new Paragraph({
        children: [
          new TextRun({ text: "linkedin.com/in/felipearmel", size: pt(9), font: "Arial", color: "0563C1" })
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
          new TextRun({ text: "(11) 98674-8218", size: pt(9), font: "Arial" })
        ],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [
          new TextRun({ text: "armelfelipe@gmail.com", size: pt(9), font: "Arial" })
        ],
        spacing: { after: 0 }
      }),

      espaco(8),
      secao("Resumo"),

      new Paragraph({
        children: [
          new TextRun({ text: "Engenheiro Químico com MBA Corporate Strategy — BSP e experiência em operações de alta complexidade. No iFood, como Head e Diretor de Operações, gerei saving de R$70MM/ano com simulador de nível de serviço e expandi cobertura de 400 para 800 cidades em operação de 30M pedidos/mês. Na Trifil, criei e sustentei S&OP por 4 anos, reduzi R$8M de GGF e melhorei acurácia de estoque de 85% para 98%. Busco posição de Gerente de Planejamento e Logística para aplicar fundamentos de Supply Chain em ambiente de alta confiabilidade.", size: pt(9), font: "Arial" })
        ],
        spacing: { after: 0 }
      }),

      espaco(8),
      secao("Experiência"),

      cargoParagraph("Head e Diretor de Operações", "iFood", "Nov 2018 – Mar 2024"),
      bullet([{ text: "Fui responsável por gerir operações logísticas de marketplace com equipe de ~240 pessoas e budget de R$300MM/ano, conduzindo S&OP executivo mensal com foco em SLA, cobertura e custo." }]),
      bullet([{ text: "Conduzi o planejamento com S&OP executivo, modelagem em Python/SQL/Databricks, dashboards em tempo real no Grafana e capacity planning de frota por cidade." }]),
      bullet([{ text: "Ampliei cobertura de 400 para 800 cidades, reduzi custo comparável em 3% YoY, gerei saving de R$70MM/ano com simulador de nível de serviço e mantive operação com 30M pedidos/mês." }]),

      espaco(6),
      cargoParagraph("Coordenador de S&OP | Expedição | Supply Chain", "Trifil", "Jan 2006 – Set 2014"),
      bullet([{ text: "Fui responsável por coordenar o Supply Chain com gestão de 40K SKUs, MRP corporativo, S&OP mensal e expedição, liderando equipe de analistas e garantindo conformidade com BPF." }]),
      bullet([{ text: "Estruturei S&OP do zero, implantei coletores RF/wi-fi para picking, defini políticas de safety stock e coordenei outsourcing nacional e internacional." }]),
      bullet([{ text: "Reduzi GGF em R$8M, melhorei acurácia de estoque de 85% para 98%, reduzi custo de compras em 27%, falta de estoque em 40% e melhorei giro de 8 para 6 meses." }]),

      espaco(6),
      cargoParagraph("Gerente de Planejamento Comercial e Operações", "VivaReal", "Mai 2015 – Dez 2017"),
      bullet([{ text: "Fui responsável por estruturar operações de planejamento comercial e Customer Success com 33 pessoas, 5 lideranças, incluindo Qualidade, SDR e cadastro de imóveis." }]),
      bullet([{ text: "Estruturei processos de CS do zero, definindo régua de onboarding, criando esteira de SDR e implementando governança com KPIs em dashboards." }]),
      bullet([{ text: "Reduzi churn para menos de 3%/mês, elevei NPS para 80%, atingi CSAT acima de 92% e aumentei conversão SDR de 18% para 50%." }]),

      espaco(8),
      secao("Formação"),

      bullet([{ text: "MBA Corporate Strategy — BSP Business School São Paulo (2016–2017)" }]),
      bullet([{ text: "Engenheiro Químico — Faculdades Oswaldo Cruz (2014)" }]),
      bullet([{ text: "Técnico em Química — SENAI Mario Amato (1997)" }]),

      espaco(8),
      secao("Stack Técnica"),

      new Paragraph({
        children: [
          new TextRun({ text: "Excel VBA · SQL · Python · Databricks · Grafana · Power BI · Tableau · ERP Infor LN · WMS", size: pt(9), font: "Arial" })
        ],
        spacing: { after: 0 }
      }),

      espaco(8),
      secao("Idiomas"),

      bullet([{ text: "Português — Nativo" }]),
      bullet([{ text: "Inglês — Avançado" }])
    ],
  }],
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
  }
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync("outputs/_tmp/cv_gerente_planejamento_logistica_einstein.docx", buffer);
  console.log("ok");
});
