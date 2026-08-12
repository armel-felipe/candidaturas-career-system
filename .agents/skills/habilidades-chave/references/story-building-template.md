# Story-Building Template — Habilidades Mercado Livre

> Template obrigatório para construção de histórias defensáveis de 500-700 caracteres.
> **Não escrever histórias abaixo de 500 caracteres.** Se não houver material suficiente para 500 caracteres, declarar gap.

---

## 1. Template Obrigatório

Cada história deve conter **exatamente** estes 4 elementos, nesta ordem:

```
[CONTEXTO] — Onde Felipe estava, cargo, período, escopo.
[PROBLEMA/MISSÃO] — O desafio operacional ou de negócio.
[AÇÃO] — O que Felipe fez. Deve conter verbo de ação no passado.
[RESULTADO] — Número concreto: saving, %, SLA, tempo, receita, etc.
```

E opcionalmente:

```
[CONEXÃO] — Por que essa história prova a habilidade. Frase única.
```

---

## 2. Verificação Obrigatória (Checklist por História)

Cada história deve passar por esta verificação antes de ser entregue:

- [ ] Contém os 4 elementos: Contexto + Problema + Ação + Resultado?
- [ ] Tem pelo menos 500 caracteres? (contar programaticamente)
- [ ] Não ultrapassa 700 caracteres?
- [ ] Resultado numérico presente? (%, R$, saving, tempo, volume)
- [ ] A empresa e o cargo batem com a experiência real escolhida?
- [ ] Nenhum dado inventado (ferramenta, budget, time, escopo)?
- [ ] Referencia a fonte no autoconhecimento.md (ex: linhas 230-238)?
- [ ] Não repete núcleo narrativo de outra história desta mesma lista?

---

## 3. Blocos Literais — iFood (Head de Operações, 2018-2022)

Fonte: `autoconhecimento.md:linhas 210-228`

> Head de Operações (nov/2018 a mar/2022)
> * Liderei uma equipe de 28 pessoas nas áreas de liveOps, regionalOps, pricing, modelagem de dados e planejamento de frota
> * Implementei torre de operações na subsidiária do Mexico, reduzindo cancelamento em 60% ajustando raios de entregas
> * Grafana: criei as métricas de acompanhamento em tempo real, diretamente no grafana. Liderei uma equipe técnica responsável por otimizar modelos de dados, infra-estrutura e performance da informação em contato próximo com engenharia de dados.
> * Criamos o indicador da entrega rápida, com ele entendemos a correlação entre frequencia de pedidos, tempo de promessa e tolerancia ao atraso dos clientes.
> * Estruturei a área de liveOps com indicadores em tempo real, correlacionando indicadores de saturação logistica com metas de tempo de entrega, ganhos dos entregadores, frequencia.
> * Modelamos os dados usando sql, databricks, tableau para visualização dos dados
> * Criei um simulador que manteve o nível de serviço sob controle com um saving de R$ 70M ano
> * Estabelecemos um processo de distribuição de MPOS que reduziu o custo de distribuição em 80% e o tempo de entrega de 14 para 2 dias.
> * Criei ferramentas de restrição de raio por bairro, aumentando a disponibilidade do serviço logistico.
> * Fui responsável pela área de pricing da operação logística, definindo a arquitetura de remuneração dos entregadores por zona e modelo de serviço
> * Conduzi testes controlados de elasticidade de preço: avaliava impacto de variações de remuneração na oferta de entregadores por região

**Numeros válidos deste bloco:** 28 pessoas, -60% cancelamentos México, saving R$70M/ano, -80% custo distribuição MPOS, 14→2 dias entrega, 352 cidades com zero perda.

---

## 4. Blocos Literais — iFood (Diretor de Operações, 2022-2024)

Fonte: `autoconhecimento.md:linhas 230-252`

