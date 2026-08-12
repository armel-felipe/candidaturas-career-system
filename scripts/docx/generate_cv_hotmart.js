const { Document, Packer, Paragraph, TextRun, TabStopType, TabStopPosition, AlignmentType, BorderStyle, ExternalHyperlink, LevelFormat } = require('docx');
const fs = require('fs');
const path = require('path');

const pt = n => n * 2; // half-points — NUNCA n * 20

function secao(text) {
  return new Paragraph({
    children: [new TextRun({ text, size: pt(12), font: "Arial" })],
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "000000", space: 1 } },
    spacing: { before: pt(6), after: pt(3) }
  });
}

function espaco(ptSize = 6) {
  return new Paragraph({
    children: [new TextRun({ text: "", size: pt(ptSize), font: "Arial" })],
    spacing: { after: 0 }
  });
}

function cargoParagraph(cargo, empresa, periodo) {
  return new Paragraph({
    tabStops: [{ type: TabStopType.RIGHT, position: TabStopPosition.MAX }],
    children: [
      new TextRun({ text: `${cargo} — ${empresa}`, bold: true, size: pt(9), font: "Arial" }),
      new TextRun({ text: "\t" + periodo, size: pt(9), font: "Arial" })
    ],
    spacing: { after: 0 }
  });
}

function bullet(runs) {
  const children = runs.map(r =>
    new TextRun({ text: r.text, bold: r.bold || false, size: pt(9), font: "Arial" })
  );
  return new Paragraph({
    numbering: { reference: "bullets", level: 0 },
    children,
    spacing: { after: pt(2) }
  });
}

// Nome do arquivo slug
const slug = "business_operations_senior_hotmart";

