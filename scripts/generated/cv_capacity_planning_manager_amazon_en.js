const { Document, Packer, Paragraph, TextRun, BorderStyle, TabStopType, TabStopPosition, AlignmentType, LevelFormat, ExternalHyperlink } = require('docx');
const fs = require('fs');

const pt = n => n * 2;

const secao = text => new Paragraph({
  children: [new TextRun({ text, size: pt(12), font: 'Arial' })],
  border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: '000000', space: 1 } },
  spacing: { before: pt(6), after: pt(3) }
});

const espaco = (ptSize = 6) => new Paragraph({
  children: [new TextRun({ text: '', size: pt(ptSize), font: 'Arial' })],
  spacing: { after: 0 }
});

const cargoParagraph = (cargo, empresa, periodo) => new Paragraph({
  tabStops: [{ type: TabStopType.RIGHT, position: TabStopPosition.MAX }],
  children: [
    new TextRun({ text: `${cargo} — ${empresa}`, bold: true, size: pt(9), font: 'Arial' }),
    new TextRun({ text: '\t' + periodo, size: pt(9), font: 'Arial' })
  ],
  spacing: { after: 0 }
});

const bullet = runs => {
  const children = runs.map(r =>
    new TextRun({ text: r.text, bold: r.bold || false, size: pt(9), font: 'Arial' })
  );
  return new Paragraph({
    numbering: { reference: 'bullets', level: 0 },
    children,
    spacing: { after: pt(2) }
  });
};

const paragrafo = text => new Paragraph({
  children: [new TextRun({ text, size: pt(9), font: 'Arial' })],
  spacing: { after: 0 }
});

