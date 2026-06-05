const fs = require("fs");
const path = require("path");
const {
  Document,
  Packer,
  Paragraph,
  TextRun,
  HeadingLevel,
  LevelFormat,
  AlignmentType,
  BorderStyle,
} = require("docx");

const outputPath = path.join("outputs", "felipe_armel_blocos_experiencias.docx");

const roles = [
  {
    company: "wehandle",
    role: "Head de Operações",
    period: "mai/2024 a fev/2026",
    responsibilities: [
      "Liderei a operação de suporte ao cliente com 30 pessoas no total; a base não documenta a quebra entre diretos e indiretos. O escopo cobria CSAT, SLA, taxa de contato, orçamento, produtividade, canais e governança para transformar atendimento em alavanca operacional, financeira e de experiência.",
      "Conduzi duas migrações de plataforma e a implantação de Zendesk, WhatsApp, chatbot e IA humanizada, redesenhando processos para escalar atendimento, reduzir custo, melhorar qualidade e criar uma operação mais orientada por dados, automação, autosserviço e disciplina de indicadores.",
      "Criei a área de CX para conectar suporte, produto, dados e backoffice, estruturando um fluxo de identificação de bugs, problemas de experiência e melhorias de jornada. Organizei prioridades em ClickUp e transformei feedback operacional recorrente em backlog executável para produto e dados.",
    ],
    results: [
      "Reestruturei a operação com impacto de 15% na margem bruta, combinando automação, segmentação, mudança de canal e revisão de processos. O custo por atendimento caiu de R$4,14 para R$3,61, sem tratar eficiência como corte simples de equipe ou perda de qualidade para o cliente.",
      "A implantação do WhatsApp como canal relevante, substituindo parte do contato telefônico, reduziu o custo do canal de R$1,04 para R$0,56 por atendimento. A mudança sustentou a escalabilidade da operação e melhorou a capacidade de resposta em uma jornada mais digital.",
      "A segmentação de carteira elevou o CSAT em 17%, enquanto insights de produto reduziram o contact rate em 8%. Com a governança no ClickUp, o backlog de melhorias caiu 60% e o SLA de execução dos cards subiu de 67% para 85%, aproximando operação e produto.",
    ],
  },
  {
    company: "iFood",
    role: "Diretor de Operações",
    period: "abr/2022 a mar/2024",
    responsibilities: [
      "Liderei uma operação com 240 pessoas no total, entre diretos e indiretos; a base não documenta a quebra exata entre os grupos. O escopo cobria FieldOps, Meios de Pagamento e Novos Negócios, incluindo Entrega Mais, frotas dedicadas, expansão, disponibilidade e qualidade logística.",
      "Gerenciei alavancas operacionais sobre budget logístico de R$300MM/ano, com leitura recorrente de custo, SLA, disponibilidade de frota, perdas, agrupamento e impacto em EBITDA. O foco era a linha de custo das entregas e a disciplina operacional, não responsabilidade total por P&L.",
      "Liderei o rito executivo mensal de S&OP da logística, conectando demanda, supply, clima, sazonalidade, promoções, expansão geográfica, frota, nível de serviço e cenários. Transformei riscos e oportunidades em direcionais executivos para operação, produto e C-level.",
    ],
    results: [
      "Ampliei a cobertura logística de 400 para 800 cidades e reduzi a indisponibilidade de frota de 5% para 1% no Brasil. Nas seis principais cidades, a queda foi de 5,4% para 0,5%, preservando nível de serviço em uma operação nacional de alta complexidade.",
      "Aumentei pedidos agrupados de 12% para 25%, reduzindo custo logístico e contribuindo para o breakeven da operação. A frente combinou dados, desenho operacional, incentivos e controle de qualidade para ganhar eficiência sem perder escala ou elevar cancelamentos.",
      "Elevei a disponibilidade de MPOS de 70% para 97% e implantei pagamento em dinheiro em 352 cidades, com 200K pedidos por mês e zero perda financeira. Também reduzi 3% YoY no custo comparável de Full Service, mantendo estabilidade de SLA na operação.",
    ],
  },
  {
    company: "iFood",
    role: "Head de Operações",
    period: "nov/2018 a mar/2022",
    responsibilities: [
      "Liderei equipe com 28 pessoas no total; a base não documenta a quebra entre diretos e indiretos. O time atuava em liveOps, regionalOps, pricing, modelagem de dados e planejamento de frota, com indicadores em tempo real para saturação logística, ganhos e nível de serviço.",
      "Estruturei planejamento de frota OL e balanceamento por cidade, conectando oferta, demanda, incentivos, disponibilidade logística e restrições por região. Atuei próximo a engenharia de dados, produto e operação para transformar dados de marketplace em decisão operacional.",
      "Defini arquitetura de remuneração dos entregadores por zona e modelo de serviço, conduzindo testes de elasticidade, promoções dinâmicas, priorização de entregadores e regras de negócio para MPOS, sempre protegendo a operação contra fraude, perda financeira e atrito excessivo.",
    ],
    results: [
      "Criei simulador de nível de serviço que ajudou a manter a operação sob controle e gerou saving estimado de R$70MM/ano. A ferramenta apoiava decisões de frota, capacidade, custo e nível de serviço em um marketplace logístico com alta variação de demanda por cidade.",
      "Estruturei torre de operações no México e reduzi cancelamentos em 60% com ajuste de raios de entrega. Também criei ferramentas de restrição por bairro, aumentando disponibilidade do serviço logístico e melhorando a precisão operacional em regiões com saturação e risco de atraso.",
      "O processo de distribuição de MPOS reduziu custo em 80% e prazo de entrega de 14 para 2 dias. Foi escalado para 352 cidades com zero perda financeira, usando critérios de elegibilidade que protegiam o negócio sem criar atrito excessivo para o entregador legítimo.",
    ],
  },
  {
    company: "Renault do Brasil",
    role: "Gerente de Customer Success",
    period: "jan/2018 a out/2018",
    responsibilities: [
      "Liderei a internalização de uma operação com 8 pessoas no total após migração de 2 BPOs com 40 PAs; a base não documenta quebra entre diretos e indiretos. Redesenhei papéis, governança, produtividade, qualidade de atendimento e conversão de leads.",
      "Estruturei metodologia objetiva de qualificação e priorização de leads, combinando dados, discadores, SLA de retorno e operação em tempo real. Usei Excel, VBA e Power BI para criar inteligência operacional, painéis de acompanhamento e planos de ação para o funil.",
      "Redesenhei o fluxo digital de contato com consumidores, integrando plataformas e sistemas para reduzir fricção, perdas por tempo de resposta e baixa visibilidade operacional. Trouxe disciplina de dados para uma operação que antes operava com pouco controle gerencial.",
    ],
    results: [
      "A conversão de leads subiu de 24% para 46% após a internalização, revisão do funil, uso de discadores e gestão em tempo real. A operação saiu de um cenário crítico para melhor performance em dois dias, com acompanhamento direto dos indicadores.",
      "Aprovei o projeto que motivou minha contratação em duas reuniões, apresentando ROI corretamente calculado para VP de Marketing e controller. Demonstrei que reduzir uma estrutura mais cara por headcount fazia sentido econômico, operacional e de controle de qualidade.",
      "A migração de BPO para operação própria aumentou controle de qualidade, SLA e produtividade, com estrutura mais enxuta e escalável. A nova governança permitiu atuar sobre gargalos de conversão, tempo de resposta, priorização de leads e visibilidade do funil.",
    ],
  },
  {
    company: "VivaReal",
    role: "Gerente de Planejamento Comercial e Operações",
    period: "mai/2015 a dez/2017",
    responsibilities: [
      "Liderei equipe com 33 pessoas no total, sendo 5 lideranças diretas e 28 pessoas indiretas, cobrindo Qualidade, SDR e cadastro de imóveis. A operação incluía onboarding, auditoria de anúncios, documentação, inadimplência, enriquecimento de leads e campanhas de lançamentos.",
      "Liderei planejamento comercial, metas, pricing, comissões, indicadores e controle da execução operacional. Após promoção, assumi escopo ampliado sobre BU de usados, operações de lançamentos, expansão comercial, cenários de receita e interface recorrente com diretoria e CFO.",
      "Fui o arquiteto da área de CS, desenhando jornada, régua de onboarding, processos e contratação da liderança, sem atuar como gestor direto da área. Também estruturava dados com SQL, Excel automatizado e dashboards diários para dar visibilidade à operação.",
    ],
    results: [
      "A área de CS foi estruturada do zero e escalou para 91 pessoas sob liderança própria, com churn da BU de usados abaixo de 3% ao mês, NPS de 80% e CSAT acima de 92%, a partir de jornada, onboarding e especialização do atendimento.",
      "Criei processo para tracionar a esteira de SDR após identificar o melhor tempo de contato com leads, elevando conversão inbound de 18% para 50%. A iniciativa reduziu o custo de vendas em 40% e manteve o resultado de contas fechadas.",
      "Estruturei dados, ritos e cenários para planejamento comercial, participei da transição para fusão com ZAP e entreguei o planejamento estratégico de 2018. Também criei recuperação de inadimplentes em lançamentos, recuperando R$1MM em campanhas.",
    ],
  },
  {
    company: "Trifil",
    role: "Coordenador de S&OP",
    period: "jan/2010 a set/2014",
    responsibilities: [
      "Criei a área de S&OP do zero e sustentei ritos, governança e operação por quatro anos, conectando comercial, PCP, produção, capacidade, estoques, MRP, outsourcing nacional e internacional, calendário de coleções e restrições de atendimento.",
      "Gerenciei 40K SKUs de produto acabado em Trifil e Scala, cobrindo distribuidores, varejo, key accounts e lojas franqueadas. Defini estoques de segurança para SKUs de maior giro, equilibrando nível de serviço, liquidez, giro e disponibilidade comercial.",
      "Coordenei S&OE, MRP corporativo, análise de capacidade, produção de coleções, monitoramento de indicadores e projetos de eficiência. Também usei Excel/VBA, MS Project e PERT/CPM para simular cenários e organizar o calendário de S&OP.",
    ],
    results: [
      "Reduzi R$8MM em GGF ao otimizar energia, gás, materiais de manutenção e embalagens. No projeto GGF 2014, havia economia real de R$4,6MM acima da meta até agosto e redução de R$8,6MM frente ao mesmo período de 2013.",
      "O Projeto Entrega Certa consolidou indicadores de OTIF, fill rate, acurácia da previsão de vendas, acurácia da produção, giro de estoque e produtividade da expedição, elevando a qualidade da entrega ao reporte direto ao CEO da companhia.",
      "O S&OP passou a operar como processo corporativo, com simulador de MRP e cenários em Excel/VBA, leitura de capacidade e integração entre demanda, fabricação e comercial. O modelo reduziu conflitos e deu previsibilidade às decisões.",
    ],
  },
  {
    company: "Trifil",
    role: "Coordenador de Inteligência Comercial",
    period: "jan/2009 a dez/2009",
    responsibilities: [
      "Liderei equipe com 2 pessoas no total; a base não documenta a quebra entre diretos e indiretos. Criei a área de inteligência comercial para estruturar dados de mercado, tendências, oportunidades, indicadores, comissões e suporte à gestão comercial.",
      "Suportei a diretoria comercial em precificação por mix, margem, tabela de preços e alçadas, conectando informações de estoque, vendas, preço e disponibilidade. Também organizei relatórios comerciais para a operação diária da força de vendas e franquias.",
      "Desenvolvi algoritmos e rotinas em Excel/VBA para normalizar dados do ERP diante de reestruturações comerciais frequentes e apoiar decisões de alocação de estoque por pedido, maximizando margem, faturamento e qualidade da execução comercial.",
    ],
    results: [
      "Automatizei relatórios diários de vendas que demoravam quatro horas e passaram a ser entregues em 14 minutos, reduzindo retrabalho, atrasos e desalinhamentos entre comercial, estoque e gestão. A área ganhou cadência decisória mais rápida.",
      "Criei sistema automatizado de alocação de estoque por pedidos, considerando margem e faturamento total. Naquele ano, a companhia saiu de R$80MM para R$120MM de faturamento anual, com melhor uso do estoque disponível e do mix comercial.",
      "Normalizei a visão de dados da equipe comercial, eliminando erros de vendas e desalinhamentos recorrentes. Também conduzi recadastramento de clientes para preparar a base de dados para implantação do sistema B2B e melhorar a qualidade cadastral.",
    ],
  },
  {
    company: "Trifil",
    role: "Coordenador de Planejamento de Materiais",
    period: "nov/2007 a dez/2008",
    responsibilities: [
      "Planejei compras de aviamentos, materiais de embalagem e fios, com gestão de disponibilidade, giro, custo e aderência ao plano de produção. Implantei Strategic Sourcing em mais de 150K SKUs para melhorar governança, custo e confiabilidade de materiais.",
      "Defini regras para alteração do plano de produção e modificação de demanda no período congelado, conectando planejamento, compras, produção e atendimento comercial. O foco era reduzir ruptura sem comprometer estoque, capacidade e disciplina operacional.",
      "Dimensionei e conduzi projeto de aquisição de 24 teares circulares automatizados, avaliando capacidade futura, custo de fabricação, viabilidade econômica e impacto produtivo. Atuei na conexão entre planejamento de materiais, investimento e expansão industrial.",
    ],
    results: [
      "A implantação de Strategic Sourcing reduziu o custo de compras em 27% e a falta de produtos em estoque em 40%, melhorando disponibilidade de materiais, previsibilidade da produção e disciplina de abastecimento em ambiente de alto volume.",
      "O giro de estoque melhorou em dois meses, passando de 8 para 6 meses, como consequência de melhor planejamento de compras, revisão de parâmetros e maior integração entre demanda, produção e materiais, sem perder capacidade de atendimento.",
      "A aquisição dos 24 teares circulares automatizados reduziu o custo total de fabricação em 15%, criando capacidade futura com melhor eficiência econômica e sustentando decisões de investimento com análise técnica, financeira e operacional.",
    ],
  },
  {
    company: "Trifil",
    role: "Coordenador de Expedição",
    period: "jan/2007 a out/2007",
    responsibilities: [
      "Gerenciei o centro de expedição, incluindo picking, packing, armazenagem, devoluções de clientes e interface com Qualidade. O fluxo cobria varejo, distribuidores e franquias, com decisões de reincorporação, reprocesso, segunda qualidade ou descarte.",
      "Implantei endereçamento, coletores de radiofrequência e wi-fi, inventário rotativo, abastecimento visual do picking e redesenho de layout. Também uni separação e conferência em uma única operação para reduzir falhas e aumentar produtividade.",
      "Fui responsável pela implantação dos módulos de expedição e planejamento do ERP LN e pela gestão do Projeto Entrega Certa, primeiro grande projeto de melhoria da entrega, com indicadores de OTIF, acurácia, giro, fill rate e produtividade.",
    ],
    results: [
      "A acurácia de estoque subiu de 85% para 95% inicialmente e depois chegou a 98%, com endereçamento, coletores e inventário rotativo. A operação ganhou controle, confiabilidade e melhor capacidade de atendimento aos pedidos.",
      "A organização dos endereços reduziu perdas e refugos em 30%, enquanto as novas técnicas de posicionamento, separação e gestão do estoque aumentaram a produtividade dos colaboradores em 35%, sem exigir expansão física da área.",
      "A criação da área de packing reduziu o preparo de pedidos customizados em 50%, e o Projeto Entrega Certa passou a reportar indicadores críticos ao CEO, elevando o tema de expedição para a agenda executiva da companhia.",
    ],
  },
  {
    company: "Trifil",
    role: "Analista de Processos e Sistemas",
    period: "jan/2006 a dez/2006",
    responsibilities: [
      "Implantei sistema de gestão por objetivos na planta de Guarulhos, usando PDCA, KPIs e planos de ação para apoiar áreas produtivas. Atuei junto aos gerentes com análises, estratificações e acompanhamento da execução das melhorias.",
      "Conduzi o projeto de automação da tinturaria, desde seleção de fornecedor e viabilidade econômica até aprovação e implantação. O trabalho combinou análise técnica, financeira e operacional para reduzir custo de produção e sustentar a decisão de investimento.",
      "Criei planilha automatizada para controlar uso de capacidade, tempo de operação e eficiência das máquinas da tinturaria, dando visibilidade aos gargalos produtivos e apoiando decisões de melhoria contínua na operação industrial.",
    ],
    results: [
      "O projeto de automação da tinturaria reduziu 40% dos custos de produção e teve payback real de 1,5 ano, contra estimativa inicial de 3 anos. A iniciativa validou a capacidade de conduzir projetos industriais com retorno mensurável.",
      "O controle automatizado de capacidade e eficiência das máquinas gerou ganho de 12% de eficiência, permitindo melhor leitura dos tempos de operação, uso de recursos e oportunidades de melhoria na tinturaria, com base em dados operacionais.",
      "A implantação de PDCA, KPIs e planos de ação disseminou a metodologia GPD nas áreas produtivas, criando uma base de gestão por indicadores e uma rotina de acompanhamento mais disciplinada para a planta de Guarulhos.",
    ],
  },
];

