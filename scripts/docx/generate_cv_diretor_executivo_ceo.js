const { Document, Packer, Paragraph, TextRun, ExternalHyperlink, TabStopType, TabStopPosition, AlignmentType, BorderStyle, LevelFormat } = require('docx');
const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');
const pt = n => n * 2;
const workspace = process.env.CAREER_WORKSPACE || process.cwd();
const outputDir = process.env.CAREER_OUTPUTS || path.join(workspace, 'outputs');
function secao(text) {
  return new Paragraph({ children: [new TextRun({ text, size: pt(12), font: "Arial" })], border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "000000", space: 1 } }, spacing: { before: pt(6), after: pt(3) } });
}
function espaco(p = 6) { return new Paragraph({ children: [new TextRun({ text: "", size: pt(p), font: "Arial" })], spacing: { after: 0 } }); }
function cp(cargo, empresa, periodo) {
  return new Paragraph({ tabStops: [{ type: TabStopType.RIGHT, position: TabStopPosition.MAX }], children: [new TextRun({ text: `${cargo} — ${empresa}`, bold: true, size: pt(9), font: "Arial" }), new TextRun({ text: "\t" + periodo, size: pt(9), font: "Arial" })], spacing: { after: 0 } });
}
function b(text) {
  return new Paragraph({ numbering: { reference: "bullets", level: 0 }, children: [new TextRun({ text, size: pt(9), font: "Arial" })], spacing: { after: pt(2) } });
}
async function main() {
  const n = process.argv[2] || "felipe_armel_cv_diretor_executivo_ceo.docx";
  fs.mkdirSync(outputDir, { recursive: true });
  const doc = new Document({
    creator: "Felipe Armel", title: "Felipe Armel - Diretor Executivo CEO Senior", description: "CV for Director Executive CEO Senior position",
    numbering: { config: [{ reference: "bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "\u2022", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 360, hanging: 180 } } } }] }] },
    styles: { default: { document: { run: { font: "Arial", size: pt(9) } } }, paragraphStyles: [{ id: "Normal", name: "Normal", quickFormat: true, run: { font: "Arial", size: pt(9) }, paragraph: { spacing: { after: 0 } } }, { id: "ListParagraph", name: "List Paragraph", basedOn: "Normal", quickFormat: true, run: { font: "Arial", size: pt(9) }, paragraph: { spacing: { after: 0 } } }] },
    sections: [{ properties: { page: { margin: { top: 720, right: 504, bottom: 720, left: 504 } } }, children: [
      new Paragraph({ children: [new TextRun({ text: "Felipe Armel Dias da Silva", bold: true, size: pt(12), font: "Arial" })], spacing: { after: 0 } }),
      new Paragraph({
        children: [
          new ExternalHyperlink({
            children: [new TextRun({ text: "linkedin.com/in/felipearmel", style: "Hyperlink", size: pt(9), font: "Arial" })],
            link: "https://linkedin.com/in/felipearmel"
          })
        ],
        spacing: { after: 0 }
      }),
      new Paragraph({ children: [new TextRun({ text: "São Paulo, SP", size: pt(9), font: "Arial" })], spacing: { after: 0 } }),
      new Paragraph({
        children: [
          new ExternalHyperlink({
            children: [new TextRun({ text: "(11) 98674-8218", style: "Hyperlink", size: pt(9), font: "Arial" })],
            link: "https://wa.me/5511986748218"
          })
        ],
        spacing: { after: 0 }
      }),
      new Paragraph({
        children: [
          new ExternalHyperlink({
            children: [new TextRun({ text: "armelfelipe@gmail.com", style: "Hyperlink", size: pt(9), font: "Arial" })],
            link: "mailto:armelfelipe@gmail.com"
          })
        ],
        spacing: { after: pt(4) }
      }),
      espaco(3),
      secao("Resumo"),
      new Paragraph({ children: [new TextRun({ text: "Executivo com 20 anos em operações digitais e transformação de negócios em marketplace e tecnologia. Como Diretor no iFood, liderei 240 pessoas com budget de R$300MM/ano, expandindo logística de 400 para 800 cidades (30M pedidos/mês) combinando P&L, pricing e escala para proteger EBITDA. Na WeHandle, reestruturei operação do zero com impacto de 15% na margem bruta conectando dados via API própria.", size: pt(9), font: "Arial" })], spacing: { after: pt(4) } }),
      espaco(6),
      secao("Experiência"),
      cp("Head de Operações", "WeHandle", "mai/2024 — fev/2026"),
      b("Reestruturei a operação de suporte com time de 30 pessoas, conduzindo transformação IA first com duas migrações de plataforma, chatbot e canal WhatsApp — custo por atendimento de R$4,14 para R$3,61, CSAT de 85% para 92%, impacto de 15% na margem bruta."),
      b("Conectei via API três plataformas de atendimento (Movidesk, CloudHumans, Zendesk) — dados disponíveis em tempo real 3 meses antes da área de dados corporativa, com redução de 60% no backlog e SLA de 67% para 85%."),
      b("Implementei canais de atendimento (WhatsApp, IA, chatbot) reduzindo custo de R$4,14 para R$3,61 (—13%). CSAT 85%→92%, SLA 95%, backlog —60%. Relação direta com fundadores em startup de construção."),
      espaco(6),
      cp("Diretor de Operações", "iFood", "abr/2022 — mar/2024"),
      b("Fui responsável pelo P&L de custo das entregas com budget de R$300MM/ano e 240 pessoas, com leitura semanal de DRE e trade-offs entre nível de serviço e rentabilidade — redução de 3% YoY protegendo EBITDA."),
      b("Conduzi S&OP executivo mensal conectando marketing, operação e finanças — colaboração C-level para direcionais e cenários de budget. Expansão de 400 para 800 cidades com 30M pedidos/mês."),
      b("Liderei lançamento de frota dedicada, MPOS em 352 cidades e pagamento em dinheiro (200K pedidos/mês) — liderança de 240 pessoas em FieldOps, Pagamentos e Novos Negócios."),
      espaco(6),
      cp("Head de Operações", "iFood", "nov/2018 — mar/2022"),
      b("Construí torre de operações no México com métricas em tempo real — experimentos controlados de elasticidade de preço que reduziram cancelamentos em 60%."),
      b("Desenvolvi simulador de capacidade de frota com Python e SQL que manteve nível de serviço com saving de R$70M/ano — liderança de equipe de 28 pessoas em liveOps e pricing."),
      b("Conduzi transformação logística escalando de 800K para 30M pedidos/mês com time de 28 pessoas em liveOps, pricing e modelagem de dados."),
      espaco(6),
      cp("Gerente de Customer Success", "Renault do Brasil", "jan/2018 — out/2018"),
      b("Internalizei operação de 2 BPOs com 40 PAS para equipe própria de 8 pessoas, subindo conversão de leads de 24% para 46% com discadores programados por mim e governança de SLA."),
      b("Aprovei projeto de ROI que motivou minha contratação em 2 reuniões — redução de equipe com valor mais alto por HC, usando dados para demonstrar viabilidade financeira."),
      b("Estruturei modelo escalável de CS com migração de operação terceirizada para estrutura própria, implantando controle de funil, SLA de retorno e priorização inteligente de leads — conversão dobrou em 90 dias."),
      espaco(6),
      cp("Gerente de Planejamento Comercial e Operações", "VivaReal", "mai/2015 — dez/2017"),
      b("Arquitetei área de CS que escalou para 91 pessoas com NPS 80%, CSAT acima de 92% e churn abaixo de 3%/mês — foco em retenção e melhoria contínua. Nunca fui gestor direto de CS."),
      b("Desenvolvi dashboards SQL que reduziram tempo de relatório de 4h para 14min. Estruturei SDR com conversão inbound de 18% para 50%, reduzindo custo de vendas em 40%."),
      b("Interface direta com CFO para DRE, cenários e decisões de investimento — alinhamento entre operação, produto e resultado financeiro."),
      espaco(6),
      cp("Coordenador de S&OP", "Trifil", "jan/2006 — dez/2014"),
      b("Criei área de S&OP do zero e sustentei por 4 anos com KPIs de OTIF, fill rate, acurácia e giro reportados ao CEO. Gerenciei 40K SKUs em duas marcas e todos os canais de distribuição."),
      b("Desenvolvi sistema VBA de alocação de estoque que maximizou faturamento de R$80M para R$120M/ano. Reduzi R$8M de GGF do P&L em 2014 com otimização de energia, gás e materiais."),
      b("Liderei projetos CAPEX de 24 teares (—15% custo fabricação) e automação de tinturaria (—40% custo, payback real 1,5 anos vs 3 projetados) — ROI, VPL e análise de viabilidade aplicados."),
      espaco(8),
      secao("Formação"),
      new Paragraph({ children: [new TextRun({ text: "MBA Corporate Strategy — Business School São Paulo (2017)", bold: true, size: pt(9), font: "Arial" })], spacing: { after: pt(2) } }),
      new Paragraph({ children: [new TextRun({ text: "Engenharia Química — Faculdades Oswaldo Cruz (2014)", bold: true, size: pt(9), font: "Arial" })], spacing: { after: pt(2) } }),
      new Paragraph({ children: [new TextRun({ text: "Six Sigma Green Belt — Setec Consulting (2020)", bold: true, size: pt(9), font: "Arial" })], spacing: { after: pt(2) } }),
      espaco(6),
      secao("Stack técnica"),
      new Paragraph({ children: [new TextRun({ text: "Python · SQL · Databricks · Grafana · Tableau · Excel VBA · Salesforce · Zendesk · ClickUp · SAP", size: pt(9), font: "Arial" })], spacing: { after: 0 } }),
      espaco(6),
      secao("Competências"),
      new Paragraph({ children: [new TextRun({ text: "Growth Strategy · Revenue Operations · Operational Scale-Up · P&L Management · Data-Driven Decision Making · Team Leadership · Business Experimentation · New Business Development · Process & Governance · KPI Definition & Tracking · Scalable Digital Operations · Intrapreneurship · Budget Allocation · Business Operations · Channel Expansion", size: pt(9), font: "Arial" })], spacing: { after: 0 } }),
      espaco(6),
      secao("Idiomas"),
      new Paragraph({ numbering: { reference: "bullets", level: 0 }, children: [new TextRun({ text: "Português — Nativo", size: pt(9), font: "Arial" })], spacing: { after: pt(2) } }),
      new Paragraph({ numbering: { reference: "bullets", level: 0 }, children: [new TextRun({ text: "Inglês — Avançado", size: pt(9), font: "Arial" })], spacing: { after: 0 } })
    ] }]
  });
  const buffer = await Packer.toBuffer(doc);
  const p = path.join(outputDir, n);
  fs.writeFileSync(p, buffer);
  const t = path.join(workspace, "scripts", "docx", "inject_arial_theme.py");
  const tr = spawnSync(process.env.PYTHON || "python3", [t, p], { stdio: "inherit" });
  if (tr.status !== 0) process.exit(tr.status || 1);
  console.log(p);
}
main().catch(e => { console.error(e); process.exit(1); });
