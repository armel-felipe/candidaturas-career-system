const { Document, Packer, Paragraph, TextRun, ExternalHyperlink, BorderStyle, TabStopType, TabStopPosition, LevelFormat, AlignmentType } = require('docx');
const fs = require('fs');
const path = require('path');

const pt = n => n * 2;

function secao(text) {
  return new Paragraph({
    children: [new TextRun({ text, size: pt(12), font: 'Arial' })],
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: '000000', space: 1 } },
    spacing: { before: pt(6), after: pt(3) }
  });
}

function espaco(ptSize = 6) {
  return new Paragraph({
    children: [new TextRun({ text: '', size: pt(ptSize), font: 'Arial' })],
    spacing: { after: 0 }
  });
}

function cargoParagraph(cargo, empresa, periodo) {
  return new Paragraph({
    tabStops: [{ type: TabStopType.RIGHT, position: TabStopPosition.MAX }],
    children: [
      new TextRun({ text: `${cargo} — ${empresa}`, bold: true, size: pt(9), font: 'Arial' }),
      new TextRun({ text: '\\t' + periodo, size: pt(9), font: 'Arial' })
    ],
    spacing: { after: 0 }
  });
}

function bullet(runs) {
  const children = runs.map(r =>
    new TextRun({ text: r.text, bold: r.bold || false, size: pt(9), font: 'Arial' })
  );
  return new Paragraph({
    numbering: { reference: 'bullets', level: 0 },
    children,
    spacing: { after: pt(2) }
  });
}