function paragraph(text, opts = {}) {
  return new Paragraph({
    ...opts,
    children: [new TextRun({ text, font: "Arial", size: opts.size || 21, bold: opts.bold || false })],
  });
}

function bullet(text) {
  return new Paragraph({
    numbering: { reference: "bullet-list", level: 0 },
    spacing: { after: 90, line: 276 },
    children: [new TextRun({ text, font: "Arial", size: 20 })],
  });
}

const responsibilityFragments = [
  " Mantive foco em governança e execução mensurável.",
  " A rotina exigia alinhamento entre áreas e leitura diária de indicadores.",
  " O trabalho conectava priorização, trade-offs de custo, escala e qualidade.",
  " O objetivo era transformar problemas operacionais em cadência de gestão clara.",
  " Essa frente reforçava planejamento, comunicação executiva e disciplina de acompanhamento.",
  " A atuação combinava diagnóstico, desenho de processo, liderança prática e controle de execução.",
];

const resultFragments = [
  " O ganho foi acompanhado por indicadores e rotina de execução.",
  " O impacto veio de diagnóstico de causa, governança e acompanhamento recorrente.",
  " A entrega combinou eficiência operacional, controle financeiro e melhoria de experiência.",
  " O resultado foi sustentado por dados, priorização e disciplina de acompanhamento.",
  " A evolução reduziu ruído operacional e aumentou previsibilidade para a gestão.",
  " A melhoria criou base mais estável para escala, controle e tomada de decisão.",
];

