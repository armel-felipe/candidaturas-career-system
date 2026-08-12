const docx = require('docx');
const fs = require('fs');
const {
  Document, Paragraph, TextRun, TabStopPosition, TabStopType,
  BorderStyle, AlignmentType, LevelFormat, Packer, Numbering
} = docx;

const pt = n => n * 2;

const espaco = (ptSize = 6) => new Paragraph({
  children: [new TextRun({ text: '', size: pt(ptSize), font: 'Arial' })],
  spacing: { after: 0 }
});

const secao = (text) => new Paragraph({
  children: [new TextRun({ text, size: pt(12), font: 'Arial' })],
  border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: '000000', space: 1 } },
  spacing: { before: pt(8), after: pt(3) }
});

const cargoParagraph = (cargo, empresa, periodo) => new Paragraph({
  tabStops: [{ type: TabStopType.RIGHT, position: TabStopPosition.MAX }],
  children: [
    new TextRun({ text: `${cargo} — ${empresa}`, bold: true, size: pt(9), font: 'Arial' }),
    new TextRun({ text: '\t' + periodo, size: pt(9), font: 'Arial' })
  ],
  spacing: { after: 0 }
});

const bullet = (runs) => new Paragraph({
  numbering: { reference: 'bullets', level: 0 },
  children: runs.map(r => new TextRun({ text: r.text, bold: r.bold || false, size: pt(9), font: 'Arial' })),
  spacing: { after: pt(2) }
});

