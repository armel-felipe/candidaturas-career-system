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
const tmpDir = path.join(workspace, "outputs", "_tmp");
const outputPath = path.join(tmpDir, "cv_gerente_projetos_otimizacao_mercado_livre.docx");

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
    children: runs.map(run => new TextRun({
      text: run.text,
      bold: run.bold || false,
      size: pt(9),
      font: "Arial",
    })),
    spacing: { after: pt(2) },
  });
}

function paragraph(text, options = {}) {
  return new Paragraph({
    children: [new TextRun({ text, size: pt(options.size || 9), bold: !!options.bold, font: "Arial" })],
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
  fs.mkdirSync(tmpDir, { recursive: true });

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
          margin: { top: 720, right: 504, bottom: 720, left: 504 },
        },
      },
      children: [
        paragraph("Felipe Armel Dias da Silva", { size: 12, bold: true }),
        hyperlink("linkedin.com/in/felipearmel", "https://linkedin.com/in/felipearmel"),
        paragraph("São Paulo, SP"),
        hyperlink("(11) 98674-8218", "https://wa.me/5511986748218"),
        hyperlink("armelfelipe@gmail.com", "mailto:armelfelipe@gmail.com"),

        espaco(8),
        secao("Resumo"),
        paragraph("Executivo Sênior com 20+ anos em operações, supply chain e logística. No iFood, gerenciei budget de R$300MM/ano e gerei saving de R$70MM/ano com sistema de simulação de frota, expandindo cobertura de 400 para 800 cidades. Na wehandle, reduzi custo por atendimento em 13% e cortei backlog de produto em 60%. Na Trifil, reduzi R$8MM de GGF e liderei S&OP com previsão de demanda para 40K SKUs. Busco posição de Gerente de Projetos de Otimização e Previsão no Mercado Envios."),

        espaco(8),
        secao("Experiência"),

        cargoParagraph("Head de Operações", "wehandle", "Mai 2024 – Fev 2026"),
        bullet([
          { text: "Fui responsável por gerir a operação de atendimento e suporte com time de " },
          { text: "30 pessoas", bold: true },
          { text: ", liderando transformação estrutural com impacto direto em margem bruta, comunicação executiva e roadmap de produto com implantação de plataforma de atendimento IA first." },
        ]),
        bullet([
          { text: "Conduzi duas migrações de plataforma (Zendesk), implantei canal WhatsApp substituindo telefone e conectei dados de atendimento ao datalake da empresa via API para decisão em tempo real." },
        ]),
        bullet([
          { text: "Reduzi custo por atendimento de " },
          { text: "R$4,14 para R$3,61 (−13%)", bold: true },
          { text: ", cortei " },
          { text: "backlog de produto em 60%", bold: true },
          { text: ", elevei " },
          { text: "SLA de execução de 67% para 85%", bold: true },
          { text: " e reduzi " },
          { text: "contact rate em 8%", bold: true },
          { text: " via direcionamento de insights ao time de produto." },
        ]),

        espaco(6),
        cargoParagraph("Head e Diretor de Operações", "iFood", "Nov 2018 – Mar 2024"),
        bullet([
          { text: "Fui responsável por gerir as operações logísticas do maior marketplace de delivery da América Latina com equipe de " },
          { text: "~240 pessoas", bold: true },
          { text: " e budget de " },
          { text: "R$300MM/ano", bold: true },
          { text: ", conduzindo S&OP executivo mensal, capacity planning de frota e planejamento integrado de supply chain." },
        ]),
        bullet([
          { text: "Liderei rito executivo mensal de S&OP conectando marketing, clima, frota e operação, com modelagem de dados em SQL, Python e Databricks, ciência de dados aplicada à logística e dashboards em tempo real no Grafana para decisão C-level." },
        ]),
        bullet([
          { text: "Gerei " },
          { text: "saving de R$70MM/ano", bold: true },
          { text: " com sistema de simulação de nível de serviço de frota, expandi cobertura de " },
          { text: "400 para 800 cidades", bold: true },
          { text: " e reduzi " },
          { text: "custo logístico comparável em 3% YoY", bold: true },
          { text: " mantendo SLA em operação de " },
          { text: "30M pedidos/mês", bold: true },
          { text: "." },
        ]),

        espaco(6),
        cargoParagraph("Gerente de Planejamento Comercial e Operações", "VivaReal", "Mai 2015 – Dez 2017"),
        bullet([
          { text: "Fui responsável por planejamento comercial e operações com equipe de " },
          { text: "33 pessoas e 5 lideranças diretas", bold: true },
          { text: ", abrangendo SDR, qualidade e cadastro de imóveis, com interface direta com CFO para leitura de DRE e análise de variação entre realizado e planejado." },
        ]),
        bullet([
          { text: "Estruturei área de CS do zero como arquiteto dos processos, definindo régua de onboarding e jornada do cliente, enquanto conduzia roadmap de produto em rituais semanais com time de engenharia para priorização de entregas no Salesforce." },
        ]),
        bullet([
          { text: "Aumentei conversão SDR inbound de " },
          { text: "18% para 50%", bold: true },
          { text: ", reduzi " },
          { text: "custo de vendas em 40%", bold: true },
          { text: ", atingi " },
          { text: "NPS 80%", bold: true },
          { text: " e " },
          { text: "CSAT acima de 92%", bold: true },
          { text: ", entregando planejamento estratégico 2018 na fusão com ZAP." },
        ]),

        espaco(6),
        cargoParagraph("Coordenador de S&OP | Expedição | Supply Chain", "Scalina (Trifil)", "Jan 2006 – Set 2014"),
        bullet([
          { text: "Fui responsável por criar e liderar a área de S&OP do zero, gerindo " },
          { text: "40K SKUs", bold: true },
          { text: " em duas marcas e todos os canais de distribuição, com previsão de demanda como KPI central, além de coordenar expedição com picking, packing e armazenamento, e supply chain com Strategic Sourcing de 150K+ SKUs." },
        ]),
        bullet([
          { text: "Conduzi gestão de projetos de tecnologia aplicados à operação: sistema de tinturaria automatizada, implantação de WMS com coletores RF, key-user do ERP LN e desenvolvimento de sistema de simulação de cenários para S&OP em Excel VBA." },
        ]),
        bullet([
          { text: "Reduzi " },
          { text: "40% dos custos de produção", bold: true },
          { text: " com automação da tinturaria (payback real de " },
          { text: "1,5 anos vs 3 projetados", bold: true },
          { text: "), elevei acurácia de estoque de " },
          { text: "85% para 98%", bold: true },
          { text: ", aumentei " },
          { text: "produtividade em 35%", bold: true },
          { text: " e reduzi " },
          { text: "R$8MM de GGF", bold: true },
          { text: " do P&L com Projeto GGF 2014." },
        ]),

        espaco(8),
        secao("Formação"),
        bullet([{ text: "MBA Corporate Strategy — BSP Business School São Paulo (2016–2017)" }]),
        bullet([{ text: "Engenheiro Químico — Faculdades Oswaldo Cruz (2014)" }]),
        bullet([{ text: "Técnico em Química — SENAI Mario Amato (1997)" }]),

        espaco(8),
        secao("Stack técnica"),
        paragraph("ERP Infor LN · WMS · Excel/VBA · SQL · Python · Databricks · Grafana · Power BI · Tableau · Salesforce · Zendesk"),

        espaco(8),
        secao("Idiomas"),
        bullet([{ text: "Português — Nativo" }]),
        bullet([{ text: "Inglês — Avançado" }]),
      ],
    }],
  });

  const buffer = await Packer.toBuffer(doc);
  fs.writeFileSync(outputPath, buffer);
  console.log("ok");
}

main().catch(error => {
  console.error(error);
  process.exit(1);
});
