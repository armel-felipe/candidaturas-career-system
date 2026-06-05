const fs = require("fs");
const path = require("path");
const {
  AlignmentType,
  BorderStyle,
  Document,
  ExternalHyperlink,
  LevelFormat,
  Packer,
  Paragraph,
  TabStopPosition,
  TabStopType,
  TextRun,
} = require("docx");

const pt = n => n * 2;

const workspace = process.cwd();
const tempDir = path.join(workspace, "outputs", "_tmp");
const tempOutput = path.join(tempDir, "cv_gerencia_geral_de_operacoes_dhl_supply_chain.docx");

function secao(text) {
  return new Paragraph({
    children: [new TextRun({ text, size: pt(12), font: "Arial" })],
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "000000", space: 1 } },
    spacing: { before: pt(6), after: pt(3) },
  });
}

function espaco(ptSize = 6) {
  return new Paragraph({
    children: [new TextRun({ text: "", size: pt(ptSize), font: "Arial" })],
    spacing: { after: 0 },
  });
}

function cargoParagraph(cargo, empresa, periodo) {
  return new Paragraph({
    tabStops: [{ type: TabStopType.RIGHT, position: TabStopPosition.MAX }],
    children: [
      new TextRun({ text: `${cargo} — ${empresa}`, bold: true, size: pt(9), font: "Arial" }),
      new TextRun({ text: `\t${periodo}`, size: pt(9), font: "Arial" }),
    ],
    spacing: { after: 0 },
  });
}

function bullet(runs) {
  const children = runs.map(r => new TextRun({
    text: r.text,
    bold: r.bold || false,
    size: pt(9),
    font: "Arial",
  }));
  return new Paragraph({
    numbering: { reference: "bullets", level: 0 },
    children,
    spacing: { after: pt(2) },
  });
}

function paragrafo(text, options = {}) {
  return new Paragraph({
    children: [new TextRun({
      text,
      size: pt(options.size || 9),
      bold: !!options.bold,
      font: "Arial",
    })],
    spacing: { after: 0 },
  });
}

function hyperlink(text, url) {
  return new Paragraph({
    children: [
      new ExternalHyperlink({
        link: url,
        children: [new TextRun({ text, style: "Hyperlink", size: pt(9), font: "Arial" })],
      }),
    ],
    spacing: { after: 0 },
  });
}