const doc = new Document({
  styles: {
    default: { document: { run: { font: 'Arial', size: pt(9) } } },
    paragraphStyles: [
      { id: 'Normal', name: 'Normal', quickFormat: true, run: { font: 'Arial', size: pt(9) }, paragraph: { spacing: { after: 0 } } },
      { id: 'ListParagraph', name: 'List Paragraph', basedOn: 'Normal', quickFormat: true, run: { font: 'Arial', size: pt(9) }, paragraph: { spacing: { after: 0 } } }
    ]
  },
  numbering: {
    config: [{
      reference: 'bullets',
      levels: [{
        level: 0, format: LevelFormat.BULLET, text: '\u2022', alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 360, hanging: 180 } } }
      }]
    }]
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
      espaco(3),
      new Paragraph({
        children: [
          new ExternalHyperlink({ children: [new TextRun({ text: 'linkedin.com/in/felipearmel', style: 'Hyperlink', size: pt(9), font: 'Arial' })], uri: 'https://linkedin.com/in/felipearmel' })
        ],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [new TextRun({ text: 'Sao Paulo, SP', size: pt(9), font: 'Arial' })],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [
          new ExternalHyperlink({ children: [new TextRun({ text: '(11) 98674-8218', style: 'Hyperlink', size: pt(9), font: 'Arial' })], uri: 'https://wa.me/5511986748218' })
        ],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [
          new ExternalHyperlink({ children: [new TextRun({ text: 'armelfelipe@gmail.com', style: 'Hyperlink', size: pt(9), font: 'Arial' })], uri: 'mailto:armelfelipe@gmail.com' })
        ],
        spacing: { after: 0 }
      }),
      espaco(8),
      secao('Summary'),
      espaco(3),
      paragrafo('Executive with 14+ years in supply chain and logistics operations. Managed capacity planning for 30M monthly orders at iFood with R$70MM/year savings. Led S&OP processes, budget of R$300MM/year, and real-time dashboards. Reduced cost by 3% YoY while expanding from 400 to 800 cities. Built fulfillment operations at Trifil with 98% inventory accuracy. Seeking a Capacity Planning Manager role in transportation.'),
      espaco(8),
      secao('Experience'),
      espaco(6),
      cargoParagraph('Head of Operations', 'WeHandle', 'May 2024 – Feb 2026'),
      bullet([
        { text: 'I led support operations for a startup undergoing restructuring, with a team of ~30 people and responsibility for cost, CSAT, SLA, and efficiency metrics.' }
      ]),
      bullet([
        { text: 'I implemented automation with chatbots, integrated data via API, created real-time dashboards in Metabase, and migrated the platform to scale support.' }
      ]),
      bullet([
        { text: 'I achieved ', bold: false },
        { text: '15%', bold: true },
        { text: ' gross margin impact, reduced cost per ticket from R$4.14 to R$3.61, and improved CSAT from 85% to ', bold: false },
        { text: '92%', bold: true },
        { text: '. Process improvement initiatives reduced TME from 20 to 8 minutes.', bold: false }
      ]),
      espaco(6),
      cargoParagraph('Director of Operations', 'iFood', 'Apr 2022 – Mar 2024'),
      bullet([
        { text: 'I managed logistics operations for ~240 people across FieldOps, Payments, and New Business, with a budget of ', bold: false },
        { text: 'R$300MM/year', bold: true },
        { text: ' and cross-functional leadership across finance, tech, and supply in monthly S&OP meetings with C-suite.', bold: false }
      ]),
      bullet([
        { text: 'I conducted capacity planning, fleet balancing, and scenario modeling using Python, SQL, and Databricks to optimize service level and cost trade-offs.' }
      ]),
      bullet([
        { text: 'I expanded coverage from ', bold: false },
        { text: '400 to 800 cities', bold: true },
        { text: ', reduced comparable cost by ', bold: false },
        { text: '3% YoY', bold: true },
        { text: ' through cost reduction initiatives, and maintained SLA in an operation of 30M orders/month.', bold: false }
      ]),
      espaco(6),
      cargoParagraph('Head of Operations', 'iFood', 'Nov 2018 – Mar 2022'),
      bullet([
        { text: 'I led a team of 28 across liveOps, pricing, data modeling, and fleet planning, creating real-time metrics in Grafana to correlate logistics saturation with service level.' }
      ]),
      bullet([
        { text: 'I built a fleet capacity simulator with SQL and Databricks that maintained service level while generating ', bold: false },
        { text: 'R$70MM/year in savings', bold: true },
        { text: '.', bold: false }
      ]),
      bullet([
        { text: 'I reduced driver unavailability from 5% to ', bold: false },
        { text: '1%', bold: true },
        { text: ' nationwide, achieved 97% MPOS availability, and implemented cash payment in 352 cities with zero financial risk.', bold: false }
      ]),
      espaco(6),
      cargoParagraph('S&OP Coordinator', 'Scalina (Trifil)', 'Jan 2010 – Sep 2014'),
      bullet([
        { text: 'I created the S&OP function from scratch, leading monthly executive meetings with sales, production, finance, and supply to align demand, capacity, and cost for ', bold: false },
        { text: '40K SKUs', bold: true },
        { text: '. Stakeholder management across functions ensured alignment on capacity planning.', bold: false }
      ]),
      bullet([
        { text: 'I built MRP simulators in Excel/VBA, managed safety stock policies, and coordinated national and international outsourcing planning.' }
      ]),
      bullet([
        { text: 'I reduced GGF by ', bold: false },
        { text: 'R$8MM', bold: true },
        { text: ' through cost reduction and process improvement initiatives, delivering R$4.6MM above target.', bold: false }
      ]),
      espaco(6),
      cargoParagraph('Distribution Center Coordinator', 'Scalina (Trifil)', 'Jan 2007 – Oct 2007'),
      bullet([
        { text: 'I managed the distribution center with picking, packing, storage, and WMS implementation using RF scanners and Wi-Fi.' }
      ]),
      bullet([
        { text: 'I implemented inventory rotation, address mapping, and visual replenishment systems to improve operational flow.' }
      ]),
      bullet([
        { text: 'I increased inventory accuracy from 85% to ', bold: false },
        { text: '98%', bold: true },
        { text: ', improved picker productivity by ', bold: false },
        { text: '35%', bold: true },
        { text: ', and reduced losses by 30%.', bold: false }
      ]),
      espaco(6),
      cargoParagraph('Manager of Commercial Planning and Operations', 'VivaReal', 'May 2015 – Dec 2017'),
      bullet([
        { text: 'I led commercial planning and operations for a real estate marketplace, with a team of 33 people across quality, SDR, and property registration.' }
      ]),
      bullet([
        { text: 'I implemented data-driven processes with SQL and dashboards, increasing SDR conversion from 18% to ', bold: false },
        { text: '50%', bold: true },
        { text: ' and reducing customer acquisition cost by 40%.', bold: false }
      ]),
      bullet([
        { text: 'I built the CS area from scratch, scaling to 91 people and achieving ', bold: false },
        { text: 'NPS 80%', bold: true },
        { text: ' and CSAT above 92%.', bold: false }
      ]),
      espaco(8),
      secao('Education'),
      espaco(3),
      bullet([
        { text: 'Specialization Certificate in Corporate Strategies — BSP Business School Sao Paulo (2016–2017)' }
      ]),
      bullet([
        { text: 'Chemical Engineer — Faculdades Oswaldo Cruz (2014)' }
      ]),
      bullet([
        { text: 'Six Sigma Green Belt — Setec Consulting (2020)' }
      ]),
      espaco(8),
      secao('Technical Skills'),
      espaco(3),
      paragrafo('SQL · Python · Databricks · Grafana · Excel/VBA · Power BI · Metabase · WMS · ERP (Infor LN)'),
      espaco(8),
      secao('Languages'),
      espaco(3),
      bullet([
        { text: 'Portuguese — Native' }
      ]),
      bullet([
        { text: 'English — Advanced' }
      ])
    ]
  }]
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync('outputs/_tmp/cv_capacity_planning_manager_amazon_en.docx', buffer);
  console.log('ok');
});