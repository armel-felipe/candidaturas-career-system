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

const pt = n => n * 2;

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

async function main() {
  const outputName = "felipe_armel_cv_gerente_head_ecommerce_dadri_shop.docx";
  fs.mkdirSync(outputDir, { recursive: true });

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
        paragraph("Executivo de operações digitais com trajetória em marketplace de larga escala (iFood), operações de atendimento (wehandle), indústria têxtil (Trifil) e tecnologia imobiliária (VivaReal). Combino estratégia digital, análise de dados e liderança de equipes multidisciplinares para estruturar e escalar operações com foco em resultado. Vivência em gestão de portfólio de produtos, integração de sistemas ERP, planejamento de promoções e coordenação multifuncional entre áreas como marketing, logística, produto e operações."),
        espaco(8),

        secao("Experiência"),

        // 1. WeHandle
        cargoParagraph("Head de Operações", "wehandle", "mai/2024 a fev/2026"),
        bullet([{ text: "Implementei estratégia de atendimento digital com automação e IA, reduzindo o custo por atendimento de R$4,14 para R$3,61 (−13%), com KPIs e Indicadores de Desempenho como CSAT, TME, contact rate e SLA." }]),
        bullet([{ text: "Estruturei a segmentação da carteira de clientes por perfil e jornada, elevando o CSAT de 85% para 92% (+17%) — aumento direto de retenção e recorrência no atendimento." }]),
        bullet([{ text: "Implantei canais digitais (WhatsApp) e automação com IA humanizada, reduzindo o tempo médio de atendimento de 20 para 8 minutos e aumentando a produtividade em 25%." }]),
        bullet([{ text: "Conectei dados de atendimento ao datalake via API, direcionando insights ao time de produto e reduzindo o contact rate em 8% — tomada de decisão orientada por dados com Python e SQL." }]),
        bullet([{ text: "Liderei time de 30 pessoas com coordenação multifuncional entre produto, dados e operação, gerindo duas migrações de plataforma de atendimento." }]),
        espaco(4),

        // 2. iFood Diretor
        cargoParagraph("Diretor de Operações", "iFood", "abr/2022 a mar/2024"),
        bullet([{ text: "Responsável pela estratégia digital da logística do maior marketplace de food do Brasil, consolidando demanda, oferta, custo e nível de serviço em planejamento integrado (S&OP executivo) conectado ao EBITDA e reportado ao C-level." }]),
        bullet([{ text: "Gerenciei budget de R$300MM/ano com leitura semanal de DRE executiva, variação vs meta e alavancas operacionais para proteção do resultado financeiro." }]),
        bullet([{ text: "Defini planejamento de promoções e precificação por zona com pricing dinâmico e testes controlados de elasticidade — estrutura de yield management aplicada a marketplace logístico." }]),
        bullet([{ text: "Escalonei a cobertura logística de 400 para 800 cidades, reduzi indisponibilidade de frota de 5% para 0,5% e pedidos agrupados de 12% para 25%, alcançando breakeven operacional." }]),
        bullet([{ text: "Criei simulador de nível de serviço com saving de R$70M/ano, mantendo SLA estável — análise de conversão e métricas aplicada a trade-offs de custo e qualidade." }]),
        bullet([{ text: "Coordenação multifuncional entre marketing, promoções, frota, supply e operação em ritos executivos com C-level." }]),
        espaco(4),

        // 3. iFood Head
        cargoParagraph("Head de Operações", "iFood", "nov/2018 a mar/2022"),
        bullet([{ text: "Liderei operação digital de marketplace que escalou de 800K para 30M pedidos/mês em 800 cidades — gestão de ecommerce operations em ambiente de alta complexidade, com modelagem de dados (SQL, Databricks, Python) e métricas em tempo real." }]),
        bullet([{ text: "Estruturei a área de liveOps com indicadores em tempo real (Grafana), correlacionando saturação logística com metas de entrega e ganhos de entregadores." }]),
        bullet([{ text: "Liderei equipe de 28 pessoas em liveOps, pricing, modelagem de dados e frota — liderança de equipes multidisciplinares com foco em resultado." }]),
        bullet([{ text: "Defini regras de elegibilidade para distribuição de MPOS com critérios de risco, escalando para 352 cidades com zero perda financeira." }]),
        espaco(4),

        // 4. VivaReal
        cargoParagraph("Gerente de Planejamento Comercial e Operações", "VivaReal", "mai/2015 a dez/2017"),
        bullet([{ text: "Aumentei a conversão de leads inbound de 18% para 50% com lead scoring e processo de priorização baseado em dados de comportamento — reduzindo o custo de vendas em 40%." }]),
        bullet([{ text: "Arquitetei a área de CS: desenhei processos, régua de onboarding e jornada do cliente. A área escalou para 91 pessoas com churn abaixo de 3% ao mês." }]),
        bullet([{ text: "Defini pricing de produtos e políticas de comissionamento, construindo cenários de receita com leitura de DRE para o CFO." }]),
        espaco(4),

        // 5. Trifil S&OP
        cargoParagraph("Coordenador de S&OP", "Trifil (Scalina)", "jan/2010 a set/2014"),
        bullet([{ text: "Criei a área de S&OP do zero, gerenciando 40K SKUs de produto acabado em duas marcas (Trifil e Scala) em todos os canais — gestão de catálogo e sortimento com complexidade de grade e canais de varejo." }]),
        bullet([{ text: "Coordenei planejamento de materiais, MRP, OTIF e acurácia de estoque de 85% para 98% com projeto Entrega Certa reportado ao CEO." }]),
        bullet([{ text: "Fui key-user do ERP LN (Infor) nos módulos de expedição, planejamento e estoque — ERP Integration com responsabilidade sobre integração entre sistemas e dados para suporte à decisão." }]),
        bullet([{ text: "Reduzi R$8MM em gastos gerais de fabricação com otimização de energia, materiais de manutenção e embalagens." }]),
        bullet([{ text: "Criei simulador em Excel/VBA para análise de cenários e validação do MRP — decisão baseada em dados com ferramentas acessíveis." }]),
        bullet([{ text: "Coordenação multifuncional entre comercial e fabricação em processos de S&OP, conectando restrições de capacidade com vendas." }]),
        espaco(8),

        secao("Formação"),
        paragraph("Engenheiro Químico — Faculdades Oswaldo Cruz (2014)"),
        paragraph("MBA Corporate Strategy — BSP Business School São Paulo (2017)"),
        paragraph("Six Sigma Green Belt — Setec Consulting (2020)"),
        paragraph("Liderança para Líder de Líderes (ILEad) — Fundação Dom Cabral (2021)"),
        espaco(8),

        secao("Stack técnica"),
        paragraph("Excel/VBA · SQL · Python · PySpark · Databricks · Grafana · Power BI · Tableau · Metabase · Salesforce · Zendesk · ERP Infor LN · WMS"),
        espaco(4),

        paragraph("Inglês: Avançado"),
      ],
    }],
  });

  const buffer = await Packer.toBuffer(doc);
  const outputPath = path.join(outputDir, outputName);
  fs.writeFileSync(outputPath, buffer);
  const themeScript = path.join(workspace, "scripts", "docx", "inject_arial_theme.py");
  const themeResult = spawnSync(process.env.PYTHON || "python", [themeScript, outputPath], { stdio: "inherit" });
  if (themeResult.status !== 0) {
    process.exit(themeResult.status || 1);
  }
  console.log(outputPath);
}

main().catch(error => {
  console.error(error);
  process.exit(1);
});