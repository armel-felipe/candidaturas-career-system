const { Document, Paragraph, TextSrun, AlignmentParagraphOptions, ExternalHyperlink, HeadingLevel } = require('docx');
const fs = require('fs');
const path = require('path');

async function generateCV() {
  const doc = new Document({
    sections: [{
      properties: {},
      children: [
        new Paragraph({
          children: [new TextSrun({ text: "Felipe Armel Dias da Silva", bold: true, size: 24, font: "Arial" })],
          alignment: AlignmentParagraphOptions.CENTER,
        }),
        new Paragraph({
          children: [
            new ExternalHyperlink({
              children: [new TextSrun({ text: "linkedin.com/in/felipearmel", style: "Hyperlink", size: 10, font: "Arial" })],
              link: "https://linkedin.com/in/felipearmel"
            })
          ],
          alignment: AlignmentParagraphOptions.CENTER,
        }),
        new Paragraph({
          children: [new TextSrun({ text: "São Paulo, SP", size: 10, font: "Arial" })],
          alignment: AlignmentParagraphOptions.CENTER,
        }),
        new Paragraph({
          children: [new TextSrun({ text: "(11) 98674-8218", size: 10, font: "Arial" })],
          alignment: AlignmentParagraphOptions.CENTER,
        }),
        new Paragraph({
          children: [
            new ExternalHyperlink({
              children: [new TextSrun({ text: "mailto:armelfelipe@gmail.com", style: "Hyperlink", size: 10, font: "Arial" })],
              link: "mailto:armelfelipe@gmail.com"
            })
          ],
          alignment: AlignmentParagraphOptions.CENTER,
        }),
        new Paragraph({ text: "Resumo", heading: HeadingLevel.HEADING_1, spacing: { before: 200 } }),
        new Paragraph({
          children: [
            new TextSrun({
              text: "Executivo com 20 anos em operações digitais e transformação de negócios em marketplace e tecnologia. Como Diretor no iFood, liderei 240 pessoas com budget de R$300MM/ano, expandindo logística de 400 para 800 cidades combinando P&L, pricing e escala para proteger EBITDA. Na wehandle, reestruturei a operação de suporte com foco em AI-first, impactando em 15% a margem bruta através de simulações de receita e custo.",
              size: 10,
              font: "Arial"
            })
          ],
          spacing: { after: 200 }
        }),
        new Paragraph({ text: "Experiência Profissional", heading: HeadingLevel.HEADING_1, spacing: { before: 200 } }),
        new Paragraph({ children: [new TextSrun({ text: "wehandle | Head de Operações", bold: true, font: "Arial" })], spacing: { before: 200 } }),
        new Paragraph({ children: [new TextSrun({ text: "Maio 2024 — Fev 2026", size: 9, font: "Arial" })] }),
        new Paragraph({ children: [new TextSrun({ text: "• Reestruturei a operação de suporte impactando em 15% a margem bruta através de simulações de receita e análise de cenários de custo.", size: 10, font: "Arial" })] }),
        new Paragraph({ children: [new TextSrun({ text: "• Liderei a transição para modelo AI-first no suporte, reduzindo o custo total de atendimento de R$4,14 para R$3,61 via automação e canais digitais.", size: 10, font: "Arial" })] }),
        new Paragraph({ children: [new TextSrun({ text: "• Implementei automações via chatbot e IA humanizada, elevando a produtividade operacional em 25% e melhorando o CSAT para 92%.", size: 10, font: "Arial" })] }),
        new Paragraph({ children: [new TextSrun({ text: "iFood | Diretor de Operações", bold: true, font: "Arial" })], spacing: { before: 200 } }),
        new Paragraph({ children: [new TextSrun({ text: "Abr 2022 — Mar 2024", size: 9, font: "Arial" })] }),
        new Paragraph({ children: [new TextSrun({ text: "• Liderei a gestão de P&L de R$300MM/ano, aplicando conceitos de unit economics para otimizar a margem de contribuição logística e proteger EBITDA YoY.", size: 10, font: "Arial" })] }),
        new Paragraph({ children: [new TextSrun({ text: "• Implementei governança de S&OP executivo, conectando demanda, supply e custo para tomada de decisão de curto prazo e proteção de margem.", size: 10, font: "Arial" })] }),
        new Paragraph({ children: [new TextSrun({ text: "• Reduzi a indisponibilidade da frota de 5% para 1% no Brasil, maximizando a delivery efficiency nas principais metrópoles através de modelos de incentivo dinâmicos.", size: 10, font: "Arial" })] }),
        new Paragraph({ children: [new TextSrun({ text: "iFood | Head de Operações", bold: true, font: "Arial" })], spacing: { before: 200 } }),
        new Paragraph({ children: [new TextSrun({ text: "Nov 2018 — Mar 2022", size: 9, font: "Arial" })] }),
        new Paragraph({ children: [new TextSrun({ text: "• Estruturei o planejamento de capacidade (capacity planning) e balanceamento de frota para expandir a cobertura de 400 para 800 cidades.", size: 10, font: "Arial" })] }),
        new Paragraph({ children: [new TextSrun({ text: "• Criei simuladores de nivel de serviço que mantiveram a operação sob controle com um saving de R$70M/ano em custos de distribuição.", size: 10, font: "Arial" })] }),
        new Paragraph({ children: [new TextSrun({ text: "• Defini a arquitetura de remuneração de entregadores por zona, utilizando testes de elasticidade de preço para equilibrar oferta e demanda em tempo real.", size: 10, font: "Arial" })] }),
        new Paragraph({ children: [new TextSrun({ text: "Renault do Brasil | Gerente de Customer Success", bold: true, font: "Arial" })], spacing: { before: 200 } }),
        new Paragraph({ children: [new TextSrun({ text: "Jan 2018 — Out 2018", size: 9, font: "Arial" })] }),
        new Paragraph({ children: [new TextSrun({ text: "• Conduzi a migração de BPO para estrutura interna, otimizando o strategic staffing para elevar a conversão de leads de 24% para 46%.", size: 10, font: "Arial" })] }),
        new Paragraph({ children: [new TextSrun({ text: "• Estabeleci governança de SLA e controle de funil rigoroso, estabilizando a execução comercial em ambiente de alta pressão.", size: 10, font: "Arial" })] }),
        new Paragraph({ children: [new TextSrun({ text: "• Redesenhei o fluxo digital de contato com consumidores, integrando plataformas para reduzir fricção no funil e perdas por tempo de resposta.", size: 10, font: "Arial" })] }),
        new Paragraph({ children: [new TextSrun({ text: "VivaReal | Gerente de Planejamento Comercial e Operações", bold: true, font: "Arial" })], spacing: { before: 200 } }),
        new Paragraph({ children: [new TextSrun({ text: "Mai 2015 — Dez 2017", size: 9, font: "Arial" })] }),
        new Paragraph({ children: [new TextSrun({ text: "• Fui o arquiteto da área de CS, desenhando processos de onboarding e régua de atendimento para uma operação que escalou para 91 pessoas.", size: 10, font: "Arial" })] }),
        new Paragraph({ children: [new TextSrun({ text: "• Otimizei a esteira de SDR, aumentando a conversão de leads inbound de 18% para 50% e reduzindo o custo de vendas em 40%.", size: 10, font: "Arial" })] }),
        new Paragraph({ children: [new TextSrun({ text: "• Gerenciei a leitura financeira da área com interface direta ao CFO, justificando alocações de budget e construindo cenários de receita para o board.", size: 10, font: "Arial" })] }),
        new Paragraph({ children: [new TextSrun({ text: "Trifil | Coordenador de S&OP / Inteligência Comercial", bold: true, font: "Arial" })], spacing: { before: 200 } }),
        new Paragraph({ children: [new TextSrun({ text: "Jan 2006 — Dez 2014", size: 9, font: "Arial" })] }),
        new Paragraph({ children: [new TextSrun({ text: "• Criei a área de S&OP do zero, sustentando ritos de planejamento integrado para 40K SKUs distribuídos em múltiplos canais (S&OP Executive).", size: 10, font: "Arial" })] }),
        new Paragraph({ children: [new TextSrun({ text: "• Reduzi R$8MM de GGF no P&L da empresa através da otimização de gastos com energia, gás e embalagens.", size: 10, font: "Arial" })] }),
        new Paragraph({ children: [new TextSrun({ text: "• Implementei sistema de gestão por objetivos (GPD) em toda a planta, elevando a eficiência operacional via análise de estratificações.", size: 10, font: "Arial" })] }),
        new Paragraph({ children: [new TextSrun({ text: "Essencis | Analista de Negócios", bold: true, font: "Arial" })], spacing: { before: 200 } }),
        new Paragraph({ children: [new TextSrun({ text: "Nov 2001 — Abr 2002", size: 9, font: "Arial" })] }),
        new Paragraph({ children: [new TextSrun({ text: "• Montei Planos de Negócios para aprovação de projetos de expansão (M&A e construção) em conselho de administração.", size: 10, font: "Arial" })] }),
        new Paragraph({ children: [new TextSrun({ text: "• Realizei análises de viabilidade econômica utilizando Fluxo de Caixa Descontado (DCF), VPL e Payback para decisão de investimento.", size: 10, font: "Arial" })] }),
        new Paragraph({ text: "Formação", heading: HeadingLevel.HEADING_1, spacing: { before: 200 } }),
        new Paragraph({ children: [new TextSrun({ text: "MBA Corporate Strategy — BSP Business School São Paulo (2017)", size: 10, font: "Arial" })] }),
        new Paragraph({ children: [new TextSrun({ text: "Engenheiro Químico — Faculdades Oswaldo Cruz (2014)", size: 10, font: "Arial" })] }),
        new Paragraph({ children: [new TextSrun({ text: "Técnico em Química — SENAI Mario Amato (1997)", size: 10, font: "Arial" })] }),
        new Paragraph({ text: "Stack técnica", heading: HeadingLevel.HEADING_1, spacing: { before: 200 } }),
        new Paragraph({ children: [new TextSrun({ text: "Excel Avançado + VBA, SQL, PySpark, Python, Databricks, Grafana, Salesforce, Zendesk, Movidesk, CloudHumans, ERP LN Infor, Power BI", size: 10, font: "Arial" })] }),
        new Paragraph({ text: "Competências", heading: HeadingLevel.HEADING_1, spacing: { before: 200 } }),
        new Paragraph({ 
          children: [new TextSrun({ 
            text: "Unit Economics · Margin Ownership · Capacity Planning · Operational Governance · AI Implementation · Automation · Strategic Staffing · Burn vs Plan · Delivery Efficiency · Profitability · S&OP Executive · Unit Cost Reduction · SLA Governance · Cross-functional Alignment · Scalable Delivery Framework_ la l l l l l l l l l l l l l l l l la l", 
            size: 10, 
            font: "Arial" 
          })], 
          spacing: { after: 200 } 
        }),
      ]
    })
  });

  const buffer = await doc.render();
  fs.writeFileSync(path.resolve('outputs/felipe_armel_cv_monks.docx'), buffer);
}

generateCV().then(() => console.log("CV generated: outputs/felipe_armel_cv_monks.docx")).catch(console.error);
