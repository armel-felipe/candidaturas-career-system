const fs = require("fs");
const docx = require("docx");
const {
  Document, Packer, Paragraph, TextRun, ExternalHyperlink,
  BorderStyle, AlignmentType
} = docx;

const pt = n => n * 2;

function espaco(ptSize = 6) {
  return new Paragraph({
    children: [new TextRun({ text: "", size: pt(ptSize), font: "Arial" })],
    spacing: { after: 0 }
  });
}

const doc = new Document({
  sections: [{
    properties: {
      page: {
        margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 }
      }
    },
    children: [
      // === HEADER ===
      new Paragraph({
        children: [new TextRun({ text: "Cover Letter — Felipe Armel Dias da Silva", bold: true, size: pt(12), font: "Arial" })],
        spacing: { after: 0 }
      }),
      espaco(6),
      new Paragraph({
        children: [new TextRun({ text: "Felipe Armel Dias da Silva", size: pt(11), font: "Arial" })],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [
          new ExternalHyperlink({
            children: [new TextRun({ text: "linkedin.com/in/felipearmel", style: "Hyperlink", size: pt(11), font: "Arial" })],
            link: "https://linkedin.com/in/felipearmel"
          })
        ],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [
          new ExternalHyperlink({
            children: [new TextRun({ text: "(11) 98674-8218", style: "Hyperlink", size: pt(11), font: "Arial" })],
            link: "https://wa.me/5511986748218"
          })
        ],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [
          new ExternalHyperlink({
            children: [new TextRun({ text: "armelfelipe@gmail.com", style: "Hyperlink", size: pt(11), font: "Arial" })],
            link: "mailto:armelfelipe@gmail.com"
          })
        ],
        spacing: { after: 0 }
      }),
      espaco(12),

      // === BODY ===
      new Paragraph({
        children: [new TextRun({ text: "Dear Wellhub Team,", size: pt(11), font: "Arial" })],
        spacing: { after: pt(6) }
      }),

      new Paragraph({
        children: [
          new TextRun({ text: "With 10 years of experience in operations and customer success — most recently raising CSAT from 85% to 92% and cutting cost per ticket by 13% as Head of Operations at wehandle — I would like to express my interest in the Director of Client Operations position.", size: pt(11), font: "Arial" })
        ],
        spacing: { after: pt(6) }
      }),

      new Paragraph({
        children: [
          new TextRun({ text: "What draws me to Wellhub is your mission to make every company a wellness company, connecting employees to fitness, mindfulness, therapy, and nutrition partners through a single global platform. Your presence across North America, Europe, and South America represents exactly the kind of cross-cultural operational challenge where I believe I can contribute most directly — at the intersection of client support, customer success, and product.", size: pt(11), font: "Arial" })
        ],
        spacing: { after: pt(6) }
      }),

      new Paragraph({
        children: [
          new TextRun({ text: "My experience in client operations and stakeholder management — specifically at wehandle, where I led the B2B SaaS support operation with a team of 30, deployed AI automation and WhatsApp channels, and acted as the bridge between product and clients, reducing backlog by 60% — connects directly to what this role demands. Combining operational efficiency with client experience improvement is what I have been doing over the past few years, and it is precisely the challenge of leading Brazil operations while connecting CS, product, and strategic clients.", size: pt(11), font: "Arial" })
        ],
        spacing: { after: pt(6) }
      }),

      new Paragraph({
        children: [
          new TextRun({ text: "I would welcome the opportunity to discuss how my background can contribute to Wellhub. Please find my resume attached.", size: pt(11), font: "Arial" })
        ],
        spacing: { after: pt(12) }
      }),

      new Paragraph({
        children: [new TextRun({ text: "Sincerely,", size: pt(11), font: "Arial" })],
        spacing: { after: pt(6) }
      }),

      new Paragraph({
        children: [new TextRun({ text: "Felipe Armel Dias da Silva", size: pt(11), font: "Arial" })],
        spacing: { after: 0 }
      })
    ]
  }]
});

Packer.toBuffer(doc).then(buffer => {
  const outPath = "outputs/_tmp/cover_letter_wellhub_director_of_client_operations_en.docx";
  fs.writeFileSync(outPath, buffer);
  console.log("ok");
});