async function main() {
  fs.mkdirSync(tempDir, { recursive: true });

  const doc = new Document({
    styles: {
      default: { document: { run: { font: "Arial", size: pt(9) } } },
      paragraphStyles: [
        {
          id: "Normal",
          name: "Normal",
          quickFormat: true,
          run: { font: "Arial", size: pt(9) },
          paragraph: { spacing: { after: 0 } },
        },
        {
          id: "ListParagraph",
          name: "List Paragraph",
          basedOn: "Normal",
          quickFormat: true,
          run: { font: "Arial", size: pt(9) },
          paragraph: { spacing: { after: 0 } },
        },
      ],
    },
    numbering: {
      config: [{
        reference: "bullets",
        levels: [{
          level: 0,
          format: LevelFormat.BULLET,
          text: "\u2022",
          alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 360, hanging: 180 } } },
        }],
      }],
    },
    sections: [{
      properties: {
        page: {
          size: { width: 11906, height: 16838 },
          margin: { top: 720, right: 504, bottom: 720, left: 504 },
        },
      },
      children: [
        paragrafo("Felipe Armel Dias da Silva", { size: 12, bold: true }),
        hyperlink("linkedin.com/in/felipearmel", "https://linkedin.com/in/felipearmel"),
        paragrafo("São Paulo, SP"),
        hyperlink("(11) 98674-8218", "https://wa.me/5511986748218"),
        hyperlink("armelfelipe@gmail.com", "mailto:armelfelipe@gmail.com"),

        espaco(8),
        secao("Resumo"),
        espaco(3),
        paragrafo("Executivo sênior com base em engenharia e trajetória em operações, supply chain e atendimento. No iFood, como Diretor de Operações, gerenciei budget de R$300MM/ano e expansão de 400 para 800 cidades; como Head, gerei saving de R$70MM/ano. Na Trifil, elevei a acuracidade de estoque a 98% e reduzi R$8MM de GGF. Busco posição de Gerência Geral de Operações em logística."),

        espaco(8),
        secao("Experiência"),

        espaco(3),
        cargoParagraph("Head de Operações", "wehandle", "Mai 2024 – Fev 2026"),
        bullet([
          { text: "Fui responsável pela operação de suporte e CX da wehandle, liderando time de " },
          { text: "30 pessoas", bold: true },
          { text: " com foco em " },
          { text: "Customer Relationship", bold: true },
          { text: ", " },
          { text: "People Management", bold: true },
          { text: ", produtividade, orçamento de custos e estabilidade dos " },
          { text: "SLAs", bold: true },
          { text: "." },
        ]),
        bullet([
          { text: "Implementei automação com IA, atendimento via WhatsApp, integrações por API e gestão de backlog com ClickUp para dar escala, visibilidade e ritmo de execução à operação." },
        ]),
        bullet([
          { text: "Alcancei SLA em " },
          { text: "95% dos tickets", bold: true },
          { text: ", elevei o CSAT de " },
          { text: "85% para 92%", bold: true },
          { text: ", reduzi o custo por atendimento de " },
          { text: "R$4,14 para R$3,61", bold: true },
          { text: " e gerei impacto de " },
          { text: "15%", bold: true },
          { text: " na margem bruta." },
        ]),

        espaco(6),
        cargoParagraph("Diretor de Operações", "iFood", "Abr 2022 – Mar 2024"),
        bullet([
          { text: "Fui responsável por operações logísticas nacionais no iFood, com equipe de " },
          { text: "240 pessoas", bold: true },
          { text: ", budget de " },
          { text: "R$300MM/ano", bold: true },
          { text: " e atuação direta sobre alavancas reais de " },
          { text: "P&L", bold: true },
          { text: " em entrega+, meios de pagamento e frotas dedicadas." },
        ]),
        bullet([
          { text: "Conduzi S&OP executivo, governança semanal de custo logístico, modelagem com Python, SQL e Databricks e decisões de capacity planning para equilibrar custo, nível de serviço e EBITDA." },
        ]),
        bullet([
          { text: "Ampliei a cobertura de " },
          { text: "400 para 800 cidades", bold: true },
          { text: ", entreguei " },
          { text: "Cost Reduction", bold: true },
          { text: " de " },
          { text: "3% YoY", bold: true },
          { text: " no custo logístico comparável e aumentei pedidos agrupados de " },
          { text: "12% para 25%", bold: true },
          { text: "." },
        ]),

        espaco(6),
        cargoParagraph("Head de Operações", "iFood", "Nov 2018 – Mar 2022"),
        bullet([
          { text: "Fui responsável por liveOps, regionalOps, pricing, modelagem de dados e planejamento de frota no iFood, liderando " },
          { text: "28 pessoas", bold: true },
          { text: " com foco em " },
          { text: "Operational Excellence", bold: true },
          { text: " e nível de serviço." },
        ]),
        bullet([
          { text: "Estruturei torre de operações, métricas em tempo real no Grafana, simulador de nível de serviço e regras operacionais de pricing para sustentar " },
          { text: "Service Level", bold: true },
          { text: " por cidade." },
        ]),
        bullet([
          { text: "Gerei saving de " },
          { text: "R$70MM/ano", bold: true },
          { text: ", reduzi cancelamentos em " },
          { text: "60%", bold: true },
          { text: " no México, cortei o custo de distribuição de MPOS em " },
          { text: "80%", bold: true },
          { text: " e reduzi o prazo de entrega de " },
          { text: "14 para 2 dias", bold: true },
          { text: "." },
        ]),

        espaco(6),
        cargoParagraph("Gerente de Planejamento Comercial e Operações", "VivaReal", "Mai 2015 – Dez 2017"),
        bullet([
          { text: "Fui responsável por planejamento comercial, qualidade, SDR e cadastro de imóveis na VivaReal, liderando " },
          { text: "33 pessoas", bold: true },
          { text: " e sustentando interface direta com CFO, operação, cliente e " },
          { text: "Compliance", bold: true },
          { text: " documental." },
        ]),
        bullet([
          { text: "Estruturei onboarding, dados diários em SQL e dashboards, além de desenhar a área de CS e contratar sua liderança, sempre como arquiteto da área e não gestor de CS." },
        ]),
        bullet([
          { text: "Elevei a conversão inbound de " },
          { text: "18% para 50%", bold: true },
          { text: ", reduzi o custo de vendas em " },
          { text: "40%", bold: true },
          { text: ", recuperei " },
          { text: "R$1MM", bold: true },
          { text: " em inadimplência e sustentei " },
          { text: "NPS de 80%", bold: true },
          { text: " com CSAT acima de 92%." },
        ]),

        espaco(6),
        cargoParagraph("Coordenador de S&OP", "Scalina (Trifil)", "Jan 2010 – Set 2014"),
        bullet([
          { text: "Fui responsável por criar a área de S&OP do zero, sustentando por " },
          { text: "4 anos", bold: true },
          { text: " a agenda de planejamento, MRP corporativo, OTIF, fill rate e " },
          { text: "KPIs", bold: true },
          { text: " em operação com " },
          { text: "40 mil SKUs", bold: true },
          { text: "." },
        ]),
        bullet([
          { text: "Desenvolvi simulador em Excel VBA, política de estoque de segurança, calendário com MS-Project e rotinas de S&OE para alinhar comercial, PCP, capacidade e outsourcing." },
        ]),
        bullet([
          { text: "Reduzi " },
          { text: "R$8MM", bold: true },
          { text: " de GGF, entreguei economia real de " },
          { text: "R$4,6MM", bold: true },
          { text: " até agosto no projeto GGF 2014 e preservei o atendimento da operação em todos os canais." },
        ]),

        espaco(6),
        cargoParagraph("Coordenador de Inteligência Comercial", "Scalina (Trifil)", "Jan 2009 – Dez 2009"),
        bullet([
          { text: "Fui responsável por criar a área de inteligência comercial com " },
          { text: "2 pessoas", bold: true },
          { text: ", apoiando pricing, indicadores, tendências e decisões de margem para a diretoria e a rede de franquias." },
        ]),
        bullet([
          { text: "Estruturei BI, normalizei dados do ERP, automatizei relatórios e desenhei algoritmo em Excel e VBA para priorização de pedidos com foco em margem e faturamento." },
        ]),
        bullet([
          { text: "Ampliei o faturamento de " },
          { text: "R$80MM para R$120MM/ano", bold: true },
          { text: " e reduzi o tempo de geração de relatórios de " },
          { text: "4 horas para 14 minutos", bold: true },
          { text: "." },
        ]),

        espaco(6),
        cargoParagraph("Coordenador de Planejamento de Materiais", "Scalina (Trifil)", "Nov 2007 – Dez 2008"),
        bullet([
          { text: "Fui responsável pelo planejamento de materiais, compras e capacidade futura na Trifil, conduzindo Strategic Sourcing em mais de " },
          { text: "150 mil SKUs", bold: true },
          { text: " para reforçar abastecimento e disciplina de custo." },
        ]),
        bullet([
          { text: "Estruturei critérios de alteração do plano de produção, planejamento de compras de aviamentos, embalagens e fios e " },
          { text: "Project Management", bold: true },
          { text: " para aquisição de 24 teares circulares automatizados." },
        ]),
        bullet([
          { text: "Reduzi o custo de compras em " },
          { text: "27%", bold: true },
          { text: ", baixei a falta de produtos em estoque em " },
          { text: "40%", bold: true },
          { text: ", melhorei o giro de " },
          { text: "8 para 6 meses", bold: true },
          { text: " e reduzi o custo total de fabricação em " },
          { text: "15%", bold: true },
          { text: "." },
        ]),

        espaco(6),
        cargoParagraph("Coordenador de Expedição", "Scalina (Trifil)", "Jan 2007 – Out 2007"),
        bullet([
          { text: "Fui responsável pelo " },
          { text: "Centro de Distribuicao", bold: true },
          { text: " da Trifil, cobrindo " },
          { text: "Warehouse Operations", bold: true },
          { text: ", picking, packing, armazenamento e devoluções com foco em produtividade, qualidade de entrega e acuracidade." },
        ]),
        bullet([
          { text: "Implementei endereçamento, inventário rotativo, coletores por radiofrequência e ERP LN, além de redesenhar layout e criar sistema visual de abastecimento do picking." },
        ]),
        bullet([
          { text: "Elevei a " },
          { text: "Inventory Accuracy", bold: true },
          { text: " de " },
          { text: "85% para 98%", bold: true },
          { text: ", aumentei a produtividade em " },
          { text: "35%", bold: true },
          { text: ", reduzi perdas em " },
          { text: "30%", bold: true },
          { text: " e cortei em " },
          { text: "50%", bold: true },
          { text: " o tempo de preparo de pedidos customizados." },
        ]),

        espaco(6),
        cargoParagraph("Analista de Processos e Sistemas", "Scalina (Trifil)", "Jan 2006 – Dez 2006"),
        bullet([
          { text: "Fui responsável por iniciativas de " },
          { text: "Continuous Improvement", bold: true },
          { text: " na planta de Guarulhos, implantando gestão por objetivos, PDCA, KPIs e planos de ação na produção." },
        ]),
        bullet([
          { text: "Conduzi a seleção, a viabilidade econômica e a implantação de um sistema de tinturaria automatizada, além de criar controles automatizados de capacidade e eficiência das máquinas." },
        ]),
        bullet([
          { text: "Reduzi os custos de produção em " },
          { text: "40%", bold: true },
          { text: ", capturei payback real de " },
          { text: "1,5 ano", bold: true },
          { text: " e aumentei a eficiência das máquinas em " },
          { text: "12%", bold: true },
          { text: "." },
        ]),

        espaco(8),
        secao("Formação"),
        espaco(3),
        bullet([{ text: "ILead Liderança para Líder de Líderes — Fundação Dom Cabral (2021)" }]),
        bullet([{ text: "Six Sigma Green Belt — Setec Consulting (2020)" }]),
        bullet([{ text: "MBA Corporate Strategy — BSP Business School São Paulo (2016–2017)" }]),
        bullet([{ text: "Engenheiro Químico — Faculdades Oswaldo Cruz (2014)" }]),

        espaco(8),
        secao("Stack técnica"),
        espaco(3),
        paragrafo("Excel/VBA · SQL · Python · Databricks · Grafana · Power BI · ERP Infor LN · WMS · MS-Project · Zendesk"),

        espaco(8),
        secao("Idiomas"),
        espaco(3),
        bullet([{ text: "Português — Nativo" }]),
        bullet([{ text: "Inglês — Avançado" }]),
      ],
    }],
  });

  const buffer = await Packer.toBuffer(doc);
  fs.writeFileSync(tempOutput, buffer);
  console.log("ok");
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
