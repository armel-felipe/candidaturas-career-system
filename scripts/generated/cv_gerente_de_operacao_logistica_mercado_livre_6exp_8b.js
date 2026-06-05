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
const rawOutput = path.join(tempDir, "felipe_armel_cv_gerente_de_operacao_logistica_mercado_livre.docx");

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
      new TextRun({ text: "\t" + periodo, size: pt(9), font: "Arial" }),
    ],
    spacing: { after: 0 },
  });
}

function bullet(runs) {
  return new Paragraph({
    numbering: { reference: "bullets", level: 0 },
    children: runs.map(run => new TextRun({ text: run.text, bold: !!run.bold, size: pt(9), font: "Arial" })),
    spacing: { after: pt(2) },
  });
}

function paragraphRuns(runs) {
  return new Paragraph({
    children: runs.map(run => new TextRun({ text: run.text, bold: !!run.bold, size: pt(9), font: "Arial" })),
    spacing: { after: 0 },
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
        style: { paragraph: { indent: { left: 360, hanging: 180 } } },
      }],
    }],
  },
  styles: {
    default: { document: { run: { font: "Arial", size: pt(9) } } },
    paragraphStyles: [
      { id: "Normal", name: "Normal", quickFormat: true, run: { font: "Arial", size: pt(9) }, paragraph: { spacing: { after: 0 } } },
      { id: "ListParagraph", name: "List Paragraph", basedOn: "Normal", quickFormat: true, run: { font: "Arial", size: pt(9) }, paragraph: { spacing: { after: 0 } } },
    ],
  },
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 720, right: 504, bottom: 720, left: 504 } } },
    children: [
      new Paragraph({ children: [new TextRun({ text: "Felipe Armel Dias da Silva", bold: true, size: pt(12), font: "Arial" })], spacing: { after: 0 } }),
      new Paragraph({ children: [new ExternalHyperlink({ link: "https://linkedin.com/in/felipearmel", children: [new TextRun({ text: "linkedin.com/in/felipearmel", style: "Hyperlink", size: pt(9), font: "Arial" })] })], spacing: { after: 0 } }),
      new Paragraph({ children: [new TextRun({ text: "São Paulo, SP", size: pt(9), font: "Arial" })], spacing: { after: 0 } }),
      new Paragraph({ children: [new ExternalHyperlink({ link: "https://wa.me/5511986748218", children: [new TextRun({ text: "(11) 98674-8218", style: "Hyperlink", size: pt(9), font: "Arial" })] })], spacing: { after: 0 } }),
      new Paragraph({ children: [new ExternalHyperlink({ link: "mailto:armelfelipe@gmail.com", children: [new TextRun({ text: "armelfelipe@gmail.com", style: "Hyperlink", size: pt(9), font: "Arial" })] })], spacing: { after: 0 } }),

      espaco(8),
      secao("Resumo"),
      espaco(3),
      paragraphRuns([
        { text: "Engenheiro Químico com MBA Corporate Strategy — BSP e carreira em operações de escala. No iFood, como Diretor de Operações, atuei em " },
        { text: "Logistics Operations", bold: true },
        { text: ", " },
        { text: "Capacity Planning", bold: true },
        { text: " e " },
        { text: "Team Leadership", bold: true },
        { text: " com budget de " },
        { text: "R$300MM/ano", bold: true },
        { text: ", cobertura de " },
        { text: "400 para 800 cidades", bold: true },
        { text: " e saving de " },
        { text: "R$70MM/ano", bold: true },
        { text: ". Na Trifil, estruturei " },
        { text: "Supply Chain Management", bold: true },
        { text: ", " },
        { text: "Warehouse Operations", bold: true },
        { text: " e " },
        { text: "KPI Management", bold: true },
        { text: "." },
      ]),

      espaco(8),
      secao("Experiência"),
      espaco(3),

      cargoParagraph("Head de Operações", "wehandle", "Mai 2024 – Fev 2026"),
      bullet([{ text: "Fui responsável por uma operação de suporte com time de 30 pessoas, orçamento de custos e foco em Operational Efficiency, CSAT, SLA e margem bruta de 15%." }]),
      bullet([{ text: "Liderei migrações de plataforma, automação com IA, integração via API e Data-Driven Decision Making com Python, SQL, Metabase e Zendesk para operar com indicadores em tempo real." }]),
      bullet([{ text: "Reduzi o custo por atendimento de R$4,14 para R$3,61 (-13%), elevei o CSAT de 85% para 92% e reduzi o TME de 20 para 8 minutos." }]),
      bullet([{ text: "Criei uma área de CX para organizar prioridades de produto e suporte, reduzindo o backlog em 60% e elevando o SLA de execução de 67% para 85%." }]),
      bullet([{ text: "Conectei dados de atendimento ao datalake via API, acelerando a leitura operacional em três plataformas e antecipando a área de dados por pelo menos 3 meses." }]),
      bullet([{ text: "Introduzi WhatsApp como canal de atendimento, reduzindo o custo por atendimento de R$1,04 para R$0,56 nesse canal." }]),
      bullet([{ text: "Implementei Zendesk como plataforma central de atendimento e consolidei automações com IA humanizada para ganho de produtividade de 25%." }]),
      bullet([{ text: "Reestruturei a operação de suporte com foco em eficiência financeira, impactando 15% da margem bruta pela alavanca de custo de atendimento." }]),

      espaco(6),

      cargoParagraph("Head e Diretor de Operações", "iFood", "Nov 2018 – Mar 2024"),
      bullet([{ text: "Fui responsável por Logistics Operations em marketplace com Team Leadership de ~240 pessoas, budget de R$300MM/ano e gestão de FieldOps, pagamentos e novos negócios." }]),
      bullet([{ text: "Conduzi Capacity Planning, Supply Chain Management operacional e Data-Driven Decision Making com S&OP executivo, Python, SQL, Databricks e Grafana para equilibrar custo, cobertura e SLA." }]),
      bullet([{ text: "Ampliei a cobertura de 400 para 800 cidades, reduzi o custo comparável em 3% YoY e gerei saving de R$70MM/ano com simulador de nível de serviço." }]),
      bullet([{ text: "Reduzi a indisponibilidade de frota de 5% para 1% no Brasil e de 5,4% para 0,5% nas top 6 cidades, elevando a estabilidade da rede." }]),
      bullet([{ text: "Aumentei a porcentagem de pedidos agrupados de 12% para 25%, atingindo breakeven da operação sem perder qualidade de entrega." }]),
      bullet([{ text: "Estruturei uma lógica de distribuição de MPOS que reduziu o custo em 80% e o prazo de 14 para 2 dias, com cobertura em 352 cidades." }]),
      bullet([{ text: "Implantei pagamento em dinheiro em 352 cidades, com 200K pedidos/mês e zero risco financeiro, ampliando acessibilidade da operação." }]),
      bullet([{ text: "Liderei o rito executivo mensal de S&OP da logística, conectando marketing, promoções, clima, frota e expansão geográfica em um processo único de planejamento." }]),

      espaco(6),

      cargoParagraph("Head de Operações", "iFood", "Nov 2018 – Mar 2022"),
      bullet([{ text: "Fui responsável por Transportation e liveOps em last mile, com time de 28 pessoas em pricing, modelagem, regionalOps e planejamento de frota." }]),
      bullet([{ text: "Estruturei KPI Management, simulador de nível de serviço, SQL e Databricks para monitorar saturação logística, oferta e nível de serviço em tempo real." }]),
      bullet([{ text: "Gerei saving de R$70MM/ano e reduzi a indisponibilidade de frota de 5% para 1% com leitura contínua de performance operacional." }]),
      bullet([{ text: "Ajustei o raio de entrega e reduzi cancelamentos em 60% no México ao redesenhar a torre de operações local." }]),
      bullet([{ text: "Estabeleci uma distribuição de MPOS que reduziu o custo em 80% e o prazo de 14 para 2 dias, com cobertura em 352 cidades." }]),
      bullet([{ text: "Criei o indicador de entrega rápida para correlacionar frequência de pedidos, promessa e tolerância ao atraso do cliente." }]),
      bullet([{ text: "Estruturei dashboards em tempo real no Grafana e dashboards analíticos em Tableau para apoiar decisões com operação e engenharia de dados." }]),
      bullet([{ text: "Modelei dados com Python, SQL e Databricks para sustentar decisão de preço, oferta e capacidade sem depender de leitura manual." }]),

      espaco(6),

      cargoParagraph("Gerente de Planejamento Comercial e Operações", "VivaReal", "Mai 2015 – Dez 2017"),
      bullet([{ text: "Fui responsável por planejamento comercial e operações com 33 pessoas e 5 lideranças, cobrindo Qualidade, SDR e cadastro de imóveis." }]),
      bullet([{ text: "Fui arquiteto da área de CS: desenhei processos, defini régua de onboarding, contratei liderança e preparei a área para 91 pessoas sob gestão de outros." }]),
      bullet([{ text: "Reduzi churn para menos de 3% ao mês, alcancei NPS de 80% e CSAT acima de 92% com especialização por jornada do cliente." }]),
      bullet([{ text: "Aumentei a conversão da esteira de SDR de 18% para 50% e reduzi o custo de vendas em 40% com um fluxo mais disciplinado." }]),
      bullet([{ text: "Recuperei R$1M em receita com área de recuperação de inadimplentes em campanhas de lançamentos." }]),
      bullet([{ text: "Implementei recebimento por cartão de crédito, modernizando o processo que só aceitava boleto." }]),
      bullet([{ text: "Implantei telefonia digital para o pós-venda e melhorei a governança operacional entre comercial, produto e operações." }]),
      bullet([{ text: "Resolvi a falta de dados com SQL, Excel automatizado e dashboards diários para suportar metas e execução comercial." }]),

      espaco(6),

      cargoParagraph("Coordenador de S&OP", "Scalina (Trifil)", "Jan 2010 – Set 2014"),
      bullet([{ text: "Fui responsável por criar a área de Supply Chain Management do zero, com 40K SKUs, MRP corporativo, S&OP e interface entre comercial, PCP e fabricação." }]),
      bullet([{ text: "Estruturei KPI Management, Continuous Improvement, Excel/VBA, simulador de MRP e gestão de cenários para OTIF, fill rate e estoque de segurança." }]),
      bullet([{ text: "Reduzi R$8M de GGF, sustentei os ritos por 4 anos e levei o Projeto Entrega Certa ao reporte direto para o CEO." }]),
      bullet([{ text: "Reduzi custo de compras em 27%, falta de estoque em 40% e melhorei o giro de 8 para 6 meses com strategic sourcing." }]),
      bullet([{ text: "Gerenciei 40K SKUs em duas marcas e todos os canais de distribuição, conectando demanda, supply e execução." }]),
      bullet([{ text: "Defini política de estoque de segurança para SKUs de maior giro, equilibrando entrega e liquidez financeira." }]),
      bullet([{ text: "Coordenei outsourcing nacional e internacional como parte do MRP corporativo e da análise de capacidade de produção." }]),
      bullet([{ text: "Utilizei MS-Project e caminho crítico para estruturar calendário de S&OP com menor risco de ruptura no planejamento." }]),

      espaco(6),

      cargoParagraph("Coordenador de Expedição", "Scalina (Trifil)", "Jan 2007 – Out 2007"),
      bullet([{ text: "Fui responsável por Warehouse Operations no centro de expedição, cobrindo picking, packing, armazenamento, inventário rotativo e ERP LN." }]),
      bullet([{ text: "Implantei WMS, coletores RF e wi-fi, endereçamento de estoque e gestão visual de abastecimento para elevar controle e fluidez da operação." }]),
      bullet([{ text: "Elevei a acurácia de estoque de 85% para 98%, aumentei a produtividade em 35% e reduzi perdas e refugos em 30%." }]),
      bullet([{ text: "Reduzi o tempo de preparo de pedidos customizados em 50% com redesenho de layout e criação da área de packing." }]),
      bullet([{ text: "Melhorei a organização física do armazém e aumentei a capacidade de armazenamento com o mesmo espaço físico." }]),
      bullet([{ text: "Implementei sistema visual de abastecimento do picking para reduzir pedidos incompletos e melhorar a confiabilidade do fluxo." }]),
      bullet([{ text: "Fui responsável pela implantação dos módulos de expedição e planejamento do ERP LN, conectando operação e sistema." }]),
      bullet([{ text: "Gerenciei o Projeto Entrega Certa com KPIs de OTIF, acurácia da previsão de vendas, acurácia da produção, giro de estoque e produtividade da expedição." }]),

      espaco(8),
      secao("Formação"),
      espaco(3),
      bullet([{ text: "MBA Corporate Strategy — BSP Business School São Paulo (2016–2017)" }]),
      bullet([{ text: "Engenheiro Químico — Faculdades Oswaldo Cruz (2014)" }]),
      bullet([{ text: "Six Sigma Green Belt — Setec Consulting (2020)" }]),
      bullet([{ text: "ILEad — Liderança para Líder de Líderes — Fundação Dom Cabral (2021)" }]),

      espaco(8),
      secao("Stack técnica"),
      espaco(3),
      paragraphRuns([{ text: "SQL · Python · Databricks · Grafana · Excel/VBA · WMS · ERP Infor LN · Metabase" }]),

      espaco(8),
      secao("Idiomas"),
      espaco(3),
      bullet([{ text: "Português — Nativo" }]),
      bullet([{ text: "Inglês — Avançado" }]),
    ],
  }],
});

Packer.toBuffer(doc).then(buffer => {
  fs.mkdirSync(tempDir, { recursive: true });
  fs.writeFileSync(rawOutput, buffer);
  console.log("ok");
});
