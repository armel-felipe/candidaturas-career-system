const fs = require("fs");
const path = require("path");
const {
  Document,
  ExternalHyperlink,
  Packer,
  Paragraph,
  TextRun,
} = require("docx");

const pt = n => n * 2;
const workspace = process.cwd();
const tempDir = path.join(workspace, "outputs", "_tmp");
const rawOutput = path.join(tempDir, "carta_apresentacao_gerente_senior_supply_chain_adm_raw.docx");

function paragraph(text, options = {}) {
  return new Paragraph({
    children: [new TextRun({ text, size: pt(options.size || 10), bold: !!options.bold, font: "Arial" })],
    spacing: { after: options.after === undefined ? pt(8) : options.after },
  });
}

function line(text, options = {}) {
  return new Paragraph({
    children: [new TextRun({ text, size: pt(options.size || 10), bold: !!options.bold, font: "Arial" })],
    spacing: { after: 0 },
  });
}

function linkLine(text, url) {
  return new Paragraph({
    children: [
      new ExternalHyperlink({
        link: url,
        children: [new TextRun({ text, style: "Hyperlink", size: pt(10), font: "Arial" })],
      }),
    ],
    spacing: { after: 0 },
  });
}

async function main() {
  fs.mkdirSync(tempDir, { recursive: true });
  const children = [
    paragraph("Carta de Apresentação — Felipe Armel Dias da Silva", { size: 12, bold: true, after: pt(12) }),
    line("Felipe Armel Dias da Silva"),
    linkLine("linkedin.com/in/felipearmel", "https://linkedin.com/in/felipearmel"),
    linkLine("(11) 98674-8218", "https://wa.me/5511986748218"),
    linkLine("armelfelipe@gmail.com", "mailto:armelfelipe@gmail.com"),

    paragraph("", { after: pt(16) }),
    paragraph("Prezada equipe da ADM,", { after: pt(10) }),

    paragraph("Com trajetória em supply chain, S&OP, planejamento de produção e operações logísticas, gostaria de compartilhar meu interesse na posição de Gerente Sênior de Supply Chain. Na Scalina (Trifil), criei a área de S&OP do zero, gerenciei 40K SKUs, atuei com MPS, MRP, políticas de estoque e reduzi R$ 8 MM de GGF em projetos de eficiência industrial."),

    paragraph("O que me atrai na ADM é a combinação entre escala global, nutrição humana e animal, originação agrícola, soluções de ingredientes e compromisso com sustentabilidade. A vaga descreve um desafio de sincronização entre demanda, produção, materiais, inventários e centros de distribuição, exatamente o tipo de operação em que minha experiência tem maior aderência."),

    paragraph("Minha experiência em S&OP, MPS, MRP, Inventory Management e Capacity Planning se conecta diretamente com a necessidade de transformar demanda em plano de produção, garantir abastecimento de matérias-primas e embalagens, otimizar inventários e preservar nível de serviço. Além da base industrial na Trifil, no iFood liderei S&OP logístico executivo, com R$ 300 MM/ano em budget de custo logístico e saving de R$ 70 MM/ano por meio de planejamento de capacidade e cenários de nível de serviço."),

    paragraph("Fico à disposição para conversar sobre como minha trajetória pode contribuir para a ADM na evolução dos processos de planejamento, governança por KPIs, gestão de capacidade e otimização de inventários. Segue o currículo em anexo."),

    paragraph("", { after: pt(10) }),
    paragraph("Atenciosamente,", { after: pt(10) }),
    paragraph("Felipe Armel Dias da Silva", { after: 0 }),
  ];

  const doc = new Document({
    styles: {
      default: { document: { run: { font: "Arial", size: pt(10) } } },
      paragraphStyles: [
        {
          id: "Normal",
          name: "Normal",
          quickFormat: true,
          run: { font: "Arial", size: pt(10) },
          paragraph: { spacing: { after: 0 } },
        },
      ],
    },
    sections: [{
      properties: {
        page: {
          size: { width: 11906, height: 16838 },
          margin: { top: 720, right: 720, bottom: 720, left: 720 },
        },
      },
      children,
    }],
  });

  const buffer = await Packer.toBuffer(doc);
  fs.writeFileSync(rawOutput, buffer);
  console.log("ok");
}

main().catch(error => {
  console.error(error);
  process.exit(1);
});