const doc = new Document({
  styles: {
    default: { document: { run: { font: 'Arial', size: pt(9) } } },
    paragraphStyles: [
      { id: 'Normal', name: 'Normal', quickFormat: true, run: { font: 'Arial', size: pt(9) }, paragraph: { spacing: { after: 0 } } },
      { id: 'ListParagraph', name: 'List Paragraph', basedOn: 'Normal', quickFormat: true, run: { font: 'Arial', size: pt(9) }, paragraph: { spacing: { after: 0 } } }
    ]
  },
  sections: [{
    properties: {
      page: { margin: { top: 720, right: 504, bottom: 720, left: 504 } }
    },
    children: [
      new Paragraph({
        children: [new TextRun({ text: 'Felipe Armel Dias da Silva', bold: true, size: pt(12), font: 'Arial' })],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [
          new ExternalHyperlink({
            children: [new TextRun({ text: 'linkedin.com/in/felipearmel', style: 'Hyperlink', size: pt(9), font: 'Arial' })],
            link: 'https://linkedin.com/in/felipearmel'
          })
        ],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [new TextRun({ text: 'São Paulo, SP', size: pt(9), font: 'Arial' })],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [
          new ExternalHyperlink({
            children: [new TextRun({ text: '(11) 98674-8218', style: 'Hyperlink', size: pt(9), font: 'Arial' })],
            link: 'https://wa.me/5511986748218'
          })
        ],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [
          new ExternalHyperlink({
            children: [new TextRun({ text: 'armelfelipe@gmail.com', style: 'Hyperlink', size: pt(9), font: 'Arial' })],
            link: 'mailto:armelfelipe@gmail.com'
          })
        ],
        spacing: { after: 0 }
      }),
      espaco(8),
      secao('Summary'),
      espaco(3),
      new Paragraph({
        children: [
          new TextRun({ 
            text: 'Senior Executive with 20 years of experience in digital operations and business transformation within marketplaces and technology. As Director of Operations at iFood, I managed a R$ 300MM/year budget and expanded logistics from 400 to 800 cities to protect EBITDA. At wehandle, I restructured operations using AI-first strategies to improve gross margin by 15%. I am seeking an Associate Director, Delivery Operations position.',
            size: pt(9), font: 'Arial' 
          })
        ],
        spacing: { after: 0 }
      }),
      espaco(8),
      secao('Experience'),
      espaco(3),
      cargoParagraph('Head of Operations', 'wehandle', 'May 2024 – Feb 2026'),
      bullet([ { text: 'I was responsible for leading the customer support operation with a team of 30 people, focusing on scaling the service via AI-first strategies and CX restructuring.' }]),
      bullet([ { text: 'Driven the adoption of ' }, { text: 'AI & Automation', bold: true }, { text: ' by migrating to a humanized AI platform and integrating WhatsApp, reducing the cost per contact from ' }, { text: 'R$ 4.14 to R$ 3.61 (-13%)', bold: true }, { text: '.' }]),
      bullet([ { text: 'Designed ' }, { text: 'Scalable Delivery Frameworks', bold: true }, { text: ' for the CX area, reducing the bug backlog by ' }, { text: '60%', bold: true }, { text: ' and increasing execution SLA to ' }, { text: '85%', bold: true }, { text: '.' }]),
      espaco(6),
      cargoParagraph('Director of Operations', 'iFood', 'Apr 2022 – Mar 2024'),
      bullet([ { text: 'I was responsible for the logistics cost P&L with a budget of ' }, { text: 'R$ 300MM/year', bold: true }, { text: ', managing a team of ~240 people across FieldOps and New Business.' }]),
      bullet([ { text: 'Exercised total ' }, { text: 'Margin Ownership', bold: true }, { text: ' by driving operational levers to protect the ' }, { text: 'EBITDA', bold: true }, { text: ' target and reducing comparable logistics costs by ' }, { text: '3% YoY', bold: true }, { text: '.' }]),
      bullet([ { text: 'Implemented rigorous ' }, { text: 'Operational Governance', bold: true }, { text: ' and ' }, { text: 'Capacity Planning', bold: true }, { text: ' via executive S&OP, expanding the logistics coverage from 400 to ' }, { text: '800 cities', bold: true }, { text: '.' }]),
      espaco(6),
      cargoParagraph('Head of Operations', 'iFood', 'Nov 2018 – Mar 2022'),
      bullet([ { text: 'I was responsible for leading LiveOps, RegionalOps, and pricing teams, managing the real-time balance between demand and supply.' }]),
      bullet([ { text: 'Developed a demand simulation tool to optimize resource ' }, { text: 'Utilization', bold: true }, { text: ', resulting in an annual saving of ' }, { text: 'R$ 70MM', bold: true }, { text: '.' }]),
      bullet([ { text: 'Executed a ' }, { text: 'Staffing Strategy', bold: true }, { text: ' for the delivery of mPOS devices across 352 cities with ' }, { text: 'zero financial loss', bold: true }, { text: ' through anti-abuse criteria.' }]),
      espaco(6),
      cargoParagraph('Customer Success Manager', 'Renault', 'Jan 2018 – Oct 2018'),
      bullet([ { text: 'I was responsible for managing the transition of two BPOs with 40 agents to an internalized, high-performance customer success model.' }]),
      bullet([ { text: 'Structured a data-driven qualification methodology and lead funnel control using custom-programmed dialers.' }]),
      bullet([ { text: 'Elevated the lead-to-sale conversion rate from ' }, { text: '24% to 46%', bold: true }, { text: ' by reducing friction and improving response time.' }]),
      espaco(6),
      cargoParagraph('Commercial Planning and Operations Manager', 'VivaReal', 'May 2015 – Dec 2017'),
      bullet([ { text: 'I was responsible for the architecture of the CS area and management of the SDR team (33 people), focusing on inbound lead qualification.' }]),
      bullet([ { text: 'Optimized the SDR pipeline by identifying the ideal contact window, increasing inbound conversion from ' }, { text: '18% to 50%', bold: true }, { text: ' in sales.' }]),
      bullet([ { text: 'Reduced the cost of sales by ' }, { text: '40%', bold: true }, { text: ' while maintaining the volume of closed accounts through process automation.' }]),
      espaco(6),
      cargoParagraph('S&OP Coordinator', 'Trifil', 'Jan 2006 – Dec 2014'),
      bullet([ { text: 'I was responsible for creating the S&OP area from scratch, managing the integrated planning of 40K SKUs across all distribution channels.' }]),
      bullet([ { text: 'Implemented a management system by objectives (GPD) and an automated dyehouse system that reduced production costs by ' }, { text: '40%', bold: true }, { text: '.' }]),
      bullet([ { text: 'Reduced General Factory Expenses (GGF) by ' }, { text: 'R$ 8MM', bold: true }, { text: ' through the optimization of energy and packaging consumption.' }]),
      espaco(6),
      cargoParagraph('Business Analyst', 'Essencis', 'Nov 2001 – Apr 2002'),
      bullet([ { text: 'I was responsible for evaluating business expansion projects and M&A opportunities for sanitary landfills and remediation units.' }]),
      bullet([ { text: 'Applied ' }, { text: 'Unit Economics', bold: true }, { text: ' and financial analysis using ' }, { text: 'DCF analysis', bold: true }, { text: ', NPV, and Payback to validate investment viability for the board.' }]),
      bullet([ { text: 'Approved a strategic soil remediation company acquisition project during the initial engineering stage.' }]),
      espaco(8),
      secao('Education'),
      espaco(3),
      new Paragraph({
        children: [new TextRun({ text: 'Specialization Certificate in Corporate Strategies — BSP Business School São Paulo (2017)', size: pt(9), font: 'Arial' })],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [new TextRun({ text: 'Chemical Engineering — Faculdades Oswaldo Cruz (2014)', size: pt(9), font: 'Arial' })],
        spacing: { after: 0 }
      }),
      espaco(8),
      secao('Technical Skills'),
      espaco(3),
      new Paragraph({
        children: [new TextRun({ text: 'Advanced Excel + VBA · SQL, PySpark, Python, Databricks · Grafana · Salesforce, Zendesk, Movidesk, CloudHumans · ERP: LN Infor, BAAN IV, Totvs Logix · Power BI', size: pt(9), font: 'Arial' })],
        spacing: { after: 0 }
      }),
      espaco(8),
      secao('Languages'),
      espaco(3),
      new Paragraph({
        numbering: { reference: 'bullets', level: 0 },
        children: [new TextRun({ text: 'Portuguese — Native', size: pt(9), font: 'Arial' })],
        spacing: { after: pt(2) }
      }),
      new Paragraph({
        numbering: { reference: 'bullets', level: 0 },
        children: [new TextRun({ text: 'English — Advanced', size: pt(9), font: 'Arial' })],
        spacing: { after: pt(2) }
      }),
      espaco(8),
      secao('Competencies'),
      espaco(3),
      new Paragraph({
        children: [new TextRun({ text: 'Delivery Operations · Margin Ownership · Unit Economics · Capacity Planning · Operational Governance · AI & Automation · Utilization · Staffing Strategy · Scalable Delivery Frameworks · P&L Management · EBITDA Protection · S&OP Executivo · DCF analysis · Budget Allocation · Process Governance', size: pt(9), font: 'Arial' })],
        spacing: { after: 0 }
      }),
    ]
  },
  numbering: {
    config: [{
      reference: 'bullets',
      levels: [{
        level: 0, format: LevelFormat.BULLET, text: '\\u2022',
        alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 360, hanging: 180 } } }
      }]
    }]
  }
});

Packer.toBuffer(doc).then(buffer => {
  const tmpDir = path.join(__dirname, 'outputs', '_tmp');
  if (!fs.existsSync(tmpDir)) fs.mkdirSync(tmpDir, { recursive: true });
  fs.writeFileSync(path.join(tmpDir, 'cv_associate_director_delivery_operations_monks_en.docx'), buffer);
  console.log('ok');
});
