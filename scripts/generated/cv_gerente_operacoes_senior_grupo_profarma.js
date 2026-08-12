const { Document, Packer, Paragraph, TextRun, AlignmentType, BorderStyle, LevelFormat, Alignment, HeadingLevel, ExternalHyperlink, TabStopType, TabStopPosition } = require("docx");
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
  sections: [{
    properties: {
      page: {
        margin: { top: 720, right: 504, bottom: 720, left: 504 }
      }
    },
    children: [
      new Paragraph({
        children: [new TextRun({ text: "Felipe Armel Dias da Silva", bold: true, size: pt(12), font: "Arial" })],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [
          new ExternalHyperlink({
            children: [new TextRun({ text: "linkedin.com/in/felipearmel", size: pt(9), font: "Arial", color: "0000FF", underline: {} })],
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
            children: [new TextRun({ text: "(11) 98674-8218", size: pt(9), font: "Arial", color: "0000FF", underline: {} })],
            link: "https://wa.me/5511986748218"
          })
        ],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [
          new ExternalHyperlink({
            children: [new TextRun({ text: "armelfelipe@gmail.com", size: pt(9), font: "Arial", color: "0000FF", underline: {} })],
            link: "mailto:armelfelipe@gmail.com"
          })
        ],
        spacing: { after: 0 }
      }),

      secao("Resumo"),
      espaco(3),
      new Paragraph({
        children: [
          new TextRun({ text: "Executivo Sênior com mais de 20 anos em gestão de operações, logística física e digital, gestão de centros de distribuição e escala de tecnologia. No iFood, exerci controle de budget de ", size: pt(9), font: "Arial" }),
          new TextRun({ text: "R$300MM/ano", bold: true, size: pt(9), font: "Arial" }),
          new TextRun({ text: " e escala de 30M pedidos/mês. Na Trifil, elevei a acurácia de estoque para ", size: pt(9), font: "Arial" }),
          new TextRun({ text: "98%", bold: true, size: pt(9), font: "Arial" }),
          new TextRun({ text: " e reduzi perdas em 30% em CD próprio. Especialista em S&OP, automação e eficiência financeira, busco a posição de Gerente de Operações Sênior no Grupo Profarma.", size: pt(9), font: "Arial" })
        ],
        spacing: { after: 0 }
      }),

      secao("Experiência"),
      espaco(3),

      cargoParagraph("Head de Operações", "wehandle", "Mai 2024 – Fev 2026"),
      bullet([{ text: "Fui responsável pela liderança da operação de suporte e CX com time de 30 pessoas, focando na reestruturação de processos e redução de custos operacionais através de automação IA-first." }]),
      bullet([{ text: "Implantei soluções de atendimento via WhatsApp e chatbots com IA humanizada, integrando dados de atendimento ao datalake via API para decisões em tempo real." }]),
      bullet([{ text: "Reduzi o custo por atendimento de R$4,14 para " }, { text: "R$3,61", bold: true }, { text: " (-13%) e elevei o CSAT de 85% para 92%, gerando um impacto de " }, { text: "15%", bold: true }, { text: " na margem bruta." }]),
      espaco(6),

      cargoParagraph("Diretor de Operações", "iFood", "Abr 2022 – Mar 2024"),
      bullet([{ text: "Fui responsável pela gestão de operações e custo das entregas com budget de " }, { text: "R$300MM/ano", bold: true }, { text: ", liderando equipe de 240 pessoas em FieldOps e novos modelos de frota." }]),
      bullet([{ text: "Liderei o rito executivo de S&OP logístico e gestão de indicadores, conectando marketing, supply e operação para trade-offs entre custo e nível de serviço visando a meta de EBITDA." }]),
      bullet([{ text: "Ampliei a cobertura logística de 400 para " }, { text: "800 cidades", bold: true }, { text: " e reduzi o custo operacional comparável em " }, { text: "3%", bold: true }, { text: " YoY, mantendo a estabilidade de SLA em escala de 30M pedidos/mês." }]),
      espaco(6),

      cargoParagraph("Head de Operações", "iFood", "Nov 2018 – Mar 2022"),
      bullet([{ text: "Fui responsável pela estruturação da área de liveOps, pricing logístico e planejamento de frota, gerenciando a escala de 800K para 30M pedidos mensais." }]),
      bullet([{ text: "Estruturei o capacity planning de frota e criei simuladores de nível de serviço no Grafana para correlacionar saturação logística e ganhos dos entregadores." }]),
      bullet([{ text: "Alcancei um saving de " }, { text: "R$70MM/ano", bold: true }, { text: " através do simulador de nível de serviço e reduzi o lead time de entrega de equipamentos (MPOS) de 14 para " }, { text: "2 dias", bold: true }, { text: " (-85%)." }]),
      espaco(6),

      cargoParagraph("Gerente de Customer Success", "Renault do Brasil", "Jan 2018 – Out 2018"),
      bullet([{ text: "Fui responsável pela internalização da operação de vendas de leads, gerenciando a transição de BPOs terceirizados para uma estrutura própria focada em conversão." }]),
      bullet([{ text: "Redesenhei o fluxo digital de contato e implementei governança de SLA de retorno em tempo real, utilizando discadores automáticos programados sob medida." }]),
      bullet([{ text: "Elevei a conversão de leads de 24% para " }, { text: "46%", bold: true }, { text: " em apenas dois dias de operação interna e aprovei o projeto de ROI com interface direta com o VP de Marketing." }]),
      espaco(6),

      cargoParagraph("Gerente de Planejamento Comercial e Operações", "VivaReal", "Mai 2015 – Dez 2017"),
      bullet([{ text: "Fui responsável pelo planejamento estratégico e arquitetura da área de CS, liderando times de Qualidade, SDR e Cadastro com foco em redução de churn." }]),
      bullet([{ text: "Desenvolvi a régua de onboarding por jornada do cliente e estruturei a esteira de SDR inbound com foco em tração e produtividade comercial." }]),
      bullet([{ text: "Aumentei a conversão de SDR de 18% para " }, { text: "50%", bold: true }, { text: ", reduzi o custo de vendas em " }, { text: "40%", bold: true }, { text: " e mantive o churn rate da BU de usados abaixo de " }, { text: "3%", bold: true }, { text: " ao mês." }]),
      espaco(6),

      cargoParagraph("Coordenador de S&OP", "Scalina (Trifil)", "Jan 2010 – Set 2014"),
      bullet([{ text: "Fui responsável pela criação da área de S&OP e gestão de estoque, gerenciando 40K SKUs e centro de distribuição abrangendo recebimento e expedição." }]),
      bullet([{ text: "Implantei WMS com coletores RF e endereçamento, garantindo a acurácia de estoque e liderando o projeto de redução de Gastos Gerais de Fabricação (GGF)." }]),
      bullet([{ text: "Elevei a acuracidade de estoque para " }, { text: "98%", bold: true }, { text: " e gerei uma redução de " }, { text: "R$8MM", bold: true }, { text: " no P&L através da otimização de custos industriais." }]),

      secao("Formação"),
      espaco(3),
      bullet([{ text: "MBA Corporate Strategy — BSP Business School São Paulo (2016–2017)" }]),
      bullet([{ text: "Engenheiro Químico — Faculdades Oswaldo Cruz (2009–2014)" }]),
      espaco(8),

      secao("Stack técnica"),
      espaco(3),
      new Paragraph({
        children: [new TextRun({ text: "Operations Management · Distribution Center · Inventory Accuracy · Inventory Management · KPI Management · Budget Control · Process Automation · WMS · RF · S&OP", size: pt(9), font: "Arial" })],
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

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync("outputs/_tmp/cv_gerente_operacoes_senior_grupo_profarma.docx", buffer);
  console.log("ok");
});
