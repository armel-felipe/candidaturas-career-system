const { spawnSync } = require('child_process');
const path = require('path');
const fs = require('fs');

const contentPath = '.career-state/general_cv_content.json';
const data = JSON.parse(fs.readFileSync(contentPath, 'utf8'));
const outputDir = 'outputs';
const outputName = 'felipe_armel_cv_geral_operacoes_supply_chain_conciso.docx';

const { Document, Packer, Paragraph, TextRun, ExternalHyperlink, LevelFormat, AlignmentType, BorderStyle, TabStopPosition, TabStopType } = require('docx');
const pt = n => n * 2;
const workspace = process.cwd();

function hl(text, url) {
  return new Paragraph({
    children: [new ExternalHyperlink({ link: url, children: [new TextRun({ text, style: 'Hyperlink', size: pt(9), font: 'Arial' })] })],
    spacing: { after: 0 },
  });
}
function p(text, opts) {
  return new Paragraph({
    children: [new TextRun({ text, size: pt(opts && opts.size || 9), bold: !!(opts && opts.bold), font: 'Arial' })],
    spacing: { after: 0 },
  });
}
function sec(text) {
  return new Paragraph({
    children: [new TextRun({ text, size: pt(12), font: 'Arial' })],
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: '000000', space: 1 } },
    spacing: { before: pt(6), after: pt(3) },
  });
}
function sp(s) { return new Paragraph({ children: [new TextRun({ text: '', size: pt(s || 6), font: 'Arial' })], spacing: { after: 0 } }); }
function cp(cargo, empresa, periodo) {
  return new Paragraph({
    tabStops: [{ type: TabStopType.RIGHT, position: TabStopPosition.MAX }],
    children: [
      new TextRun({ text: cargo + ' - ' + empresa, bold: true, size: pt(9), font: 'Arial' }),
      new TextRun({ text: '\t' + periodo, size: pt(9), font: 'Arial' }),
    ],
    spacing: { after: 0 },
  });
}
function bl(text) {
  return new Paragraph({
    numbering: { reference: 'bullets', level: 0 },
    children: [new TextRun({ text, size: pt(9), font: 'Arial' })],
    spacing: { after: pt(2) },
  });
}

const children = [
  p('Felipe Armel Dias da Silva', { size: 12, bold: true }),
  hl('linkedin.com/in/felipearmel', 'https://linkedin.com/in/felipearmel'),
  p('Sao Paulo, SP'),
  hl('(11) 98674-8218', 'https://wa.me/5511986748218'),
  hl('armelfelipe@gmail.com', 'mailto:armelfelipe@gmail.com'),
  sp(8),
  sec('Resumo'),
  p(data.summary || ''),
  sp(8),
  sec('Experiencia'),
];

for (const exp of data.experiences || []) {
  children.push(cp(exp.role || '', exp.company || '', exp.period || ''));
  for (const item of exp.bullets || []) {
    children.push(bl(item.text || ''));
  }
  children.push(sp(6));
}

if (Array.isArray(data.education) && data.education.length) {
  children.push(sec('Formacao'));
  for (const item of data.education) children.push(bl(item));
  children.push(sp(8));
}
if (Array.isArray(data.languages) && data.languages.length) {
  children.push(sec('Idiomas'));
  for (const item of data.languages) children.push(bl(item));
}

const doc = new Document({
  styles: {
    default: { document: { run: { font: 'Arial', size: pt(9) } } },
    paragraphStyles: [
      { id: 'Normal', name: 'Normal', quickFormat: true, run: { font: 'Arial', size: pt(9) }, paragraph: { spacing: { after: 0 } } },
      { id: 'ListParagraph', name: 'List Paragraph', basedOn: 'Normal', quickFormat: true, run: { font: 'Arial', size: pt(9) }, paragraph: { spacing: { after: 0 } } },
    ],
  },
  numbering: {
    config: [{
      reference: 'bullets',
      levels: [{ level: 0, format: LevelFormat.BULLET, text: '\u2022', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 360, hanging: 180 } } } }],
    }],
  },
  sections: [{ properties: { page: { margin: { top: 720, right: 504, bottom: 720, left: 504 } } }, children }],
});

async function main() {
  const outputPath = path.join(outputDir, outputName);
  const buf = await Packer.toBuffer(doc);
  fs.writeFileSync(outputPath, buf);
  console.log('DOCX:', outputPath, '(' + buf.length + ' bytes)');
  const themeResult = spawnSync('python3', [path.join(workspace, 'scripts', 'docx', 'inject_arial_theme.py'), outputPath], { stdio: 'inherit' });
  if (themeResult.status !== 0) process.exit(themeResult.status || 1);
  console.log('Theme OK');
}
main().catch(e => { console.error(e); process.exit(1); });