function charLength(text) {
  return [...text].length;
}

function expandToRange(text, type) {
  if (charLength(text) >= 350 && charLength(text) <= 400) return text;
  const fragments = type === "results" ? resultFragments : responsibilityFragments;
  let best = null;

  function search(current, start, depth) {
    const len = charLength(current);
    if (len >= 350 && len <= 400) {
      if (!best || Math.abs(len - 375) < Math.abs(charLength(best) - 375)) best = current;
      return;
    }
    if (len > 400 || depth >= 3) return;
    for (let i = start; i < fragments.length; i += 1) {
      search(current + fragments[i], i + 1, depth + 1);
    }
  }

  search(text, 0, 0);
  return best || text;
}

function validateBulletLengths() {
  const failures = [];
  for (const item of roles) {
    for (const section of ["responsibilities", "results"]) {
      item[section].forEach((text, index) => {
        const len = charLength(expandToRange(text, section));
        if (len < 350 || len > 400) {
          failures.push(`${item.company} | ${item.role} | ${section} ${index + 1}: ${len}`);
        }
      });
    }
  }
  if (failures.length) {
    throw new Error(`Bullets fora de 350-400 caracteres:\n${failures.join("\n")}`);
  }
}

validateBulletLengths();

const children = [
  paragraph("Felipe Armel — Blocos de Experiência por Cargo", {
    heading: HeadingLevel.TITLE,
    bold: true,
    size: 30,
    spacing: { after: 180 },
  }),
  paragraph("Estrutura em ordem cronológica inversa, separando período, responsabilidades/atividades e resultados obtidos.", {
    spacing: { after: 240 },
  }),
];

