const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, ExternalHyperlink,
  TabStopPosition, TabStopType, LevelFormat, AlignmentType,
  BorderStyle, Header, Footer, PageNumber, PageReference,
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
        children: [new TextRun({ text: "Felipe Armel Dias da Silva", bold: true, size: pt(12), font: "Arial" })],
        spacing: { after: 0 }
      }),
      new Paragraph({
        spacing: { after: 0 },
        children: [
          new ExternalHyperlink({
            children: [new TextRun({ text: "linkedin.com/in/felipearmel", style: "Hyperlink", size: pt(9), font: "Arial" })],
            link: "https://linkedin.com/in/felipearmel"
          })
        ]
      }),
      new Paragraph({
        children: [new TextRun({ text: "São Paulo, SP", size: pt(9), font: "Arial" })],
        spacing: { after: 0 }
      }),
      new Paragraph({
        spacing: { after: 0 },
        children: [
          new ExternalHyperlink({
            children: [new TextRun({ text: "(11) 98674-8218", style: "Hyperlink", size: pt(9), font: "Arial" })],
            link: "https://wa.me/5511986748218"
          })
        ]
      }),
      new Paragraph({
        spacing: { after: 0 },
        children: [
          new ExternalHyperlink({
            children: [new TextRun({ text: "armelfelipe@gmail.com", style: "Hyperlink", size: pt(9), font: "Arial" })],
            link: "mailto:armelfelipe@gmail.com"
          })
        ]
      }),
      espaco(8),

      secao("Resumo"),
      espaco(3),
      new Paragraph({
        children: [new TextRun({ text: "Engenheiro Químico com MBA Corporate Strategy e 20+ anos em operações. Como Head na wehandle, liderei time de 30 pessoas com gestão de incidentes, SLAs e melhoria contínua, reduzindo contact rate em 8%. No iFood, como Head e Diretor, liderei 240 pessoas com budget R$300MM/ano, análise de dados operacionais e reporte para liderança, expandindo cobertura de 400 para 800 cidades. Na VivaReal, estruturei CS de 91 pessoas com gestão de times e conversão SDR 18%→50%. Na Trifil, criei S&OP e reduzi R$8M em GGF. Busco posição de Coordenador de Operações em fintech.", size: pt(9), font: "Arial" })],
        spacing: { after: 0 }
      }),
      espaco(8),

      secao("Experiência"),
      espaco(3),

      cargoParagraph("Head de Operações", "wehandle", "Mai 2024 – Fev 2026"),
      bullet([{ text: "Fui responsável por liderar a operação de suporte e customer experience com time de 30 pessoas — gestão de incidentes críticos B2B, monitoramento de processos, SLAs e a jornada completa de atendimento em plataforma SaaS." }]),
      bullet([{ text: "Conectei APIs das plataformas de atendimento ao datalake para dashboards em tempo real, implantei automação com IA e canal WhatsApp, e criei board de priorização com produto via ClickUp, aplicando análise de dados operacionais." }]),
      bullet([{ text: "Reduzi o contact rate em " }, { text: "8%", bold: true }, { text: " e o backlog em " }, { text: "60%", bold: true }, { text: ", mantive SLA em " }, { text: "95%", bold: true }, { text: ", e reduzi o custo por atendimento de R$4,14 para " }, { text: "R$3,61", bold: true }, { text: " (−13%) com melhoria contínua." }]),
      espaco(6),

      cargoParagraph("Diretor de Operações", "iFood", "Abr 2022 – Mar 2024"),
      bullet([{ text: "Fui responsável por gerir as operações logísticas com equipe de ~240 pessoas e budget de " }, { text: "R$300MM/ano", bold: true }, { text: ", incluindo FieldOps, Meios de Pagamento e Novos Negócios, com reporte para liderança executiva." }]),
      bullet([{ text: "Conduzi o rito executivo mensal de S&OP da logística, coordenando fornecedores e parceiros de frota com relacionamento com fornecedores, e liderei iniciativas de otimização com dashboards Grafana e modelagem em Python, SQL e Databricks." }]),
      bullet([{ text: "Ampliei cobertura de " }, { text: "400 para 800 cidades", bold: true }, { text: ", reduzi indisponibilidade de frota de " }, { text: "5% para 0,5%", bold: true }, { text: " nas top 6 cidades e reduzi o custo comparável em " }, { text: "3% YoY", bold: true }, { text: "." }]),
      espaco(6),

      cargoParagraph("Head de Operações", "iFood", "Nov 2018 – Mar 2022"),
      bullet([{ text: "Fui responsável por liderar times de liveOps, pricing, modelagem de dados e planejamento de frota com 28 pessoas, conectando operação, tecnologia e métricas em tempo real com gestão de times multidisciplinares." }]),
      bullet([{ text: "Modelei dados com SQL, Python e Databricks, criei dashboards Grafana e estruturei o rito de S&OP com indicadores em tempo real de saturação logística e nível de serviço, gerando reporte semanal para liderança." }]),
      bullet([{ text: "Criei simulador logístico que gerou saving projetado de " }, { text: "R$70M/ano", bold: true }, { text: " e reduzi custo de distribuição de MPOS em " }, { text: "80%", bold: true }, { text: ", com tempo de entrega caindo de 14 para 2 dias." }]),
      espaco(6),

      cargoParagraph("Gerente de Planejamento Comercial e Operações", "VivaReal", "Mai 2015 – Dez 2017"),
      bullet([{ text: "Fui responsável por estruturar a área de operações comerciais com gestão de times, atuando como arquiteto da área de CS e liderando equipes de planejamento comercial, SDR e qualidade, com 33 pessoas diretas e 5 lideranças." }]),
      bullet([{ text: "Desenhei processos de onboarding, régua de atendimento e jornada do cliente, contratei a liderança de CS e implantei dashboards com SQL e Excel para disponibilizar dados em tempo real." }]),
      bullet([{ text: "Elevei a conversão SDR inbound de " }, { text: "18% para 50%", bold: true }, { text: ", atingi CSAT acima de " }, { text: "92%", bold: true }, { text: " e reduzi o custo de vendas em " }, { text: "40%", bold: true }, { text: ", com a área de CS escalando para " }, { text: "91 pessoas", bold: true }, { text: "." }]),
      espaco(6),

      cargoParagraph("Coordenador de S&OP", "Trifil", "Jan 2010 – Set 2014"),
      bullet([{ text: "Fui responsável por criar a área de S&OP do zero e sustentar os ritos por 4 anos, gerenciando " }, { text: "40K SKUs", bold: true }, { text: " de produto acabado e intermediando comercial e fabricação com melhoria contínua dos processos." }]),
      bullet([{ text: "Implantei projeto de OTIF com GPD, modelei simulador para validação de MRP e avaliação de cenários com Excel VBA, e coordenei equipe de analistas de indicadores com análise de dados operacionais." }]),
      bullet([{ text: "Reduzi " }, { text: "R$8 milhões", bold: true }, { text: " em Gastos Gerais de Fabricação no P&L e mantive OTIF estruturado como reporte para liderança ao CEO." }]),
      espaco(8),

      secao("Formação"),
      espaco(3),
      bullet([{ text: "MBA Corporate Strategy — BSP Business School São Paulo (2017)" }]),
      bullet([{ text: "Engenharia Química — Faculdades Oswaldo Cruz (2014)" }]),
      espaco(8),

      secao("Stack técnica"),
      espaco(3),
      new Paragraph({
        children: [new TextRun({ text: "Python · SQL · Grafana · Databricks · Metabase · Power BI · ClickUp · Zendesk · Excel/VBA", size: pt(9), font: "Arial" })],
        spacing: { after: 0 }
      }),
      espaco(8),

      secao("Idiomas"),
      espaco(3),
      bullet([{ text: "Português — Nativo" }]),
      bullet([{ text: "Inglês — Avançado" }]),
    ]
  }]
});

Packer.toBuffer(doc).then(buffer => {
  const out = "outputs/_tmp/cv_coordenador_operacoes_nomad.docx";
  fs.writeFileSync(out, buffer);
  console.log("ok");
}).catch(err => {
  console.error(err);
  process.exit(1);
});
