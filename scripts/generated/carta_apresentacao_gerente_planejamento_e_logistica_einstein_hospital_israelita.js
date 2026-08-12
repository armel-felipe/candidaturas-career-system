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
const rawOutput = path.join(tempDir, "carta_apresentacao_gerente_planejamento_e_logistica_einstein_hospital_israelita_raw.docx");

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
    paragraph("Carta de Apresentação - Felipe Armel Dias da Silva", { size: 12, bold: true, after: pt(12) }),
    line("Felipe Armel Dias da Silva"),
    linkLine("linkedin.com/in/felipearmel", "https://linkedin.com/in/felipearmel"),
    linkLine("(11) 98674-8218", "https://wa.me/5511986748218"),
    linkLine("armelfelipe@gmail.com", "mailto:armelfelipe@gmail.com"),

    paragraph("", { after: pt(14) }),
    paragraph("Prezada equipe do Einstein Hospital Israelita,"),

    paragraph(
      "Com quase 30 anos de experiência em operações, planejamento de demanda e supply chain, tendo resultados como a gestão de R$300MM/ano no iFood, a ampliação de cobertura de 400 para 800 cidades e o saving de R$70MM/ano com simulador de nivel de servico logistico, gostaria de compartilhar meu interesse na posição de Gerente Planejamento e Logistica."
    ),

    paragraph(
      "O que me atrai no Einstein Hospital Israelita é o compromisso com inovação, excelência, educação, prevenção e responsabilidade social na saúde. Iniciativas e frentes como inovação, tecnologia, pesquisa e ensino mostram uma agenda que exige operação previsível, disciplina de serviço e resposta rápida em um ambiente assistencial de alta criticidade."
    ),

    paragraph(
      "Minha experiência em planejamento de demanda, MRP, politica de estoque, armazenagem, expedicao, nivel de servico logistico e compliance se conecta diretamente com o desafio da vaga. Na Trifil, criei e sustentei a área de S&OP por 4 anos, gerenciei 40K SKUs, defini safety stock, reduzi falta de estoque em 40% e elevei a acuracidade de estoque de 85% para 98%; no iFood, liderei planejamento de capacidade, frota e governança executiva com budget de R$300MM/ano. Na VivaReal, estruturei planejamento comercial, SDR e CS com escala para 91 pessoas e conversão inbound de 18% para 50%, reforçando minha capacidade de integrar áreas e operar por indicadores."
    ),

    paragraph(
      "Fico à disposição para conversar sobre como minha trajetória pode contribuir para a previsibilidade de estoques, o nível de serviço logístico e a integração entre Compras, Farmácia, Assistência, TI e Financeiro no Einstein Hospital Israelita. Segue o currículo em anexo."
    ),

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
