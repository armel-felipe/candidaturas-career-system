# Resumo Narrativo de CV Personalizado — Design

## Objetivo

Restaurar o resumo personalizado do CV em primeira pessoa. O catálogo de
posicionamento deve orientar o objetivo profissional, sem substituir a
apresentação executiva, as histórias relevantes ou as competências que o
FIT_MAP selecionou.

## Estrutura do resumo

O resumo em português terá até três frases, sempre em primeira pessoa:

1. **Posicionamento.** Apresenta experiência, foco e contexto de atuação a
   partir do cargo, dor central e cluster dominante do FIT_MAP. Exemplo:
   `Atuo há mais de 20 anos em operações, planejamento e transformação de negócios complexos.`
2. **Prova.** Conecta duas histórias distintas e defensáveis do CV, priorizadas
   pelo FIT_MAP. Cada história deve contribuir com escopo ou resultado diferente.
3. **Direção.** Reescreve o `caso` do catálogo como objetivo natural:
   `Busco uma posição em que eu possa estruturar a cadência de portfólio, metas e captura de benefícios.`

Se a direção não acrescentar informação à abertura ou à prova, a terceira frase
é omitida. Não há obrigação de reproduzir a palavra `caso`, o título do cargo
ou a formulação do catálogo literalmente.

## Uso do catálogo

O seletor atual continua escolhendo uma área/caso com FIT_MAP e descrição da
vaga. O catálogo informa o tema da frase de direção; `resultado_chave` continua
apenas como sinal de desempate e nunca é texto publicável.

## Antirrepetição

Antes de compor cada frase, o compositor normaliza termos (caixa, acentos e
pontuação) e mantém os termos substantivos já usados. A frase seguinte não pode
repetir um termo de foco da frase anterior, salvo nomes próprios, cargo alvo ou
uma keyword ATS necessária. Quando houver colisão, usa sinônimo aprovado ou
remove o termo redundante. Se não houver conteúdo novo, a frase é omitida.

As duas histórias não podem ser a mesma experiência nem repetir o mesmo
resultado numérico. Abertura não pode listar novamente resultados, e direção
não pode recontar uma história.

## Fontes e evidência

- Abertura usa somente dados do FIT_MAP e o perfil canônico já autorizado.
- Prova usa exclusivamente experiências e bullets que já alimentam
  `summary_support`.
- Direção usa apenas o `caso` validado pelo catálogo, sem números ou texto de
  `resultado_chave`.
- A proveniência atual do catálogo e das duas evidências permanece obrigatória.

## Validação

Além dos validadores existentes, o resumo deve falhar quando:

- o texto português não estiver em primeira pessoa;
- houver repetição de termo de foco entre frases sem exceção autorizada;
- as duas histórias usarem a mesma experiência ou o mesmo número;
- o `resultado_chave` do catálogo aparecer no resumo ou em `summary_support`;
- a direção repetir integralmente a abertura ou a prova.

CVs em inglês permanecem no comportamento atual até haver copy aprovada em
primeira pessoa para esse idioma.