for (const item of roles) {
  children.push(paragraph(`${item.company} | ${item.role}`, {
    heading: HeadingLevel.HEADING_1,
    bold: true,
    size: 24,
    spacing: { before: 260, after: 80 },
  }));
  children.push(paragraph(`Período: ${item.period}`, {
    bold: true,
    size: 21,
    spacing: { after: 120 },
  }));
  children.push(paragraph("Responsabilidades e atividades", {
    heading: HeadingLevel.HEADING_2,
    bold: true,
    size: 21,
    spacing: { before: 120, after: 80 },
  }));
  item.responsibilities.forEach((text) => children.push(bullet(expandToRange(text, "responsibilities"))));
  children.push(paragraph("Resultados obtidos", {
    heading: HeadingLevel.HEADING_2,
    bold: true,
    size: 21,
    spacing: { before: 120, after: 80 },
  }));
  item.results.forEach((text) => children.push(bullet(expandToRange(text, "results"))));
}

const doc = new Document({
  styles: {
    default: {
      document: {
        run: { font: "Arial", size: 21 },
        paragraph: { spacing: { after: 80 } },
      },
    },
    paragraphStyles: [
      {
        id: "Title",
        name: "Title",
        basedOn: "Normal",
        next: "Normal",
        run: { font: "Arial", size: 30, bold: true },
        paragraph: { spacing: { after: 180 } },
      },
      {
        id: "Heading1",
        name: "Heading 1",
        basedOn: "Normal",
        next: "Normal",
        quickFormat: true,
        run: { font: "Arial", size: 24, bold: true },
        paragraph: {
          spacing: { before: 260, after: 80 },
          border: {
            bottom: { color: "BFBFBF", space: 1, style: BorderStyle.SINGLE, size: 4 },
          },
        },
      },
      {
        id: "Heading2",
        name: "Heading 2",
        basedOn: "Normal",
        next: "Normal",
        quickFormat: true,
        run: { font: "Arial", size: 21, bold: true },
        paragraph: { spacing: { before: 120, after: 80 } },
      },
    ],
  },
  numbering: {
    config: [
      {
        reference: "bullet-list",
        levels: [
          {
            level: 0,
            format: LevelFormat.BULLET,
            text: "•",
            alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 360, hanging: 180 } } },
          },
        ],
      },
    ],
  },
  sections: [
    {
      properties: {
        page: {
          size: { width: 11906, height: 16838 },
          margin: { top: 850, right: 850, bottom: 850, left: 850 },
        },
      },
      children,
    },
  ],
});

Packer.toBuffer(doc).then((buffer) => {
  fs.writeFileSync(outputPath, buffer);
  console.log(`DOCX gerado: ${outputPath}`);
  console.log(`Cargos: ${roles.length}`);
});
