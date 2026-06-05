const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, TabStopType, TabStopPosition,
  AlignmentType, LevelFormat, BorderStyle, ExternalHyperlink
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

const headerLink = (text, url) => new ExternalHyperlink({
  children: [new TextRun({ text, style: "Hyperlink", size: pt(9), font: "Arial" })],
  link: url
});

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
    properties: { page: { margin: { top: 720, right: 504, bottom: 720, left: 504 } } },
    children: [
      // CABECALHO
      new Paragraph({
        children: [new TextRun({ text: "Felipe Armel Dias da Silva", bold: true, size: pt(12), font: "Arial" })],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [headerLink("linkedin.com/in/felipearmel", "https://linkedin.com/in/felipearmel")],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [new TextRun({ text: "S\u00e3o Paulo, SP", size: pt(9), font: "Arial" })],
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
      espaco(8),

      // RESUMO
      secao("Resumo"),
      espaco(3),
      new Paragraph({
        children: [new TextRun({
          text: "Executivo S\u00eanior com 25+ anos de carreira em supply chain management, opera\u00e7\u00f5es e crescimento. Reduzi R$70MM/ano em custo log\u00edstico como Diretor no iFood e elevei margem bruta em 15% reestruturando opera\u00e7\u00e3o early-stage na wehandle. Constru\u00ed \u00e1reas do zero em m\u00faltiplos contextos \u2014 de CS em marketplace a S&OP em ind\u00fastria de 40K SKUs. Busco posi\u00e7\u00e3o de Diretor Operacional (COO) na Ocean Drop.",
          size: pt(9), font: "Arial"
        })],
        spacing: { after: 0 }
      }),
      espaco(8),

      // EXPERIENCIA
      secao("Experi\u00eancia"),
      espaco(3),

      // wehandle
      cargoParagraph("Head de Opera\u00e7\u00f5es", "wehandle", "Mai 2024 \u2013 Fev 2026"),
      bullet([{ text: "Fui respons\u00e1vel por gerir a opera\u00e7\u00e3o de suporte e CX com autonomia total de escopo em ambiente early-stage, liderando time de 30 pessoas com foco em margem bruta, CSAT, SLA e cost reduction.", bold: false }]),
      bullet([{ text: "Estruturei a \u00e1rea de CX do zero, implantei Zendesk com modelo IA first e canal WhatsApp, modelei dados de tr\u00eas plataformas via API e conectei ao datalake para decis\u00e3o em tempo real.", bold: false }]),
      bullet([{ text: "Elevei ", bold: false }, { text: "margem bruta em 15%", bold: true }, { text: ", reduzi custo total por atendimento de R$4,14 para R$3,61 (\u221213%) e TME de 20 para 8 minutos, alcancei CSAT de 92% e SLA em 95% dos tickets, com backlog de produto reduzido em 60%.", bold: false }]),
      espaco(6),

      // iFood Diretor
      cargoParagraph("Diretor de Opera\u00e7\u00f5es", "iFood", "Abr 2022 \u2013 Mar 2024"),
      bullet([{ text: "Fui respons\u00e1vel pelas opera\u00e7\u00f5es log\u00edsticas nacionais com equipe de ~240 pessoas cobrindo FieldOps, Meios de Pagamento e Novos Neg\u00f3cios, gerindo budget de ", bold: false }, { text: "R$300MM/ano", bold: true }, { text: " e conduzindo executive governance com rituais mensais de S&OP perante o C-level.", bold: false }]),
      bullet([{ text: "Conduzi S&OP executivo mensal integrando marketing, clima, frota e expans\u00e3o em processo \u00fanico de planejamento, com leitura semanal de DRE, modelagem em Python, SQL e Databricks, e capacity planning por cidade.", bold: false }]),
      bullet([{ text: "Ampliei cobertura de ", bold: false }, { text: "400 para 800 cidades", bold: true }, { text: ", reduzi custo compar\u00e1vel em 3% YoY mantendo SLA em 30M pedidos/m\u00eas, reduzi indisponibilidade de frota de 5% para 1% e elevei entregas agrupadas de 12% para 25% atingindo breakeven.", bold: false }]),
      espaco(6),

      // iFood Head
      cargoParagraph("Head de Opera\u00e7\u00f5es", "iFood", "Nov 2018 \u2013 Mar 2022"),
      bullet([{ text: "Fui respons\u00e1vel por liderar equipe de 28 pessoas em liveOps, regionalOps, pricing, modelagem de dados e planejamento de frota, implementando torre de opera\u00e7\u00f5es e dashboards em tempo real no Grafana.", bold: false }]),
      bullet([{ text: "Estruturei capacity planning com simulador propriet\u00e1rio de operational excellence, conduzi testes controlados de elasticidade de pre\u00e7o e criei ferramentas de restri\u00e7\u00e3o de raio por bairro para equilibrar oferta e demanda log\u00edstica.", bold: false }]),
      bullet([{ text: "Gerei saving de ", bold: false }, { text: "R$70MM/ano", bold: true }, { text: " mantendo n\u00edvel de servi\u00e7o, reduzi custo de distribui\u00e7\u00e3o de MPOS em 80% e prazo de 14 para 2 dias, e reduzi cancelamentos no M\u00e9xico em 60%.", bold: false }]),
      espaco(6),

      // VivaReal
      cargoParagraph("Gerente de Planejamento Comercial e Opera\u00e7\u00f5es", "VivaReal", "Mai 2015 \u2013 Dez 2017"),
      bullet([{ text: "Fui respons\u00e1vel pelo planejamento comercial e opera\u00e7\u00f5es da BU de usados e lan\u00e7amentos, com time de 33 pessoas em Qualidade, SDR e cadastro de im\u00f3veis, e fui o arquiteto da \u00e1rea de CS que escalou para ", bold: false }, { text: "91 pessoas", bold: true }, { text: " sob gest\u00e3o de outros.", bold: false }]),
      bullet([{ text: "Estruturei processo de SDR inbound com r\u00e9gua de qualifica\u00e7\u00e3o, pipeline no Salesforce, algoritmo VBA de aloca\u00e7\u00e3o de estoque e sistema de telefonia digital para atendimento p\u00f3s-venda.", bold: false }]),
      bullet([{ text: "Elevei convers\u00e3o SDR inbound de 18% para 50% com \u221240% de custo de vendas, aumentei faturamento de R$80M para R$120M/ano, recuperei R$1M em inadimplentes e alcancei NPS de 80% e CSAT acima de 92%.", bold: false }]),
      espaco(6),

      // Trifil S&OP
      cargoParagraph("Coordenador de S&OP", "Trifil", "Jan 2010 \u2013 Set 2014"),
      bullet([{ text: "Fui respons\u00e1vel por criar e operar a \u00e1rea de S&OP por 4 anos, gerenciando supply chain management de ", bold: false }, { text: "40K SKUs", bold: true }, { text: " de produto acabado em duas marcas e todos os canais de distribui\u00e7\u00e3o, com equipe dedicada \u00e0 gera\u00e7\u00e3o de indicadores e planejamento.", bold: false }]),
      bullet([{ text: "Conduzi S&OE semanal com recalibra\u00e7\u00e3o de oportunidades, defini pol\u00edtica de safety stock, gerenciei MRP corporativo e outsourcing, e implementei OPEX management via projeto de redu\u00e7\u00e3o de custos industriais.", bold: false }]),
      bullet([{ text: "Reduzi ", bold: false }, { text: "R$8MM", bold: true }, { text: " de GGF do P&L com economia de R$4,6M acima da meta, estruturei indicadores cr\u00edticos (OTIF, fill rate, inventory management) reportados ao CEO e mantive equil\u00edbrio entre n\u00edvel de servi\u00e7o e liquidez financeira por 4 anos.", bold: false }]),
      espaco(6),

      // Trifil Exp/Mat
      cargoParagraph("Coordenador de Expedi\u00e7\u00e3o e Planejamento de Materiais", "Trifil", "Jan 2007 \u2013 Dez 2008"),
      bullet([{ text: "Fui respons\u00e1vel por gerir centro de expedi\u00e7\u00e3o com picking, packing e armazenamento, e pelo planejamento de materiais de 150K+ SKUs, como key-user dos m\u00f3dulos de expedi\u00e7\u00e3o e planejamento do ERP Infor LN.", bold: false }]),
      bullet([{ text: "Implantei coletores RF e wi-fi unindo separa\u00e7\u00e3o e confer\u00eancia, redesenhei layout e endere\u00e7amento de estoque, e apliquei Strategic Sourcing com an\u00e1lise de fornecedores e dimensionamento de investimentos em capacidade produtiva.", bold: false }]),
      bullet([{ text: "Elevei acur\u00e1cia de estoque de 85% para ", bold: false }, { text: "98%", bold: true }, { text: " e produtividade em 35% com \u221230% de perdas, reduzi custo de compras em 27% e falta de estoque em 40%, melhorei giro de 8 para 6 meses e reduzi custo de fabrica\u00e7\u00e3o em 15%.", bold: false }]),
      espaco(8),

      // FORMACAO
      secao("Forma\u00e7\u00e3o"),
      espaco(3),
      bullet([{ text: "ILEad \u2014 Lideran\u00e7a para L\u00edder de L\u00edderes \u2014 Funda\u00e7\u00e3o Dom Cabral (2021)", bold: false }]),
      bullet([{ text: "Six Sigma Green Belt \u2014 Setec Consulting (2020)", bold: false }]),
      bullet([{ text: "MBA Corporate Strategy \u2014 BSP Business School S\u00e3o Paulo (2016\u20132017)", bold: false }]),
      bullet([{ text: "Planejamento e Or\u00e7amento \u2014 Saint Paul Escola de Neg\u00f3cios (2016)", bold: false }]),
      bullet([{ text: "Engenharia Qu\u00edmica \u2014 Faculdades Oswaldo Cruz (2014)", bold: false }]),
      espaco(8),

      // STACK
      secao("Stack t\u00e9cnica"),
      espaco(3),
      new Paragraph({
        children: [new TextRun({ text: "SQL \u00b7 Python \u00b7 Databricks \u00b7 Excel/VBA \u00b7 Grafana \u00b7 Zendesk \u00b7 ERP Infor LN \u00b7 WMS \u00b7 Power BI \u00b7 Tableau \u00b7 Metabase \u00b7 Salesforce", size: pt(9), font: "Arial" })],
        spacing: { after: 0 }
      }),
      espaco(8),

      // IDIOMAS
      secao("Idiomas"),
      espaco(3),
      bullet([{ text: "Portugu\u00eas \u2014 Nativo", bold: false }]),
      bullet([{ text: "Ingl\u00eas \u2014 Avan\u00e7ado", bold: false }])
    ]
  }]
});

const outDir = "outputs/_tmp";
if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });
const outputPath = `${outDir}/cv_ocean_drop_coo_concise.docx`;

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync(outputPath, buffer);
  console.log("ok");
});