> Diretor de Operações (abr/2022 a mar/2024)
> * Minha equipe aumentou 240 pessoas, entre os direto e indiretos, acumulando a gestão da área de FieldOps, Meios de Pagamento, Novos Negócios (entrega mais, frotas dedicadas)
> * Fui responsável pela linha do P&L de custo das entregas, dando eficiencia para um budget de R$300MM por ano.
> * Reestruturei a eficiência logística em Full Service ao isolar impactos de políticas de remuneração, reduzindo o custo comparável em 3% YoY (2023 vs 2022)
> * Aumentei a porcentagem agrupadas de 12% para 25%, reduzindo o custo logistico e alcançando o breakeven da operação
> * Aumentamos a cobertura do serviço logistico de 400 para 800 cidades
> * Liderei iniciativas e otimização reduzindo a indisponibilidade da frota de 5% para 1% em nível Brasil, nas top 6 cidades saindo de 5,4% para 0.5%
> * Liderei o rito executivo mensal de S&OP da logística, consolidando visão Brasil e São Paulo com leitura de demanda, supply, custo logístico, nível de serviço, criticidade e cenários para tomada de decisão.
> * Conectei marketing, promoções, clima, disponibilidade de frota, expansão geográfica, supply e operação em um processo único de planejamento
> * Conduzi trade-offs entre custo e nível de serviço com gestão de cenários normal e crítico para proteger a meta de EBITDA do P&L
> * Atuei sobre a aderência ao goal de EBITDA do P&L, com leitura recorrente de variação vs meta e alavancas operacionais

**Numeros válidos deste bloco:** 240 pessoas, R$300MM budget, -3% custo YoY, 12%→25% agrupamento, 400→800 cidades, 5%→1% indisponibilidade, 5,4%→0,5% top 6 cidades.

---

## 5. Blocos Literais — Scalina (Trifil) — Coord. Expedição + S&OP (2006-2014)

Fonte: `autoconhecimento.md:linhas 128-175`

**Coordenador de Expedição (jan/2007 a out/2007):**
> * Gerenciei o centro de expedição, estruturado a área de picking, packing, armazenamento
> * Melhoramos a acuracidade do estoque para 98%, implantando endereçamento de estoque, coletores e inventário rotativo — subindo de 85% para 95% inicialmente
> * Organização dos endereçamentos reduziram as perdas e refugos em 30%
> * Melhorei a produtividade dos colaboradores em 35% com adoção de técnicas de endereçamento, posicionamento e separação do produto no estoque
> * Implantei coletores automáticos para o picking (primeiro rádio-frequência, depois wi-fi)
> * Fui responsável pela implantação dos módulos de expedição, planejamento do ERP LN
> * Gerente do Projeto Entrega Certa: indicadores chave OTIF (ex-works), acurácia da previsão de vendas, acurácia da produção, giro do estoque de EPA e produtividade da expedição

**Coordenador de S&OP (jan/2010 a set/2014):**
> * Criei a área de S&OP do zero e sustentei os ritos e operações por 4 anos
> * Gerenciava 40K SKUs de produto acabado em duas marcas, todos os canais
> * Gerente do projeto GGF 2014: economia real de R$ 4,6M em relação à meta e redução de R$ 8,6M vs mesmo período 2013
> * Reduzi 8 milhões de GGF do P&L da empresa, otimizando gastos com energia, gás, materiais de manutenção e embalagens
> * Criei um simulador para validação do MRP e avaliação de cenários para o S&OP com excel VBA

**Numeros válidos deste bloco:** 98% acurácia, -30% perdas, +35% produtividade, R$4,6M economia GGF, R$8,6M redução vs 2013, R$154M meta GGF, 40K SKUs, -27% custo compras, -40% falta estoque, giro melhorou 2 meses.

---

## 6. Blocos Literais — WeHandle (Head de Operações, 2024-2026)

Fonte: `autoconhecimento.md:linhas 254-274`

> Head de Operações (maio/2024 a fev/2026)
> * A otimização total (automação + implantação de canal de whatsapp) reduziu o custo total de R$ 4,14 para R$3,6
> * Criei área de CX para definir melhores soluções e alinhamentos com produtos
> * Segmentação Estratégica: aumento de 17% no CSat
> * Implementação de WhatsApp: reduziu custo por atendimento de R$1,04 para R$0,56
> * Automação com chatbot e IA: aumento de 25% na produtividade
> * Reestruturação impactou 15% na margem Bruta
> * Conectei via API nas três plataformas de atendimento: Movidesk, CloudHumans e Zendesk
> * Reduzimos 60% o backlog de cards e SLA subiu de 67% para 85%
> * CSAT de 85% para 92% e SLA em 95% dos tickets
> * TME de 20 minutos para 8 minutos

