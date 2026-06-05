const fs = require("fs");
const path = require("path");
const { spawnSync } = require("child_process");
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

const pt = n => n * 2; // half-points. Never use n * 20 here.

const workspace = process.env.CAREER_WORKSPACE || process.cwd();
const outputDir = process.env.CAREER_OUTPUTS || path.join(workspace, "outputs");

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

function textRunParagraph(text) {
  return new Paragraph({
    children: [new TextRun({ text, size: pt(9), font: "Arial" })],
    spacing: { after: 0 },
  });
}

async function main() {
  const outputName = process.argv[2] || "felipe_armel_cv_gerente_operacoes_uniscience.docx";
  fs.mkdirSync(outputDir, { recursive: true });
  fs.mkdirSync(path.join(outputDir, "_tmp"), { recursive: true });

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

        // === RESUMO ===
        secao("Resumo"),
        textRunParagraph("Executivo com 20 anos em operações digitais e transformação de negócios. No iFood, como Diretor de Operações, liderei 240 pessoas com budget de R$300MM/ano, expandindo cobertura logística de 400 para 800 cidades. Na WeHandle, reestruturei a operação de CS com impacto de 15% na margem bruta. Início de carreira em farmacêutica com gestão da qualidade ISO 9001. Engenheiro Químico e MBA Corporate Strategy. Busco posição de Gerente de Operações."),
        espaco(8),

        // === EXPERIÊNCIA ===
        secao("Experiência"),

        // --- WeHandle ---
        cargoParagraph("Head de Operações", "WeHandle", "Mai 2024 – Fev 2026"),
        bullet([
          { text: "Fui responsável pela gestão integrada de Customer Service, CX e suporte, com equipe de 30 pessoas, reestruturando processos e conectando atendimento à operação." }
        ]),
        bullet([
          { text: "Liderei migrações de plataforma de atendimento (Movidesk, CloudHumans, Zendesk), implantei automação com IA e canal WhatsApp, e integrei dados ao datalake via API." }
        ]),
        bullet([
          { text: "Alcancei melhoria de CSAT de 85% para 92% com SLA de 95%, reduzi o custo por atendimento de R$ 4,14 para R$ 3,61 e gerei impacto de " },
          { text: "15% na margem bruta", bold: true },
          { text: " da companhia." }
        ]),
        espaco(6),

        // --- iFood Diretor ---
        cargoParagraph("Diretor de Operações", "iFood", "Abr 2022 – Mar 2024"),
        bullet([
          { text: "Fui responsável pelas operações logísticas com equipe de ~240 pessoas e budget de " },
          { text: "R$300MM/ano", bold: true },
          { text: ", gerindo FieldOps, Meios de Pagamento e Novos Negócios." }
        ]),
        bullet([
          { text: "Conduzi o S&OP executivo mensal consolidando demanda, supply e custo logístico, modelei dados com Python, SQL e Databricks, e estabeleci governança de planejamento por cidade." }
        ]),
        bullet([
          { text: "Ampliei cobertura logística de 400 para 800 cidades, reduzi o custo comparável em " },
          { text: "3% YoY", bold: true },
          { text: " e aumentei pedidos agrupados de 12% para 25%, contribuindo para o breakeven da operação." }
        ]),
        espaco(6),

        // --- iFood Head ---
        cargoParagraph("Head de Operações", "iFood", "Nov 2018 – Mar 2022"),
        bullet([
          { text: "Fui responsável pelo planejamento de frota, pricing e liveOps com equipe de 28 pessoas, estruturando indicadores em tempo real no Grafana." }
        ]),
        bullet([
          { text: "Liderei a criação de simulador de nível de serviço, análise de elasticidade de preço para oferta de entregadores e distribuição de MPOS em 352 cidades." }
        ]),
        bullet([
          { text: "Gerei saving de " },
          { text: "R$70M/ano", bold: true },
          { text: " com o simulador, reduzi custo de distribuição de MPOS em 80% e prazo de 14 para 2 dias, e reduzi cancelamento no México em 60% ajustando raios." }
        ]),
        espaco(6),

        // --- Renault ---
        cargoParagraph("Gerente de Customer Success", "Renault do Brasil", "Jan 2018 – Out 2018"),
        bullet([
          { text: "Fui responsável pela migração de operação terceirizada (BPO, 40 PAS) para estrutura própria com 8 pessoas, criando modelo escalável de CS com maior controle de SLA." }
        ]),
        bullet([
          { text: "Estruturei metodologia de qualificação baseada em dados, implementei governança de SLA de retorno e direcionei ferramentas de discagem com análise de performance." }
        ]),
        bullet([
          { text: "Elevei a conversão de vendas de leads de " },
          { text: "24% para 46%", bold: true },
          { text: " com dados em tempo real e controle rigoroso de funil." }
        ]),
        espaco(6),

        // --- VivaReal ---
        cargoParagraph("Gerente de Planejamento Comercial e Operações", "VivaReal", "Mai 2015 – Dez 2017"),
        bullet([
          { text: "Fui arquiteto da área de Customer Success: idealizei processos, defini régua de onboarding, contratei a liderança — a área escalou para " },
          { text: "91 pessoas", bold: true },
          { text: " sob gestão de outros." }
        ]),
        bullet([
          { text: "Estruturei planejamento comercial com desdobramento de metas, políticas de comissionamento e indicadores de performance para equipes de 33 pessoas." }
        ]),
        bullet([
          { text: "Alcancei NPS de 80% e CSAT acima de 92%, recuperei R$1M em inadimplentes e reduzi custo de vendas em 40% com otimização de funil SDR." }
        ]),
        espaco(6),

        // --- Trifil ---
        cargoParagraph("Coordenador de S&OP", "Scalina (Trifil)", "Jan 2010 – Set 2014"),
        bullet([
          { text: "Fui responsável pelo planejamento de demanda e gestão de estoques de " },
          { text: "40 mil SKUs", bold: true },
          { text: " em duas marcas, com MRP corporativo e análise de capacidade de produção." }
        ]),
        bullet([
          { text: "Liderei o Projeto Entrega Certa com KPIs de OTIF, fill rate e acurácia de produção, reportados ao CEO; coordenei outsourcing nacional e internacional." }
        ]),
        bullet([
          { text: "Reduzi " },
          { text: "R$8M em Gastos Gerais de Fabricação", bold: true },
          { text: " do P&L, melhorei giro de estoque de 8 para 6 meses e mantive R$154M em GGF dentro da meta anual." }
        ]),
        espaco(6),

        // --- Essencis ---
        cargoParagraph("Analista de Negócios", "Essencis", "Nov 2001 – Abr 2002"),
        bullet([
          { text: "Fui responsável por avaliar projetos de expansão (aterros, incineradores, remediação) com análise de viabilidade usando FCD, VPL e Payback, aprovando aquisição em estágio de engenharia." }
        ]),
        bullet([
          { text: "Apliquei análise financeira para decisão de investimento em projetos ambientais e químicos, com apresentação direta ao conselho da empresa." }
        ]),
        espaco(8),

        // === FORMAÇÃO ===
        secao("Formação"),
        bullet([{ text: "MBA Corporate Strategy — BSP Business School São Paulo (2017)" }]),
        bullet([{ text: "Engenharia Química — Faculdades Oswaldo Cruz (2014)" }]),
        bullet([{ text: "Six Sigma Green Belt — Setec Consulting (2020)" }]),
        espaco(8),

        // === STACK TÉCNICA ===
        secao("Stack técnica"),
        textRunParagraph("Excel/VBA · SQL · Python · Databricks · Grafana · Power BI · Tableau · Metabase · Salesforce · Zendesk · ERP Infor LN"),
        espaco(8),

        // === COMPETÊNCIAS ===
        secao("Competências"),
        textRunParagraph("Gestão de Operações · Supply Chain Management · Customer Service Operations · Gestão da Qualidade · Liderança de Equipes · ERP Implementation · KPI Management · Redução de Custos · Data Analysis · Continuous Improvement · Logistics Planning · Demand Planning · ISO 9001 · Change Management · Process Improvement"),
        espaco(8),

        // === IDIOMAS ===
        secao("Idiomas"),
        bullet([{ text: "Português — Nativo" }]),
        bullet([{ text: "Inglês — Avançado" }]),
      ],
    }],
  });

  const tmpPath = path.join(outputDir, "_tmp", outputName);
  const buffer = await Packer.toBuffer(doc);
  fs.writeFileSync(tmpPath, buffer);
  console.log("ok");

  // Inject Arial theme
  const themeScript = path.join(workspace, "scripts", "docx", "inject_arial_theme.py");
  const finalPath = path.join(outputDir, outputName);
  const themeResult = spawnSync("python3", [themeScript, tmpPath, finalPath], { stdio: "inherit" });
  if (themeResult.status !== 0) {
    process.exit(themeResult.status || 1);
  }
  console.log("ok");
}

main().catch(error => {
  console.error(error);
  process.exit(1);
});
