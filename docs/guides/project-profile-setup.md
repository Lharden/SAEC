# Guia Rápido: Configuração de Perfil de Projeto (RSL)

## Objetivo

Garantir que cada projeto use um perfil metodológico fixo (campos, regras, quotes e prompt) antes da execução do pipeline.

## Regra de uso

1. Projeto novo: configuração de perfil é obrigatória.
2. Projeto existente: perfil ativo é carregado automaticamente.
3. Alterações só mudam quando o usuário editar e salvar.
4. Sem perfil ativo válido, o pipeline não executa (`Step 2/3/5` e `--all`).

## Como configurar no GUI

1. Abra o projeto.
2. Acesse `Project > Configure Profile...`.
3. Escolha um modo:
   - `Use preset profile`: ponto de partida opcional (ex.: `cimo_v3_3`).
   - `Import YAML`: importar perfil declarativo.
   - `Import XLSX template`: importar planilha oficial validada.
   - `Build custom profile (GUI)`: criar campos/regras sem editar código.
   - O sistema executa sempre pelo **perfil ativo**; não existe campo global obrigatório por domínio.
4. Prompt do perfil:
   - Pode ser informado por arquivo `.md` nos modos de importação.
   - No `Build custom profile (GUI)`, pode ser editado inline no próprio diálogo.
   - Se nenhum prompt for fornecido, o sistema usa/genera um prompt universal base automaticamente.
5. Corrija pendências exibidas no resumo de validação.
6. Clique em `Save`.

## Frameworks possíveis

- CIMO
- PICO
- PECO
- SPIDER
- SPICE
- Custom (estrutura própria)

## Versionamento e compatibilidade

- Todo perfil salvo usa `schema_version` explícito.
- YAML legado é migrado automaticamente quando possível.
- Se o schema for incompatível, a importação falha com mensagem de erro clara.
- XLSX nunca é usado diretamente em runtime: ele é convertido para perfil canônico (`ProfileSpec`) e validado antes de ativar.

## Template XLSX oficial

No modo `Import XLSX template`, clique em `Download XLSX Template...`.

Abas obrigatórias:

- `meta`
- `fields`
- `rules`
- `quotes_policy`
- `prompt`

Regras importantes:

- `fields.id` deve ser único.
- Campo `ArtigoID` é obrigatório para integração com mapping/pipeline.
- Para listas, use `|` (ex.: `A|B|C`).
- Booleans aceitos: `true/false`, `yes/no`, `sim/nao`, `1/0`.
- Qualquer erro de linha/campo bloqueia ativação do perfil (fail-safe).

## Reprodutibilidade

A cada execução com perfil obrigatório, o sistema salva snapshot em:

`outputs/consolidated/run_audit/<run_id>/`

Conteúdo:

- YAML exato do perfil usado
- Prompt de extração usado (quando disponível)
- Metadados e hash SHA-256 dos artefatos