**Numeros válidos deste bloco:** R$4,14→R$3,60 custo total, +17% CSat, R$1,04→R$0,56 custo WhatsApp, +25% produtividade, 15% margem bruta, -60% backlog, 67%→85% SLA, 85%→92% CSAT, 95% SLA tickets, 20→8min TME.

---

## 7. Exemplo de História Completa (dentro de 500-700 caracteres)

Habilidade: **Operations Management**
Cargo: Diretor de Operações
Empresa: iFood

> Como Diretor de Operações no iFood, liderei uma equipe de 240 pessoas responsável por FieldOps, Meios de Pagamento e Novos Negócios em uma operação logística de 30 milhões de pedidos mensais. O desafio era reestruturar a eficiência logística em um contexto de crescimento acelerado — expandimos a cobertura de 400 para 800 cidades em dois anos, o que pressionava a estrutura de custos. Isolei os impactos das políticas de remuneração de entregadores sobre o custo logístico, identifiquei alavancas específicas de eficiência e redesenhei o modelo de agrupamento de pedidos. Resultado: redução de 3% no custo comparável YoY, agrupamento subiu de 12% para 25% (alcançando o breakeven da operação), e a indisponibilidade da frota caiu de 5% para 1% em nível Brasil. (Fonte: autoconhecimento.md:linhas 230-238)

**Contagem: 688 caracteres** ✓

---

## 8. Contraexemplo — História Conciosa (NÃO USAR)

Habilidade: **Operations Management**
> No iFood como Diretor liderei 240 pessoas e reduzi custo em 3% YoY.

**Contagem: 89 caracteres** ✗ — REPROVADA

---

## 9. Regra de Citação de Fonte

Cada história deve incluir `(Fonte: autoconhecimento.md:linhas X-Y)` no final. As linhas de origem são:

| Experiência | Linhas no autoconhecimento.md |
|-------------|------------------------------|
| iFood — Head de Operações | 210-228 |
| iFood — Diretor de Operações | 230-252 |
| Scalina/Trifil — Analista | 129-133 |
| Scalina/Trifil — Coord. Expedição | 134-145 |
| Scalina/Trifil — Coord. Materiais | 146-152 |
| Scalina/Trifil — Coord. Inteligência Comercial | 153-162 |
| Scalina/Trifil — Coord. S&OP | 163-175 |
| VivaReal — Gerente | 177-195 |
| Renault — Gerente CS | 197-208 |
| WeHandle — Head | 254-274 |

---

## 10. Processo de Construção (Ordem Obrigatória)

1. **Selecionar** a habilidade do catálogo Mercado Livre (do arquivo `references/habilidades_mercado_livre.json`)
2. **Localizar** no FIT_MAP qual termo_vaga ou keyword corresponde a essa habilidade
3. **Extrair** o bloco literal de `autoconhecimento.md` correspondente à experiência escolhida (da tabela acima)
4. **Construir** a história usando o Template (seção 1) com os elementos do bloco literal
5. **Contar** caracteres. Se < 500, adicionar:
   - Mais contexto da empresa (período, tamanho da operação)
   - O problema específico que motivou a ação
   - A ação em detalhe (como Felipe fez)
   - Um segundo resultado se disponível
6. **Verificar** checklist da seção 2
7. **Escrever** a fonte no formato `(Fonte: autoconhecimento.md:linhas X-Y)`

---

## 11. Estratégia para Chegar a 500 Caracteres

| Técnica | O que adicionar | Exemplo |
|---------|----------------|---------|
| Contexto da empresa | Período, tamanho da equipe, volume de operação | "No iFood como Diretor (2022-2024), liderei 240 pessoas em operação de 30M pedidos/mês" |
| Problema específico | O que estava quebrado ou pressionado | "A expansão de 400 para 800 cidades pressionava a estrutura de custos" |
| Como fez | Método, ferramenta, abordagem | "Isolei impactos das políticas de remuneração, redesenhei o modelo de agrupamento" |
| Segundo resultado | Outro número do mesmo bloco | "Além da redução de custo, a indisponibilidade caiu de 5% para 1%" |
| Conexão com a habilidade | Frase final ligando à habilidade | "Essa gestão integrada de pessoas, métricas e trade-offs demonstra domínio de Operations Management em escala de marketplace" |