const doc = new Document({
  creator: "Felipe Armel",
  title: `Felipe Armel - CV - Hotmart - Business Operations Sênior`,
  description: "CV para Hotmart - Business Operations Sênior | Parcerias Estratégicas",
  numbering: {
    config: [{
      reference: "bullets",
      levels: [{
        level: 0, format: LevelFormat.BULLET, text: "\u2022",
        alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 360, hanging: 180 } } }
      }]
    }]
  },
  styles: {
    default: {
      document: { run: { font: "Arial", size: pt(9) } }
    },
    paragraphStyles: [
      { id: "Normal", name: "Normal", quickFormat: true,
        run: { font: "Arial", size: pt(9) },
        paragraph: { spacing: { after: 0 } } },
      { id: "ListParagraph", name: "List Paragraph", basedOn: "Normal", quickFormat: true,
        run: { font: "Arial", size: pt(9) },
        paragraph: { spacing: { after: 0 } } }
    ]
  },
  sections: [{
    properties: {
      page: { margin: { top: 720, right: 504, bottom: 720, left: 504 } }
    },
    children: [
      // Nome
      new Paragraph({
        children: [new TextRun({ text: "Felipe Armel Dias da Silva", bold: true, size: pt(12), font: "Arial" })],
        spacing: { after: 0 }
      }),
      // LinkedIn
      new Paragraph({
        children: [
          new ExternalHyperlink({
            children: [new TextRun({ text: "linkedin.com/in/felipearmel", style: "Hyperlink", size: pt(9), font: "Arial" })],
            link: "https://linkedin.com/in/felipearmel"
          })
        ],
        spacing: { after: 0 }
      }),
      // Localização
      new Paragraph({
        children: [new TextRun({ text: "São Paulo, SP", size: pt(9), font: "Arial" })],
        spacing: { after: 0 }
      }),
      // WhatsApp
      new Paragraph({
        children: [
          new ExternalHyperlink({
            children: [new TextRun({ text: "(11) 98674-8218", style: "Hyperlink", size: pt(9), font: "Arial" })],
            link: "https://wa.me/5511986748218"
          })
        ],
        spacing: { after: 0 }
      }),
      // Email
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

      // Resumo — max 480 chars, factual
      secao("Resumo"),
      new Paragraph({
        children: [
          new TextRun({ text: "Executivo com 20 anos em operações digitais e transformação de negócios em marketplace e tecnologia. Como Diretor de Operações no iFood, liderei 240 pessoas com budget de R$300MM/ano, expandindo logística de 400 para 800 cidades e combinando P&L, pricing e escala para proteger EBITDA. Na WeHandle como Head de Operações, reestruturei operação do zero com impacto de 15% na margem bruta, conectando dados via API própria. Busco posição de Business Operations Sênior.", size: pt(9), font: "Arial" })
        ],
        spacing: { after: pt(4) }
      }),

      espaco(6),

      // Experiência
      secao("Experiência"),

      // WeHandle
      cargoParagraph("Head de Operações", "WeHandle", "Mai 2024 – Fev 2026"),
      bullet([{ text: "Fui responsável por reestruturar a operação de atendimento do zero, liderando time de 30 pessoas com autonomia total sobre processos, plataformas e orçamento.", bold: false }]),
      bullet([{ text: "Implantei automação com IA e canal WhatsApp, liderei duas migrações de plataforma e conectei dados via API de três sistemas de atendimento para decisão em tempo real.", bold: false }]),
      bullet([{ text: "Reduzi o custo por atendimento de R$4,14 para R$3,61 e impactei ", bold: false }, { text: "15% na margem bruta", bold: true }, { text: " da empresa, elevando CSAT de 85% para 92%.", bold: false }]),

      espaco(6),

      // iFood Diretor
      cargoParagraph("Diretor de Operações", "iFood", "Abr 2022 – Mar 2024"),
      bullet([{ text: "Fui responsável por gerir as operações logísticas com orçamento de ", bold: false }, { text: "R$300MM/ano", bold: true }, { text: " e equipe de 240 pessoas, acumulando FieldOps, Meios de Pagamento e Novos Negócios.", bold: false }]),
      bullet([{ text: "Conduzi o rito executivo de S&OP conectando marketing, operações, produto e C-level, com modelagem em Python, SQL e Databricks.", bold: false }]),
      bullet([{ text: "Ampliei cobertura de 400 para 800 cidades em operação de 30M pedidos/mês e protegi a meta de EBITDA com cenários executivos de trade-off.", bold: false }]),

      espaco(6),

      // iFood Head
      cargoParagraph("Head de Operações", "iFood", "Nov 2018 – Mar 2022"),
      bullet([{ text: "Fui responsável por planejar e executar a estratégia de frota e supply, estruturando a operação logística para escala nacional.", bold: false }]),
      bullet([{ text: "Conduzi testes controlados de elasticidade de preço e métricas em tempo real no Grafana, com análises em Python, SQL e Databricks.", bold: false }]),
      bullet([{ text: "Gerei saving de ", bold: false }, { text: "R$70MM/ano", bold: true }, { text: " com simulador de alocação de frota e reduzi indisponibilidade de 5% para 1%.", bold: false }]),

      espaco(6),

      // Renault
      cargoParagraph("Gerente de Customer Service", "Renault", "Jan 2018 – Out 2018"),
      bullet([{ text: "Fui responsável por estruturar o Customer Service da divisão de frotas e fidelidade, gerenciando operação de pós-venda e relacionamento com frotistas.", bold: false }]),
      bullet([{ text: "Estruturei modelo escalável com migração BPO, controle de funil de vendas e SLA baseado em dados, utilizando Power BI e Excel VBA.", bold: false }]),
      bullet([{ text: "Elevei conversão de leads de 24% para 46% e aprovei projeto de R$2MM em duas reuniões de diretoria com ROI calculado.", bold: false }]),

      espaco(6),

      // VivaReal
      cargoParagraph("Gerente de Planejamento Comercial e Operações", "VivaReal", "Mai 2015 – Dez 2017"),
      bullet([{ text: "Fui responsável por arquitetar a área de Customer Success do zero, crescendo para 91 pessoas com operação multicanal de suporte e implantação.", bold: false }]),
      bullet([{ text: "Estruturei processos de onboarding, SLA, qualidade e P&L da área, com interface direta com CFO e produto para priorização de roadmap.", bold: false }]),
      bullet([{ text: "Elevei conversão SDR inbound de 18% para 50% e reduzi churn via segmentação de clientes por ticket e ROI.", bold: false }]),

      espaco(6),

      // Trifil
      cargoParagraph("Coordenador de S&OP", "Trifil / Scalina", "Jan 2006 – Dez 2014"),
      bullet([{ text: "Fui responsável por criar a área de S&OP do zero, gerenciando 150K SKUs de matéria-prima com rito executivo mensal ao CEO.", bold: false }]),
      bullet([{ text: "Estruturei strategic sourcing e projeto de aquisição de 24 máquinas teares com análise de viabilidade econômica e negociação de contratos.", bold: false }]),
      bullet([{ text: "Reduzi ", bold: false }, { text: "R$8MM de GGF", bold: true }, { text: " do P&L e 15% do custo total de fabricação, sustentando o S&OP por 4 anos.", bold: false }]),

      espaco(8),

      // Formação
      secao("Formação"),
      new Paragraph({
        children: [
          new TextRun({ text: "MBA Corporate Strategy — BSP Business School São Paulo (2017)", size: pt(9), font: "Arial" })
        ],
        spacing: { after: pt(2) }
      }),
      new Paragraph({
        children: [
          new TextRun({ text: "Engenharia Química — Faculdades Oswaldo Cruz (2014)", size: pt(9), font: "Arial" })
        ],
        spacing: { after: pt(2) }
      }),

      espaco(6),

      // Stack técnica
      secao("Stack técnica"),
      new Paragraph({
        children: [
          new TextRun({ text: "Python · SQL · Databricks · Tableau · Grafana · Power BI · Excel VBA · Salesforce · Zendesk", size: pt(9), font: "Arial" })
        ],
        spacing: { after: pt(2) }
      }),

      espaco(6),

      // Competências
      secao("Competências"),
      new Paragraph({
        children: [
          new TextRun({ text: "Business Operations · Parcerias Estratégicas · Processos escaláveis · Alinhamento crossfuncional · Análises de desempenho · Materiais executivos · Interface com Tecnologia / Produto · Gestão de contratos · Perfil analítico / business sense · Excel avançado / PowerPoint · Comunicação executiva · Múltiplos projetos simultâneos · Power BI / visualização de dados · SQL · Empresa de tecnologia / alto crescimento", size: pt(9), font: "Arial" })
        ],
        spacing: { after: pt(2) }
      }),

      espaco(6),

      // Idiomas
      secao("Idiomas"),
      bullet([{ text: "Português — Nativo", bold: false }]),
      bullet([{ text: "Inglês — Avançado", bold: false }])
    ]
  }]
});

const outputPathTmp = path.join(process.cwd(), "outputs", "_tmp", `cv_${slug}.docx`);
fs.mkdirSync(path.dirname(outputPathTmp), { recursive: true });
Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync(outputPathTmp, buffer);
  console.log("ok");
}).catch(err => {
  console.error("ERROR:" + err.message);
  process.exit(1);
});
