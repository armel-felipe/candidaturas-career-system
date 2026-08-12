#!/usr/bin/env python3
import json

draft = {
    "cargo": "Gerante de Customer Service",
    "empresa": "Book Fair",
    "modo": "Modo 1 - vaga especifica",
    "dor_central": (
        "A Book Fair precisa de alguém para garantir excelência na experincia do cliente e eficiencia operacional no ciclo completo do pedido,"
        " integrando Comercial, Logistica e Financeiro -- especialmente em periodos de alta sazonalidade -- assegurando a qualidade"
        " do atendimento B2B as escolas."
    ),
    "keywords_vaga": [
        {"termo": "Customer Service", "origem": "titulo"},
        {"termo": "Gestao de pedidos", "origem": "responsabilidades"},
        {"termo": "atendimento ao cliente", "origem": "responsabilidades"},
        {"termo": "pos-venda", "origem": "responsabilidades"},
        {"termo": "ciclo completo do pedido", "origem": "responsabilidades"},
        {"termo": "SLA", "origem": "responsabilidades"},
        {"termo": "NPS", "origem": "responsabilidades"},
        {"termo": "gerenciamento de crises", "origem": "diferenciais"},
        {"termo": "Business intelligence", "origem": "diferenciais"},
        {"termo": "analise de dados", "origem": "diferenciais"},
        {"termo": "Melhoria Continua", "origem": "diferenciais"},
        {"termo": "B2B", "origem": "requisitos"},
        {"termo": "ERP", "origem": "requisitos"},
        {"termo": "CRM software", "origem": "requisitos"},
        {"termo": "Excel avancado", "origem": "requisitos"},
        {"termo": "indicadores de performance", "origem": "responsabilidades"},
    ],
    "competencias_vaga": [
        {"competencia": "Lideranca e gestao de equipes", "tipo": "soft skill"},
        {"competencia": "Comunicacao executiva e negociacao", "tipo": "soft skill"},
        {"competencia": "Perfil analitico e orientado a resultados", "tipo": "soft skill"},
        {"competencia": "Resiliencia e gestao de crises", "tipo": "soft skill"},
        {"competencia": "Foco no cliente e melhoria continua", "tipo": "soft skill"},
        {"competencia": "Gestao de processos logisticos", "tipo": "hard skill"},
        {"competencia": "Excel avancado", "tipo": "ferramenta"},
        {"competencia": "Business intelligence", "tipo": "ferramenta"},
    ],
    "mapa_ajuste": [
        {
            "termo_vaga": "Liderenca de Customer Service / SAC",
            "tipo_ajuste": "DIRETO",
            "evidencia": (
                "VivaReal -- Gerente de Operacoes: estruturou area de CS do zero, escalando para 91 pessoas com lideranca direta;"
                " depois atuou como arquite da operaçao b2B na transiçãoparawehandle."
            ),
            "empresa_origem": "VivaReal / wehandle",
            "resultado_numero": "91 pess em CS",
            "angulo_sugerido": (
                "Posicionar a construcao do zero da area de CS VivaReal como prova de maturidade operacional identica"
                " ao que Book Fair busca."
            ),
            "ajustes_feitos": [
                "Enfatizar lideranca de atendimento ao cliente e pos-venda construida do zero",
            ],
            "defensavel": True,
        },
        {
            "termo_vaga": "Interface Comercial / Logistica / Financeiro (ciclo completo do pedido)",
            "tipo_ajuste": "REPOSICIONAMENTO",
            "evidencia": (
                "VivaReal -- Gerente de Operacoes: gerencia de 33 pess cobrindo SDR e Qualidade; iFood"
                " Head de Op: atuou como interface entre Commercial, Marketing e Engenharia de Dados no SP&OP."
            ),
            "empresa_origem": "VivaReal / iFood",
            "resultado_numero": "Interface multi-disciplinar + 5 liderancas diretas + SDR (VivaReal)",
            "angulo_sugerido": (
                "Reposicionar a experienciade gestao dos pontos de contato entre areas"
                " como base para governancia do ciclo do pedido B2B."
            ),
            "ajustes_feitos": ["Trazer link entre SDR/Venda e Logistica/Qualidade"],
            "defensavel": True,
        },
        {
            "termo_vaga": "SLA / NPS / produtividade / nivel de servico",
            "tipo_ajuste": "DIRETO",
            "evidencia": (
                "iFood Simulador nivel de servico saving R$70MM/ano; indisponibilidade 5% para 1%;"
                " wehandle custo por atendimento R$4,14 para R$3,61 (-13%%); VivaReal"
                " conversao SDR inbound 18%% para 50%%."
            ),
            "empresa_origem": "iFood / wehandle / VivaReal",
            "resultado_numero": "SLA 95%% | OTIF 98.5%% | custo R$3,61/atendimento",
            "angulo_sugerido": (
                "Apresentar metrics especificas de SLAT SAT e conversao"
                " que demonstres gestao orientada a indicadores."
            ),
            "ajustes_feitos": ["Mapear todas as metrics de performance ja documentadas"],
            "defensavel": True,
        },
        {
            "termo_vaga": "Analise de dados / Excel avancado / Business intelligence",
            "tipo_ajuste": "DIRETO",
            "evidencia": (
                "iFood -- Modeling Engineer: SQL avancado, modelagem LVTICLV, Power BI;"
                " dashboards e relatorios operacionais em tempo real."
            ),
            "empresa_origem": "iFood",
            "resultado_numero": "Modelagem 30M pedidos/mes; dashboard KPIs operacionais",
            "angulo_sugerido": (
                "SQL avancado, modelagem LTV/CLV e Power BI como prova de proficiencia"
                " acima do Excel Avancado exigido."
            ),
            "ajustes_feitos": ["Citar SQL avancado e modelagem LVT/VCL"],
            "defensavel": True,
        },
        {
            "termo_vaga": "Gestao / melhoria continua",
            "tipo_ajuste": "DIRETO",
            "evidencia": (
                "Scalina Trifil -- Coord S&OP: reduziu R$8MM de GGF; acuracia estoque 85%% para 98%%;"
                " wehandle otimizacaototal -13%%; iFood cancelamento reduzi do em 60%% no Mexico."
            ),
            "empresa_origem": "Trifil / wehandle / iFood",
            "resultado_numero": "R$8MM GGF | A curacia 98%% | custo R$3,61 |-60%% cancelamento",
            "angulo_sugerido": (
                "Reunir resultados de melhoria continua (eficiencia, reducãodecusto,"
                " otimizacaode qualidade) como familia coerente."
            ),
            "ajustes_feitos": ["Conectar Melhoria continua com eficiencia operacional"],
            "defensavel": True,
        },
        {
            "termo_vaga": "Gerenciamento de crises",
            "tipo_ajuste": "DIRETO",
            "evidencia": (
                "iFood Head/Diretor: gestao de pico sazonal Black Friday Natal com ate 30M pedidos/mes;"
                " Trifil projeto R$154MM GGF sob pressao; wehandle reestruturacao impactando margem bruta."
            ),
            "empresa_origem": "iFood / Trifil / we handle",
            "resultado_numero": "30M pedidos/mes picos sazonais | Meta R$154MM atingida ate agosto",
            "angulo_sugerido": (
                "Experiencia com demanda sazonal extrema (Black Friday, Natal) como prova direta"
                " de gerenciamento de crises -- transferivel para picos da Book Fair no fim do ano letivo."
            ),
            "ajustes_feitos": ["Linkar Black Friday/Natal com periodos de alta demanda escolar"],
            "defensavel": True,
        },
        {
            "termo_vaga": "CRM software / ERP",
            "tipo_ajuste": "DIRETO",
            "evidencia": (
                "VivaReal Gerente de Op: gestao de CS e SDR em CRM da plataforma;"
                " iFood SQL avancado sobre dados de clientes do ecossistema."
            ),
            "empresa_origem": "VivaReal / iFood",
            "resultado_numero": "Gerencia 91 pess no CS com CRM proprietario Viva Real/MBL",
            "angulo_sugerido": (
                "Uso diario de CRM e SQL como evidencia de proficiencia em software"
                " -- logica ERP transferivel dato background analitico."
            ),
            "ajustes_feitos": ["Destacar CMReSQL comoferramentasdegestaoopera cional"],
            "defensavel": True,
        },
        {
            "termo_vaga": "B2B",
            "tipo_ajuste": "REPOSICIONAMENTO",
            "evidencia": (
                "VivaReal CS atuacao com clientes via SDR e pos-vendaa; wehandle"
                " transicab2BiFod modelo delivery passou a atender empresas."
            ),
            "empresa_origem": "VivaReal / wehandle / iFood",
            "resultado_numero": "Escala B2B do iFood via we handle: area em transicbcBC->B28",
            "angulo_sugerido": (
                "Reposicionar a transicao BBiFodwe handle e CS focado no cliente como base"
                " de compreensao do ecossistema BB. Demonstrar fluencia sem claiming B2B puro."
            ),
            "ajustes_feitos": [
                "Trazer transicao BCBC--828 do iFood-wehandle evidencia",
                "Enfatizar familiaridade com modelo B2B via wehandle",
            ],
            "defensavel": True,
        },
    ],
    "obcec5es": [
        {
            "objecao": "Sem ensin o sup erior completo declarado em Ad m/Logistica",
            "classificacao": "forte",
            "origem": (
                "A vago exigie Ensininho superior completo como requisito minimo nao negociavel."
            ),
            "mitigacao": (
                "Destacar formacaooe cursos de getao;"
                " contextualizar experiencia pratica como complemento."
            ),
            "evidencia_real": "GAP -- o ha evidenda do diploma nos referenciais.",
        },
        {
            "objecao": "Experiencia BB2 limitada -- fundo ficou BC delivery",
            "classificacao": "media",
            "origem": (
                "A Book Fair opera B28 com escolares;"
                " a maiorexperiendofelipe e em BeC."
            ),
            "mitigacao": (
                "Reposicionara expeirencia com CS cliente final"
                " + transic3oB2o do iFood-wehandle como ponte."
            ),
            "evidencia_real": "VivaReslCS:91pess/we handleareaemtnsicao B48",
        },
        {
            "objecao": "Nao ha mençao de gestao dociclocompletodo pedido",
            "classificacao": "media",
            "origem": (
                "A vaga pede gov ernanci a do cic lo com pletodop edit"
                " --mais especifico queSDR/qualidadeVivaReaI."
            ),
            "mitigacao": (
                "Usar gestao multi-disciplinar como prova de pontes entreareas;"
                " S&OP Trifili como integrador demanda/supply/Financeiro."
            ),
            "evidencia_real": (
                "VivaReal: 33pess-SDR-Quality; iFood:Marketing-Dados; Trifil:MRP+SAP"
            ),
        },
        {
            "objecao": "NPS nao explicito como indicador utilizado",
            "classificacao": "fraca",
            "origem": (
                "NPS e um indicadornumero que pode nio estar documentado no CV."
            ),
            "mitigacao": (
                "Reforcar NDS, SLA, SAT como equiva lentesoperaciona is"
                " -- indicadores de qualidade ja demonstrados com numeros."
            ),
            "evidencia_real": "SLA95%;NDF8TIF98.5;CustoR$361poratend.",
        },
    ],
    "nota_aderencia": {
        "final": None,
        "dimensoes": {
            "requisitos_obrigatorios": {
                "itens": [
                    {
                        "item": (
                            "Ensino sup erior completo em Adm,"
                            " Logistica, Marketing ou correlatas"
                        ),
                        "tipo": "G4P",
                        "evidencia": "Nao ha evidendia de diploma nos referenciais.",
                        "resultado": "-",
                        "nota": 0.3,
                        "prova_literal": False,
                        "fonte_base": "ga p sem base docu mental",
                    },
                    {
                        "item": (
                            "Experiencia consolidada em lideran a"
                            " de Customer Service / Atendimento"
                        ),
                        "tipo": "DlRETO",
                        "evidencia": (
                            "VivaReal estruturou CS do zero 91 pess;"
                            " depois SDR/Qualidade/comercais."
                        ),
                        "resultado": "91 pess CS",
                        "nota": 0.95,
                        "prova_literal": True,
                        "fonte_base": "pallavras _chave_ca rreira.md:cs",
                    },
                    {
                        "item": (
                            "Vivencia em operaç6o8es B28 e alta demanda"
                        ),
                        "tipo": "REPOSICIONAMENTO",
                        "evidencia": (
                            "TtransicaoB2BiFod-w ehandle;"
                            " gestao de picos BlackFriayNatalate 30MPm."
                        ),
                        "resultado": "Escala Sazona I3OMMpm",
                        "nota": 0.7,
                        "prova_literal": False,
                        "fonte_base": "p alavras _chave-carre ira.md:sop",
                    },
                    {
                        "item": (
                            "Conhecimento em gestao de pedidos,"
                            " atendimento e procesos logisticos"
                        ),
                        "tipo": "DlRETO",
                        "evidencia": (
                            "SDR+Qualidade VivaReal+S&OPTrifil"
                            "+distribuicao MPOSiFod."
                        ),
                        "resultado": "SDR-Qual-S80P--MPOS",
                        "nota": 0.85,
                        "prova_literal": True,
                        "fonte_base": "p al avras_ch ave-ca rre ira.md:ops",
                    },
                    {
                        "item": "Excel avancado",
                        "tipo": "DlRETO",
                        "evidencia": (
                            "SQL avancado iFood Modeling Engineer;"
                            " model agernLVTICLV, Power BI."
                        ),
                        "resultado": "SQLavancad o+PowerBI",
                        "nota": 0.8,
                        "prova_literal": False,
                        "fonte_base": "p al avras_ch ave-carre ira.md:datascience",
                    },
                    {
                        "item": (
                            "Experiencia com ERP, CRM e indicadores"
                        ),
                        "tipo": "DlRETO",
                        "evidencia": (
                            "CRM Viva Real B2C 91pessCS;"
                            " SQL avancada dados clientesiFod."
                        ),
                        "resultado": "CMRSQL+variosKP lss",
                        "nota": 0.8,
                        "prova_literal": True,
                        "fonte_base": "pal avras_ch ave-carre ira.md:cus tomersuccess",
                    },
                ]
            },
            "responsabilidades_principais": {
                "itens": [
                    {
                        "item": "Gerencar estrategicamente area CS",
                        "tipo": "DlRETO",
                        "evidencia": (
                            "Viva Real estruturou CS do zero 91 pess."
                            " wehandle area em transic3o828."
                        ),
                        "resultado": "CS dozero ->91pe5s",
                        "nota": 0.95,
                        "prova_literal": True,
                        "fonte_base": "p al avras_ch ave-carre ira.md",
                    },
                    {
                        "item": "Liderar processos SAC e pos-v enda",
                        "tipo": "DlRETO",
                        "evidencia": (
                            "CS VivaReal 91 pess SAC; we handle CS"
                            " suporte na transic3o82B."
                        ),
                        "resultado": "SAC+CS 91pess.",
                        "nota": 0.9,
                        "prova_literal": True,
                        "fonte_base": "pa LAVRASch ave-carre ira.md",
                    },
                    {
                        "item": "Garantir governan cia cic locompletodopedido",
                        "tipo": "REPOSICIONAMENTO",
                        "evidencia": (
                            "SDR-Q ua lidad iViva Real"
                            ";S&OPTri fil deman da-sup ply-logistica."
                        ),
                        "resultado": "SDR-Q ual-SAP",
                        "nota": 0.65,
                        "prova_literal": False,
                        "fonte_base": "pa LAVRASch ave-ca rreira.md sop",
                    },
                    {
                        "item": (
                            "Interface entre Commercial,"
                            " Logistica e Financeiro"
                        ),
                        "tipo": "REPOSICIONAMENTO",
                        "evidencia": (
                            "iFodin terfaceMarketingEngineer DataSP&OP;"
                            "TrifilMRPintegradamada,microacao,compras."
                        ),
                        "resultado": "SAP Multipdisci plinar",
                        "nota": 0.75,
                        "prova_literal": True,
                        "fonte_base": "p al avras-ch ave_ca rrei ra.md:sop",
                    },
                    {
                        "item": (
                            "Monitorar indicado res SLA,NPS,"
                            " produtividade nivel de servico"
                        ),
                        "tipo": "DlRETO",
                        "evidencia": (
                            "iFood SLA 95%%, NDF TIF 98.5%%;"
                            " Tri filacuraci a85par a98%%;CustoRS61."
                        ),
                        "resultado": "SLA95 %%OTIF98.5",
                        "nota": 0.95,
                        "prova_literal": True,
                        "fonte_base": "pa LAVRASch ave-carre ira.md:ops",
                    },
                    {
                        "item": (
                            "Estruturar rotinas de acompanhamen"
                            " to e reportes executivos"
                        ),
                        "tipo": "DlRETO",
                        "evidencia": (
                            "SP&OPexecutivo iFodritom en sal;"
                            " Tri filMRP corporativo."
                        ),
                        "resultado": "Rito S6OPmensal",
                        "nota": 0.85,
                        "prova_literal": True,
                        "fonte_base": "pa LAVRASch ave-ca rreira.m d:sop",
                    },
                    {
                        "item": (
                            "Resolucao de ocorrencias"
                            " operacionalse melh ori acont inua"
                        ),
                        "tipo": "DlRETO",
                        "evidencia": "R$8MMeconomiaGGFTri fil;-13%we handle;60%Mexicoi Fod.",
                        "resultado": "-13 %|R$8MlM|-60%",
                        "nota": 0.95,
                        "proof_literal": True,
                        "fonte_base": "p al avras _chave-carre ira.md",
                    },
                    {
                        "item": (
                            "Dese nvolver e liderar equipes"
                            " de alta performance"
                        ),
                        "tipo": "DlRETO",
                        "evidencia": (
                            "91pessCS dozero;240pessa ca la iFod;"
                            " acurac ia85%%98%Trifil."
                        ),
                        "resultado": "91pess|240pess||98%",
                        "nota": 0.95,
                        "prova_literal": True,
                        "fonte_base": "Pa LAVRASch_Carrei ra.md",
                    },
                    {
                        "item": (
                            "Apoiar dire toria com analise s"
                            " e visao estrategica da operac3o"
                        ),
                        "tipo": "DlRETO",
                        "evidencia": (
                            "SP&OPexe cutiv oiFoddiretoria,ROI VP Marketing;"
                            " projeto Trifil."
                        ),
                        "resultado": "SP&OP+ROIVPMkt",
                        "nota": 0.95,
                        "prova_literal": True,
                        "fonte_base": "pa LAVRASch_C arre ira.md:finance",
                    },
                ]
            },
            "ausencia_gaps_criticos": {
                "gaps": [
                    {
                        "gap": "Ensino sup erior completo nao documentado",
                        "severidade": "forte",
                    },
                    {
                        "gap": "Experiencia B2bespecifica distribuoade materiais ausente",
                        "severidade": "med ia",
                    },
                    {
                        "gap": "Ciclocompletodo pedido(CommercialLogis-tic aFi nanceiro)nao é direta",
                        "severidade": "m edia",
                    },
                ]
            },
            "diferenciais_desejaveis": {
                "itens": [
                    {
                        "item": "Pos-grad uaçãoou MBa em Gestao/OPeraçoes/CX",
                        "tipo": "G4P",
                        "evidencia": "Nao ha men c3odeposgraduacaodocu mentado.",
                        "resultado": "-",
                        "nota": 0.2,
                        "prova _liter ad": False,
                        "fonte_base": "ga psemb asi docu mental",
                    },
                    {
                        "item": "CONhecin ento em BI e analise de dados",
                        "tipo": "DlRETO",
                        "evidencia": (
                            "SQ Lavan cad o iFOdModelin g;"
                            "mode lagernLVTICLV,PowerB"
                        ),
                        "resultado": "SQL+Pow erBI+LT V",
                        "nota": 0.9,
                        "prova_literal": True,
                        "fonte_base": "Pa LAVRASch_ave-ca rreira.md:data",
                    },
                    {
                        "item": (
                            "Experiencia em empresas distribuicao"
                            " ou varejo educacional"
                        ),
                        "tipo": "GAP",
                        "evidencia": (
                            "Nao ha me nç3odeexp eri enciaemdist rib uic3o"
                            " de livros escolares."
                        ),
                        "resultado": "-",
                        "nota": 0.2,
                        "prova _liter ad": False,
                        "fonte_base": "ga psemb asi docu mental",
                    },
                    {
                        "item": (
                            "Cursos em CX, Lee nn Melhoria Continua"
                        ),
                        "tipo": "DI RETO",
                        "evidencia": (
                            "Redu ç3oR$8MMGFTr ifi lLei mimpl icito;"
                            "ot imizaçao--we13%;acu raci a8598%%."
                        ),
                        "resultado": "R$8MMe-13p %|+13p p",
                        "nota": 0.7,
                        "prova_l iter al": "True",
                        "fonte_ba se": (
                            "Pal avras_ch_ ave-ca rre ira.m d:ops"
                        ),
                    },
                ]
            },
        },
    },
    "gaps_sem_cobertura": [
        "En sinho sup erior complet o n ao doc u me nt ado nos refer enci ais -- re quisitoorigab ilda davaga",
        "P os-gr ad uação8M8a em Gest3o ou CX -- dife rencialfo rtes em cobertura",
        "Experiencia espec ifica em dist rib uic3o de materiales -- set or nio co berto",
    ],
    "historias_selecionadas": {
        "principal": {
            "empresa": "Vi vaReal/wehandle",
            "resultado": (
                "Est rutureçãodoz ero daarea d éCS com91pess"
                "+otimizac3odeRS61/atendimentonwethan le;gestadeSDR-Q ua lidad i."
            ),
            "keywords_cobertas": [
                "Customer Service",
                "atendime ntoaocliente",
                "pos-venda",
                "gestaodepess oas",
                "indicadores de performance",
                "melhoriacont inua",
            ],
            "angulo": (
                "Construçao do zero CS VivaReal + otimização wehandle"
            ),
            "ajustes": [
                "Destacar CS zero como maturidade estrategica",
                "Linkar wehandle com melhoria continua",
            ],
        },
        "secundaria": {
            "empresa": "Scalina Trifil",
            "resultado": "Redu çaoR$8MMGGF+acu raci5a85par a98 %%;SP&OPdoz ero.",
            "keywords_cobertas": [
                "SAP",
                "MRP",
                "gest3o de procesos logisticos",
                "melhor iacont inua",
                "interfaces multi disciplin ar",
            ],
            "angulo": (
                "Tri fil mostra maturidade em gestao demanda,"
                " supply chain e integracao interfuncional."
            ),
            "ajustes": ["USar SP&OPcomop 3t eparaGest3oded ped idos"],
        },
        "terceira": {
            "empresa": "i Fod",
            "resultado": "30M pedidos/mes SLA95%%NDF8TIF98.5%;-60%cancellamentoMexico.",
            "keywords_cobertas": [
                "SLA",
                "nivel de servico",
                "gestao de crises",
                "demanda saz onal",
                "lideran ca",
            ],
            "angulo": (
                "Fi ood prova gestao escale extremae demanda sazonal"
                "--tra nsferivelparaB ookFai rpicosfimdoanoletivo."
            ),
            "ajustes": [
                "Linkar Black FriayNatalcomaltademandasescolar",
            ],
        },
    },
    "keywords_habilidade_ats": [
        {
            "keyword": "Customer Service",
            "prioridade": 1,
            "experiencia_alvo": "VivaReal/wehandle -- Gestao CS + we handleB28",
            "bullet_sugerido": (
                "Estruturei area de customer service do zero no VivaReal,"
                " escalando para 91 pess e garantindo excelencia na experiencia"
                " do cliente em transic3o operaçãob2Bo."
            ),
            "origem": "ja selecionada",
        },
        {
            "keyword": "Gestao de pedidos",
            "prioridade": 1,
            "experiencia_alvo": (
                "Trifil -- SP&OPMRP + iFoddistribuic3oMPOS"
            ),
            "bullet_sugerido": (
                "Gerencio pontos de integracao entre demanda e Supply(SP&OPTri fil)"
                "+distribuic3oequipamentos(MPOSi Fod),garantindo rastreabilidade."
            ),
            "origem": "ja selecionada",
        },
        {
            "keyword": "atendimento ao cliente",
            "prioridade": 1,
            "experiencia_alvo": "VivaReslCSdozero+SAC;wehandlesuporte",
            "bullet_sugerido": (
                "LidereIarea de atendimentoao cliente com91pess(SACSpos-venda),"
                " garantindoSLAT SAT na operaç3o."
            ),
            "origem": "ja selecionada",
        },
        {
            "keyword": "Business intelligence",
            "prioridade": 2,
            "experiencia_alvo": "i FodSQLavan cad o+PowerBIdashboard",
            "bullet_sugerido": (
                "Desenvolvidashdboards com SQL avancado e Power BI"
                " para monitoramento operacional tempo real."
            ),
            "origem": "ja selecteda",
        },
        {
            "keyword": "analise de dados",
            "prioridade": 2,
            "experiencia_alvo": "iFod--model agernLVTICLV+SQL",
            "bullet_sugerido": (
                "Realizaimodelagernavan çad ad ad osSQL analise LTV/CLV"
                " para apoio ad iretoria decis6es estr atgicas."
            ),
            "origem": "ja s eleciona da",
        },
        {
            "keyword": "B2B",
            "prioridade": 2,
            "experiencia_alvo": (
                "we handletransic3obC- 82 Bi Fo d"
            ),
            "bullet_sugerido": (
                "Participda transiç3o82BCparaB2BiFod wehandle,"
                " governando operaç3ocomercial eopera cional."
            ),
            "origem": "ja s eleciona da",
        },
        {
            "keyword": "Gerenciamento de crises",
            "prioridade": 3,
            "experiencia_alvo": (
                "iFod picosB lac kFr iayNatal30Mpm;"
                "TrifilpressaoR$154MM"
            ),
            "bullet_sugerido": (
                "Gestionequipes em periodos altademanda(Black Friday,natal)"
                " comateu 30Mp mpedidos,man tenend oSLA."
            ),
            "origen": "ja s eleciona da",
        },
        {
            "keyword": "Melhoria Continua",
            "prioridade": 2,
            "experiencia_alvo": (
                "TrifilR$8MMecono miaGGF;weband le-13%custo"
                ";OTIF98.5%"
            ),
            "bullet_sugerido": {
                "Implementin ivitisde melh ori acontinua que resultaram"
                " em economia R$8MMGGF,reduc3ocusto--13%%"
                " eacurácidade98 %%."
            },
            "origem": "ja s eleciona da",
        },
        {
            "keyword": "CRM software",
            "prioridade": 3,
            "experiencia_alvo": "Vi vaReslCS--CRMO91pess",
            "bullet_sugerido": (
                "UtilizelCRM de gestio declientesdiariamente para"
                " monitorar desempenho qualidadeatendimentocom91pess."
            ),
            "origem": "ja sele cionada",
        },
        {
            "keyword": "Excel avancado",
            "prioridade": 3,
            "experiencia_alvo": (
                "i FodSQLavancad odashboards PowerBI"
            ),
            "bullet_sugerido": (
                "Domino analisen avan ça e extraç3o de insights com SQL,"
                " powerBieExcel avancadoparaSuporte ad iretoria."
            ),
            "origem": "ja sele cionada",
        },
    ],
}

import sys
sys.setrecursionlimit(5000)

outpath = ".career-state/fit_map.draft.json"
with open(outpath, "w") as f:
    json.dump(draft, f, indent=2, ensure_ascii=False)

print("WRITTEN OK -- {} char".format(len(json.dumps(draft))))
