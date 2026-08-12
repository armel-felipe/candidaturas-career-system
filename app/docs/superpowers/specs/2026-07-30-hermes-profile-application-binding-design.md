# Vínculo fixo entre profile Hermes e candidatura — Design

## Objetivo

Permitir que Felipe delegue uma vaga diretamente a qualquer profile Hermes e
que aquele profile conduza somente aquela candidatura, do intake ao fechamento,
sem terminal, seleção de fila ou risco de misturar contextos com outro profile.

## Unidade de trabalho

Cada profile Hermes pode ter uma única candidatura ativa. O vínculo é criado no
primeiro pedido que contém uma entrada de vaga: registro Notion, vaga salva do
LinkedIn, URL, texto colado ou descrição já preparada.

O vínculo persistido contém o identificador estável do profile Hermes, o
`application_id`, a sessão que o criou, a origem e o horário. Ele é separado
dos arquivos globais legados e sempre aponta para a pasta celular da
candidatura.

## Fluxo para o usuário

Felipe conversa normalmente com cada profile:

1. Envia uma vaga ao profile escolhido e pede para conduzir a candidatura.
2. O profile identifica a origem, executa o intake apropriado e reivindica a
   candidatura para si antes de qualquer análise.
3. O profile leva a vaga até os entregáveis solicitados: FIT_MAP, CV, carta,
   habilidades, registro/atualizações no Notion, respostas e e-mail.
4. Mensagens posteriores daquele profile retomam a mesma candidatura pelo
   vínculo, sem exigir ID, terminal ou contexto repetido.
5. Após o encerramento, o profile fica disponível para uma nova vaga.

Dois profiles podem executar esse fluxo simultaneamente, pois cada um usa uma
pasta e um run próprios. Os fatos do candidato e as regras editoriais seguem
centralizados; Notion e OneDrive permanecem serializados por lock.

## Regras do AGENTS.md

No runtime Hermes, uma mensagem que inicia uma vaga deve seguir este contrato:

- determinar a entrada e criar/recuperar a candidatura app-scoped;
- registrar o vínculo profile–candidatura antes de escrever FIT_MAP ou CV;
- usar somente requests, caminhos e comandos app-scoped daquela candidatura;
- continuar o fluxo até a etapa solicitada, preservando os gates locais;
- retomar o vínculo em mensagens sem nova fonte de vaga;
- proibir comandos legados globais de intake, FIT_MAP, CV e `outputs/`.

## Troca de vaga

Se um profile receber nova vaga enquanto sua candidatura estiver ativa, ele não
troca silenciosamente. Deve informar a candidatura atual e pedir uma decisão
explícita: encerrar/liberar a atual ou trocar o vínculo. A troca preserva todos
os artefatos e o histórico da candidatura anterior.

## Componentes

- Um serviço de binding app-scoped cria, consulta e libera o vínculo do profile
  de maneira atômica.
- A entrada de intake usa o profile Hermes atual como proprietário e recebe o
  `application_id` retornado pelo binding.
- O contexto/hook Hermes resolve a candidatura vinculada antes de preparar uma
  resposta ou request de etapa.
- `AGENTS.md` descreve esse comportamento como padrão obrigatório para profiles
  Hermes e não como instrução opcional.
- A SQLite de controle registra ownership e impede que dois profiles assumam a
  mesma candidatura simultaneamente.

## Critérios de aceitação

- Dois profiles Hermes recebem vagas distintas e criam dois `application_id`
  diferentes, sem arquivo global de vaga ativa.
- Cada profile retoma apenas sua candidatura ao receber uma pergunta ou pedido
  de novo entregável.
- Um profile não pode ler, alterar ou liberar a candidatura pertencente ao
  outro.
- Nova vaga para profile ocupado exige decisão explícita; nenhuma candidatura é
  perdida ou sobrescrita.
- Após o encerramento, o mesmo profile pode assumir outra vaga.
- FIT_MAP, CV, carta, habilidades, Notion e e-mail recebem a mesma identidade
  de candidatura e são auditáveis pelo run correspondente.

## Fora de escopo

Não há seleção automática de vagas por fila, distribuição de carga, criação de
profiles Hermes ou execução em múltiplos hosts. Felipe escolhe o profile e
delega a vaga a ele por conversa.
