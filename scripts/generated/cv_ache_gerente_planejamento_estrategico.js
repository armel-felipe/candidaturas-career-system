const pt = n => n * 2;

const {
  Document, Packer, Paragraph, TextRun,
  BorderStyle, TabStopType, TabStopPosition,
  AlignmentType, ExternalHyperlink, LevelFormat
} = require("docx");
const fs = require("fs");

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
  sections: [{
    properties: {
      page: {
        margin: { top: 720, right: 504, bottom: 720, left: 504 }
      }
    },
    children: [
      // CABEÇALHO
      new Paragraph({
        children: [new TextRun({ text: "Felipe Armel Dias da Silva", bold: true, size: pt(12), font: "Arial" })],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [
          new ExternalHyperlink({
            children: [new TextRun({ text: "linkedin.com/in/felipearmel", style: "Hyperlink", size: pt(9), font: "Arial" })],
            link: "https://linkedin.com/in/felipearmel"
          })
        ],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [new TextRun({ text: "S\u00e3o Paulo, SP", size: pt(9), font: "Arial" })],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [
          new ExternalHyperlink({
            children: [new TextRun({ text: "(11) 98674-8218", style: "Hyperlink", size: pt(9), font: "Arial" })],
            link: "https://wa.me/5511986748218"
          })
        ],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [
          new ExternalHyperlink({
            children: [new TextRun({ text: "armelfelipe@gmail.com", style: "Hyperlink", size: pt(9), font: "Arial" })],
            link: "mailto:armelfelipe@gmail.com"
          })
        ],
        spacing: { after: 0 }
      }),

      espaco(8),

      // RESUMO
      secao("Resumo"),
      espaco(3),
      new Paragraph({
        children: [
          new TextRun({
            text: "Engenheiro Qu\u00edmico com MBA Corporate Strategy (BSP). Constru\u00ed carreira em planejamento estrat\u00e9gico, S&OP e governan\u00e7a corporativa \u2014 liderei o PE corporativo na VivaReal (fus\u00e3o com ZAP) e o S&OP executivo no iFood com budget de R$300MM/ano. Busco posi\u00e7\u00e3o de Gerente de Planejamento Estrat\u00e9gico.",
            size: pt(9), font: "Arial"
          })
        ],
        spacing: { after: 0 }
      }),

      espaco(8),

      // EXPERIÊNCIA
      secao("Experi\u00eancia"),
      espaco(3),

      // wehandle
      cargoParagraph("Head de Opera\u00e7\u00f5es", "wehandle", "Mai 2024 \u2013 Fev 2026"),
      bullet([
        { text: "Assumi a opera\u00e7\u00e3o de suporte ao cliente com time de 30 pessoas, margem bruta de ", bold: false },
        { text: "15%", bold: true },
        { text: " e conduzi duas migra\u00e7\u00f5es de plataforma de atendimento para modelo IA first com foco em escalabilidade.", bold: false }
      ]),
      bullet([
        { text: "Implantei canal WhatsApp substituindo contato telef\u00f4nico e introduzi chatbot com IA humanizada, conectando dados de atendimento ao datalake via API para decis\u00e3o em tempo real.", bold: false }
      ]),
      bullet([
        { text: "Reduzi custo por atendimento de R$4,14 para R$3,61 (", bold: false },
        { text: "\u221213%", bold: true },
        { text: "), elevei CSAT de 85% para 92% e reduzi TME de 20 para 8 minutos.", bold: false }
      ]),

      espaco(6),

      // iFood Diretor
      cargoParagraph("Diretor de Opera\u00e7\u00f5es", "iFood", "Abr 2022 \u2013 Mar 2024"),
      bullet([
        { text: "Fui respons\u00e1vel pela linha de custo das entregas com equipe de at\u00e9 240 pessoas e budget de ", bold: false },
        { text: "R$300MM/ano", bold: true },
        { text: ", conduzindo S&OP executivo mensal e desdobramento estrat\u00e9gico com o VP e C-level.", bold: false }
      ]),
      bullet([
        { text: "Estruturei governan\u00e7a corporativa com rituais mensais de S&OP, modelagem financeira com Python, SQL e Databricks, e an\u00e1lise de cen\u00e1rios para trade-offs entre custo e n\u00edvel de servi\u00e7o.", bold: false }
      ]),
      bullet([
        { text: "Ampliei cobertura de 400 para 800 cidades, reduzi custo log\u00edstico compar\u00e1vel em 3% YoY, aumentei entregas agrupadas de 12% para ", bold: false },
        { text: "25%", bold: true },
        { text: " e reduzi indisponibilidade de frota de 5% para 1%.", bold: false }
      ]),

      espaco(6),

      // iFood Head
      cargoParagraph("Head de Opera\u00e7\u00f5es", "iFood", "Nov 2018 \u2013 Mar 2022"),
      bullet([
        { text: "Liderei equipe de 28 pessoas em liveOps, pricing, modelagem de dados e planejamento de frota, estruturando a torre de opera\u00e7\u00f5es da subsidi\u00e1ria do M\u00e9xico.", bold: false }
      ]),
      bullet([
        { text: "Estruturei capacity planning de frota, criei dashboards em tempo real no Grafana e modelei dados com SQL, Databricks e Tableau para correla\u00e7\u00e3o entre satura\u00e7\u00e3o log\u00edstica e NDS.", bold: false }
      ]),
      bullet([
        { text: "Gerei saving de ", bold: false },
        { text: "R$70MM/ano", bold: true },
        { text: " com simulador de n\u00edvel de servi\u00e7o, reduzi custo de distribui\u00e7\u00e3o de MPOS em 80% e reduzi cancelamentos no M\u00e9xico em 60% ajustando raios de entrega.", bold: false }
      ]),

      espaco(6),

      // VivaReal
      cargoParagraph("Gerente de Planejamento Comercial e Opera\u00e7\u00f5es", "VivaReal", "Mai 2015 \u2013 Dez 2017"),
      bullet([
        { text: "Fui respons\u00e1vel pelo planejamento estrat\u00e9gico da empresa, desdobramento de metas e controle da execu\u00e7\u00e3o operacional, com equipe de 33 pessoas e 5 lideran\u00e7as diretas.", bold: false }
      ]),
      bullet([
        { text: "Estruturei a \u00e1rea de CS como arquiteto \u2014 desenhei processos, defini r\u00e9gua de onboarding e contratei a lideran\u00e7a \u2014 e otimizei a esteira SDR com an\u00e1lise de convers\u00e3o e segmenta\u00e7\u00e3o de leads.", bold: false }
      ]),
      bullet([
        { text: "Entreguei o planejamento estrat\u00e9gico de 2018 no contexto da fus\u00e3o com ZAP, elevei convers\u00e3o SDR inbound de 18% para ", bold: false },
        { text: "50%", bold: true },
        { text: " e reduzi custo de vendas em 40%.", bold: false }
      ]),

      espaco(6),

      // Trifil consolidado
      cargoParagraph("Coordenador de S&OP | Expedi\u00e7\u00e3o | Supply Chain", "Trifil (Scalina)", "Jan 2006 \u2013 Set 2014"),
      bullet([
        { text: "Fui respons\u00e1vel por criar as \u00e1reas de S&OP e Intelig\u00eancia de Mercado do zero, gerenciar 40K SKUs em duas marcas e conduzir projetos estrat\u00e9gicos reportados diretamente ao CEO.", bold: false }
      ]),
      bullet([
        { text: "Atuei como PMO de gest\u00e3o de projetos estrat\u00e9gicos corporativos (Projeto Entrega Certa e GGF 2014), implementei Strategic Sourcing em 150K+ SKUs e implantei metodologias GPD/PDCA com KPIs.", bold: false }
      ]),
      bullet([
        { text: "Reduzi ", bold: false },
        { text: "R$8MM", bold: true },
        { text: " de GGF do P&L, reduzi custo de compras em 27% e elevei acur\u00e1cia de estoque de 85% para 98%.", bold: false }
      ]),

      espaco(6),

      // Sanofi e Nycomed (farmacêuticas)
      cargoParagraph("Operador de Produ\u00e7\u00e3o e Analista de Qualidade", "Sanofi e Nycomed", "Fev 1998 \u2013 Nov 2001"),
      bullet([
        { text: "Iniciei minha carreira na ind\u00fastria farmac\u00eautica, atuando em ambiente regulado com BPF, valida\u00e7\u00e3o de processos e equipamentos, controle de qualidade em processo e elabora\u00e7\u00e3o de POPs.", bold: false }
      ]),
      bullet([
        { text: "Estruturei playbook de implanta\u00e7\u00e3o de torqu\u00edmetro digital para testes de veda\u00e7\u00e3o de frascos e desenvolvi par\u00e2metros de controle de secagem com balan\u00e7a de halog\u00eanio.", bold: false }
      ]),
      bullet([
        { text: "Efetivado em 5 meses no programa de est\u00e1gio de 1 ano por desempenho, elaborei mais de ", bold: false },
        { text: "180 POPs", bold: true },
        { text: " e atuei como respons\u00e1vel tempor\u00e1rio pelo terceiro turno durante transi\u00e7\u00e3o de planta.", bold: false }
      ]),

      espaco(8),

      // FORMAÇÃO
      secao("Forma\u00e7\u00e3o"),
      espaco(3),
      bullet([
        { text: "MBA Corporate Strategy \u2014 BSP Business School S\u00e3o Paulo (2016\u20132017)", bold: false }
      ]),
      bullet([
        { text: "ILEad \u2014 Lideran\u00e7a para L\u00edder de L\u00edderes \u2014 Funda\u00e7\u00e3o Dom Cabral (2021)", bold: false }
      ]),
      bullet([
        { text: "Six Sigma Green Belt \u2014 Setec Consulting (2020)", bold: false }
      ]),
      bullet([
        { text: "Engenharia Qu\u00edmica \u2014 Faculdades Oswaldo Cruz (2014)", bold: false }
      ]),

      espaco(8),

      // STACK TÉCNICA
      secao("Stack t\u00e9cnica"),
      espaco(3),
      new Paragraph({
        children: [new TextRun({
          text: "Excel/VBA \u00b7 SQL \u00b7 Python \u00b7 Databricks \u00b7 Power BI \u00b7 Tableau \u00b7 Grafana \u00b7 Salesforce \u00b7 Zendesk \u00b7 ERP Infor LN",
          size: pt(9), font: "Arial"
        })],
        spacing: { after: 0 }
      }),

      espaco(8),

      // IDIOMAS
      secao("Idiomas"),
      espaco(3),
      bullet([
        { text: "Portugu\u00eas \u2014 Nativo", bold: false }
      ]),
      bullet([
        { text: "Ingl\u00eas \u2014 Avan\u00e7ado", bold: false }
      ])
    ]
  }]
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync("outputs/_tmp/cv_ache_gerente_planejamento_estrategico.docx", buffer);
  console.log("ok");
});