const doc = new Document({
  styles: {
    default: { document: { run: { font: 'Arial', size: pt(9) } } },
    paragraphStyles: [
      { id: 'Normal', name: 'Normal', quickFormat: true, run: { font: 'Arial', size: pt(9) }, paragraph: { spacing: { after: 0 } } },
      { id: 'ListParagraph', name: 'List Paragraph', basedOn: 'Normal', quickFormat: true, run: { font: 'Arial', size: pt(9) }, paragraph: { spacing: { after: 0 } } }
    ]
  },
  numbering: {
    config: [{
      reference: 'bullets',
      levels: [{
        level: 0, format: LevelFormat.BULLET, text: '\u2022',
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
        children: [new TextRun({ text: 'Felipe Armel Dias da Silva', bold: true, size: pt(12), font: 'Arial' })],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [new TextRun({ text: 'linkedin.com/in/felipearmel', size: pt(9), font: 'Arial' })],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [new TextRun({ text: 'São Paulo, SP', size: pt(9), font: 'Arial' })],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [new TextRun({ text: '(11) 98674-8218', size: pt(9), font: 'Arial' })],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [new TextRun({ text: 'armelfelipe@gmail.com', size: pt(9), font: 'Arial' })],
        spacing: { after: 0 }
      }),
      espaco(6),

      // Resumo
      secao('Resumo'),
      espaco(3),
      new Paragraph({
        children: [new TextRun({
          text: 'Diretor de Operações com mais de 6 anos de experiência executiva em logística. No iFood, como Diretor, reduzi o custo logístico em 3% YoY sobre budget de R$300MM e ampliei a cobertura de 400 para 800 cidades. Como Head, gerei saving de R$70M/ano. Na WeHandle, liderei transformação organizacional com automação IA. Busco posição de Diretor de Operações com foco em planejamento estratégico e eficiência operacional.',
          size: pt(9), font: 'Arial'
        })],
        spacing: { after: 0 }
      }),
      espaco(8),

      // Experiência
      secao('Experiência'),
      espaco(3),

      // WeHandle
      cargoParagraph('Head de Operações', 'WeHandle', 'Mai 2024 – Fev 2026'),
      bullet([
        { text: 'Liderei a transformação organizacional da operação de suporte e CX, estruturando processos de atendimento, automação com IA e backoffice com time de 30 pessoas.' }
      ]),
      bullet([
        { text: 'Liderei duas migrações de plataforma de atendimento com implantação de chatbot e IA humanizada, conectando dados via API em três plataformas (Movidesk, CloudHumans, Zendesk).' }
      ]),
      bullet([
        { text: 'Reduzi o custo por atendimento de R$4,14 para R$', bold: false }, { text: '3,61', bold: true }, { text: ' (−13%), elevei o CSAT de 85% para ', bold: false }, { text: '92%', bold: true }, { text: ' e impactei ', bold: false }, { text: '15%', bold: true }, { text: ' na margem bruta da empresa.' }
      ]),
      espaco(6),

      // iFood Diretor
      cargoParagraph('Diretor de Operações', 'iFood', 'Abr 2022 – Mar 2024'),
      bullet([
        { text: 'Fui responsável por gerir as operações logísticas em escala nacional com equipe de ', bold: false }, { text: '240 pessoas', bold: true }, { text: ', cinco lideranças diretas (FieldOps, Meios de Pagamento, Novos Negócios) e budget de R$300MM/ano.' }
      ]),
      bullet([
        { text: 'Conduzi trade-offs entre custo e nível de serviço com S&OP executivo mensal, leitura de DRE semanal e modelagem em Python, SQL e Databricks para tomada de decisão.' }
      ]),
      bullet([
        { text: 'Ampliei a cobertura logística de 400 para ', bold: false }, { text: '800 cidades', bold: true }, { text: ', reduzi o custo comparável em ', bold: false }, { text: '3% YoY', bold: true }, { text: ', elevei o agrupamento de pedidos de 12% para 25% e reduzi a indisponibilidade da frota de 5% para 0,5%.' }
      ]),
      espaco(6),

      // iFood Head
      cargoParagraph('Head de Operações', 'iFood', 'Nov 2018 – Mar 2022'),
      bullet([
        { text: 'Fui responsável por estruturar o planejamento logístico — liveOps, pricing, modelagem de dados e planejamento de frota — com equipe de 28 pessoas.' }
      ]),
      bullet([
        { text: 'Criei métricas em tempo real no Grafana, modelei dados com SQL, PySpark e Databricks e atuei na precificação dinâmica logística e na definição de arquitetura de remuneração dos entregadores.' }
      ]),
      bullet([
        { text: 'Gerei saving de ', bold: false }, { text: 'R$70M/ano', bold: true }, { text: ' com simulador de nível de serviço, distribuí MPOS em ', bold: false }, { text: '352 cidades', bold: true }, { text: ' com zero perda financeira e liderei a expansão logística.' }
      ]),
      espaco(6),

      // VivaReal
      cargoParagraph('Gerente de Planejamento Comercial e Operações', 'VivaReal', 'Mai 2015 – Dez 2017'),
      bullet([
        { text: 'Fui responsável por planejamento comercial e operações, incluindo times de SDR, Qualidade e Cadastro, totalizando 33 pessoas e cinco lideranças diretas.' }
      ]),
      bullet([
        { text: 'Estruturei processos e métricas de CS, definindo régua de onboarding e jornada do cliente — fui o arquiteto da área, que escalou para ', bold: false }, { text: '91 pessoas', bold: true }, { text: ' sob gestão de outros.' }
      ]),
      bullet([
        { text: 'Aumentei a conversão SDR inbound de 18% para ', bold: false }, { text: '50%', bold: true }, { text: ', reduzi o custo de vendas em ', bold: false }, { text: '40%', bold: true }, { text: ' e mantive CSAT acima de ', bold: false }, { text: '92%', bold: true }, { text: ' com churn abaixo de 3%.' }
      ]),
      espaco(6),

      // Trifil S&OP
      cargoParagraph('Coordenador de S&OP', 'Trifil', 'Jan 2010 – Set 2014'),
      bullet([
        { text: 'Fui responsável por fundar a área de S&OP, gerenciando 40K SKUs de produto acabado nas marcas Trifil e Scala em todos os canais de distribuição.' }
      ]),
      bullet([
        { text: 'Conduzi o Projeto Entrega Certa (OTIF, fill rate, acurácia de previsão) reportado ao CEO e gerenciei o MRP corporativo com análise de capacidade de produção.' }
      ]),
      bullet([
        { text: 'Reduzi ', bold: false }, { text: 'R$8M', bold: true }, { text: ' em gastos gerais de fabricação, coordenei Strategic Sourcing de 150K SKUs com redução de 27% no custo de compras e diminuí a falta de produtos em estoque em 40%.' }
      ]),
      espaco(6),

      // Trifil Expedição
      cargoParagraph('Coordenador de Expedição', 'Trifil', 'Jan 2007 – Out 2007'),
      bullet([
        { text: 'Fui responsável por estruturar o centro de expedição com picking, packing e armazenamento, aplicando endereçamento de estoque e inventário rotativo.' }
      ]),
      bullet([
        { text: 'Implantei coletores automáticos para picking e redesenhei o layout, aumentando a capacidade de armazenamento no mesmo espaço físico.' }
      ]),
      bullet([
        { text: 'Elevei a acuracidade do estoque de 85% para ', bold: false }, { text: '98%', bold: true }, { text: ' e reduzi perdas e refugos em 30%.' }
      ]),
      espaco(8),

      // Formação
      secao('Formação'),
      espaco(3),
      bullet([{ text: 'MBA Corporate Strategy — BSP Business School São Paulo (2017)' }]),
      bullet([{ text: 'Engenharia Química — Faculdades Oswaldo Cruz (2014)' }]),
      bullet([{ text: 'Six Sigma Green Belt — Setec Consulting (2020)' }]),
      bullet([{ text: 'ILEAD Liderança para Líder de Líderes — Fundação Dom Cabral (2021)' }]),
      espaco(8),

      // Stack técnica
      secao('Stack técnica'),
      espaco(3),
      new Paragraph({
        children: [new TextRun({ text: 'Excel/VBA · SQL · PySpark · Python · Databricks · Grafana · Salesforce · Zendesk · Power BI · Tableau · ERP Infor LN', size: pt(9), font: 'Arial' })],
        spacing: { after: 0 }
      }),
      espaco(8),

      // Idiomas
      secao('Idiomas'),
      espaco(3),
      bullet([{ text: 'Português — Nativo' }]),
      bullet([{ text: 'Inglês — Avançado' }]),
    ]
  }]
});

const outputPath = 'outputs/felipe_armel_cv_diretor_operacoes_confidencial.docx';
Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync(outputPath, buffer);
  console.log(`DOCX gerado: ${outputPath}`);
});
