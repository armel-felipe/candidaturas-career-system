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

const pt = n => n * 2; // half-points. NEVER n * 20 (twips).

const workspace = process.cwd();
const tempDir = path.join(workspace, "outputs", "_tmp");
const rawOutput = path.join(tempDir, "cv_shopee_gerente_ops_logisticas_raw.docx");

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
  const children = runs.map(r =>
    new TextRun({ text: r.text, bold: r.bold || false, size: pt(9), font: "Arial" })
  );
  return new Paragraph({
    numbering: { reference: "bullets", level: 0 },
    children,
    spacing: { after: pt(2) },
  });
}

const doc = new Document({
  numbering: {
    config: [
      {
        reference: "bullets",
        levels: [
          {
            level: 0,
            format: LevelFormat.BULLET,
            text: "•",
            alignment: AlignmentType.LEFT,
            style: {
              paragraph: { indent: { left: 360, hanging: 180 } },
            },
          },
        ],
      },
    ],
  },
  styles: {
    default: {
      document: { run: { font: "Arial", size: pt(9) } },
    },
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
  sections: [
    {
      properties: {
        page: {
          size: { width: 11906, height: 16838 }, // A4 in DXA
          margin: { top: 720, right: 504, bottom: 720, left: 504 },
        },
      },
      children: [
        // ── CABEÇALHO ──────────────────────────────────────────────
        new Paragraph({
          children: [
            new TextRun({ text: "Felipe Armel Dias da Silva", bold: true, size: pt(12), font: "Arial" }),
          ],
          spacing: { after: 0 },
        }),
        new Paragraph({
          children: [
            new ExternalHyperlink({
              link: "https://www.linkedin.com/in/felipearmel",
              children: [
                new TextRun({
                  text: "linkedin.com/in/felipearmel",
                  size: pt(9),
                  font: "Arial",
                  style: "Hyperlink",
                }),
              ],
            }),
          ],
          spacing: { after: 0 },
        }),
        new Paragraph({
          children: [new TextRun({ text: "São Paulo, SP", size: pt(9), font: "Arial" })],
          spacing: { after: 0 },
        }),
        new Paragraph({
          children: [
            new ExternalHyperlink({
              link: "https://wa.me/5511986748218",
              children: [
                new TextRun({
                  text: "(11) 98674-8218",
                  size: pt(9),
                  font: "Arial",
                  style: "Hyperlink",
                }),
              ],
            }),
          ],
          spacing: { after: 0 },
        }),
        new Paragraph({
          children: [
            new ExternalHyperlink({
              link: "mailto:armelfelipe@gmail.com",
              children: [
                new TextRun({
                  text: "armelfelipe@gmail.com",
                  size: pt(9),
                  font: "Arial",
                  style: "Hyperlink",
                }),
              ],
            }),
          ],
          spacing: { after: 0 },
        }),

        espaco(8),

        // ── RESUMO ─────────────────────────────────────────────────
        secao("Resumo"),
        espaco(3),
        new Paragraph({
          children: [
            new TextRun({ text: "Engenheiro Químico e MBA em Estratégia Corporativa (BSP). No iFood, como Diretor de Operações, geri budget de ", size: pt(9), font: "Arial" }),
            new TextRun({ text: "R$300MM/ano", bold: true, size: pt(9), font: "Arial" }),
            new TextRun({ text: " e reduzi custo logístico comparável em ", size: pt(9), font: "Arial" }),
            new TextRun({ text: "3% YoY", bold: true, size: pt(9), font: "Arial" }),
            new TextRun({ text: "; como Head, criei simulador de frota com saving de ", size: pt(9), font: "Arial" }),
            new TextRun({ text: "R$70MM/ano", bold: true, size: pt(9), font: "Arial" }),
            new TextRun({ text: ". Experiência em operação de centro de distribuição físico (WMS, picking, OTIF) e liderança de até 240 pessoas. Busco posição de Gerente de Operações Logísticas.", size: pt(9), font: "Arial" }),
          ],
          spacing: { after: 0 },
        }),

        espaco(8),

        // ── EXPERIÊNCIA ────────────────────────────────────────────
        secao("Experiência"),
        espaco(3),

        // wehandle
        cargoParagraph("Head de Operações", "wehandle", "Mai 2024 – Fev 2026"),
        bullet([
          { text: "Fui responsável por liderar a operação de atendimento com " },
          { text: "time de 30 pessoas", bold: true },
          { text: ", conduzindo 2 migrações de plataforma e implementando canais de WhatsApp e IA para escalar com custo controlado." },
        ]),
        bullet([
          { text: "Implantei Zendesk como plataforma central, conectei as três plataformas de atendimento via API e usei Python e SQL para manter indicadores operacionais em tempo real." },
        ]),
        bullet([
          { text: "Reduzi custo por atendimento de R$4,14 para " },
          { text: "R$3,61 (−13%)", bold: true },
          { text: ", elevei CSAT de 85% para 92% e reduzi TME de 20 para 8 minutos." },
        ]),

        espaco(6),

        // iFood Diretor
        cargoParagraph("Diretor de Operações", "iFood", "Abr 2022 – Mar 2024"),
        bullet([
          { text: "Fui responsável por gerir as operações logísticas com equipe de " },
          { text: "~240 pessoas", bold: true },
          { text: " (FieldOps, Pagamentos e Novos Negócios) e budget de R$300MM/ano, conduzindo S&OP executivo mensal com foco em CPO, cobertura e SLA." },
        ]),
        bullet([
          { text: "Conduzi o planejamento operacional com S&OP executivo mensal, modelagem em Python, SQL e Databricks, e capacity planning de frota por cidade." },
        ]),
        bullet([
          { text: "Ampliei cobertura de 400 para " },
          { text: "800 cidades", bold: true },
          { text: ", reduzi custo logístico comparável em " },
          { text: "3% YoY", bold: true },
          { text: " e mantive SLA em operação de 30M pedidos/mês." },
        ]),

        espaco(6),

        // iFood Head
        cargoParagraph("Head de Operações", "iFood", "Nov 2018 – Mar 2022"),
        bullet([
          { text: "Fui responsável por estruturar o liveOps em " },
          { text: "last mile", bold: true },
          { text: " com indicadores em tempo real, o planejamento de frota e capacity planning — time de 28 pessoas em pricing, modelagem e operações regionais." },
        ]),
        bullet([
          { text: "Estruturei o monitoramento com Grafana, criei simulador proprietário de nível de serviço e modelei dados com SQL e Databricks." },
        ]),
        bullet([
          { text: "Alcancei saving de " },
          { text: "R$70MM/ano", bold: true },
          { text: " com o simulador de frota e reduzi indisponibilidade de frota de 5% para 1% no Brasil (top 6 cidades: de 5,4% para " },
          { text: "0,5%", bold: true },
          { text: ")." },
        ]),

        espaco(6),

        // Trifil S&OP
        cargoParagraph("Coordenador de S&OP", "Scalina (Trifil)", "Jan 2010 – Set 2014"),
        bullet([
          { text: "Fui responsável por criar e gerir a área de " },
          { text: "S&OP do zero", bold: true },
          { text: ", gerenciando 40K SKUs em duas marcas e todos os canais, com equipe de analistas de KPIs, MRP corporativo e planejamento de capacidade de produção." },
        ]),
        bullet([
          { text: "Apliquei PDCA e Six Sigma como metodologia de melhoria contínua, criei simulador de MRP em Excel/VBA e usei MS-Project para governança do calendário S&OP." },
        ]),
        bullet([
          { text: "Reduzi " },
          { text: "R$8MM de GGF", bold: true },
          { text: " do P&L otimizando energia, gás e embalagens e estabeleci OTIF como KPI central reportado ao CEO." },
        ]),

        espaco(6),

        // Trifil Expedição
        cargoParagraph("Coordenador de Expedição", "Scalina (Trifil)", "Jan 2007 – Out 2007"),
        bullet([
          { text: "Fui responsável por gerir o centro de expedição com " },
          { text: "warehouse operations", bold: true },
          { text: " completa — picking, packing e armazenamento — implantando WMS, coletores RF e wi-fi e endereçamento de estoque." },
        ]),
        bullet([
          { text: "Implantei WMS com coletores RF e wi-fi, introduzi inventário rotativo e usei PDCA para controle de qualidade e tratamento de desvios." },
        ]),
        bullet([
          { text: "Elevei acurácia de estoque de 85% para " },
          { text: "98%", bold: true },
          { text: ", aumentei produtividade dos colaboradores em 35% e reduzi perdas em 30%." },
        ]),

        espaco(8),

        // ── FORMAÇÃO ───────────────────────────────────────────────
        secao("Formação"),
        espaco(3),
        bullet([{ text: "ILEad — Liderança para Líder de Líderes — Fundação Dom Cabral (2021)" }]),
        bullet([{ text: "Six Sigma Green Belt — Setec Consulting (2020)" }]),
        bullet([{ text: "MBA Corporate Strategy — BSP Business School São Paulo (2016–2017)" }]),
        bullet([{ text: "Engenheiro Químico — Faculdades Oswaldo Cruz (concluído 2014)" }]),

        espaco(8),

        // ── STACK TÉCNICA ──────────────────────────────────────────
        secao("Stack técnica"),
        espaco(3),
        new Paragraph({
          children: [
            new TextRun({
              text: "Excel avançado + VBA · SQL · Python · Databricks · Grafana · WMS · ERP Infor LN · Power BI",
              size: pt(9),
              font: "Arial",
            }),
          ],
          spacing: { after: 0 },
        }),

        espaco(8),

        // ── IDIOMAS ────────────────────────────────────────────────
        secao("Idiomas"),
        espaco(3),
        bullet([{ text: "Português — Nativo" }]),
        bullet([{ text: "Inglês — Avançado" }]),
      ],
    },
  ],
});

Packer.toBuffer(doc).then(buffer => {
  fs.mkdirSync(tempDir, { recursive: true });
  fs.writeFileSync(rawOutput, buffer);
  console.log("ok");
});
