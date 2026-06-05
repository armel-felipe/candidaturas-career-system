const fs = require("fs");
const docx = require("docx");
const {
  Document, Packer, Paragraph, TextRun, ExternalHyperlink,
  TabStopType, TabStopPosition, LevelFormat, AlignmentType,
  BorderStyle
} = docx;

const pt = n => n * 2;

function line(text, options = {}) {
  return new Paragraph({
    children: [new TextRun({ text, size: pt(options.size || 11), font: "Arial", bold: options.bold || false })],
    spacing: { after: options.after || 0, before: options.before || 0 }
  });
}

function linkText(text, url) {
  return new Paragraph({
    children: [
      new ExternalHyperlink({
        children: [new TextRun({ text, style: "Hyperlink", size: pt(11), font: "Arial" })],
        link: url
      })
    ],
    spacing: { after: 0 }
  });
}

function spacer() {
  return new Paragraph({
    children: [new TextRun({ text: "", size: pt(11), font: "Arial" })],
    spacing: { after: 0 }
  });
}

function bodyPara(text) {
  return new Paragraph({
    children: [new TextRun({ text, size: pt(11), font: "Arial" })],
    spacing: { after: pt(6) },
    alignment: AlignmentType.JUSTIFIED
  });
}

const doc = new Document({
  styles: {
    default: { document: { run: { font: "Arial", size: pt(11) } } },
    paragraphStyles: [
      {
        id: "Normal", name: "Normal", quickFormat: true,
        run: { font: "Arial", size: pt(11) },
        paragraph: { spacing: { after: 0 } }
      }
    ]
  },
  sections: [{
    properties: {
      page: {
        margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 }
      }
    },
    children: [
      // Title
      line("Cover Letter — Felipe Armel Dias da Silva", { bold: true, size: 14, after: pt(12) }),

      // Contact
      line("Felipe Armel Dias da Silva"),
      linkText("linkedin.com/in/felipearmel", "https://linkedin.com/in/felipearmel"),
      linkText("(11) 98674-8218", "https://wa.me/5511986748218"),
      linkText("armelfelipe@gmail.com", "mailto:armelfelipe@gmail.com"),

      spacer(),
      spacer(),

      // Salutation
      line("Dear dehaze team,"),
      spacer(),

      // P1 — Opening with context and result
      bodyPara(
        "With 20+ years building and scaling operations from scratch — including a 15% impact on gross margin and 13% cost reduction in a startup context — I want to share my strong interest in the Chief of Staff - Brazil position."
      ),

      // P2 — Connection with the company
      bodyPara(
        "What draws me to dehaze is the mission to catch what 31% of chronic diagnoses currently miss by building AI infrastructure on existing, unharmonized health data. Saving 10% of health spend for insurers while helping patients live healthier lives is the kind of problem where operational execution directly translates to real-world impact. That is exactly the space where I believe I can contribute most directly: being on the ground in Brazil, opening doors, and building the structure that makes the mission possible."
      ),

      // P3 — Specific differentiator
      bodyPara(
        "My experience building operations from scratch — specifically at wehandle, where I reported directly to the CEO, built CX and data capabilities before the data team existed, and impacted 15% of gross margin — connects directly with what this role demands: a first employee in Brazil who can build the backbone of the operation while the CEO is not physically present. In parallel, my experience at iFood shows I can operate at scale — owning a R$300MM annual P&L, leading monthly S&OP executive with C-level, and managing 240 people across 800 cities."
      ),

      // P4 — Closing
      bodyPara(
        "I would welcome the opportunity to discuss how my background can contribute to dehaze's growth in Brazil."
      ),

      spacer(),
      line("Best regards,"),
      spacer(),
      line("Felipe Armel Dias da Silva")
    ]
  }]
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync("/Users/mac/llm server/projetos/candidaturas/outputs/_tmp/cover_letter_chief_of_staff_dehaze_en.docx", buffer);
  console.log("ok");
});
