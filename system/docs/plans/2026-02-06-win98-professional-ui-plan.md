# SAEC-O&G Win98 Professional UI Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Evoluir o `.exe` para uma aplicacao desktop profissional com UX de operador (workspace, projetos, filas, logs, outputs), preservando visual/classico Win98.

**Architecture:** Manter o pipeline atual como motor (`main.py`, `src/pipeline_*`, `src/processors.py`) e adicionar uma camada GUI orientada a casos de uso. A GUI nao reimplementa regras de negocio: ela orquestra o pipeline existente, persiste estado de workspace/projeto e apresenta monitoramento de execucao.

**Tech Stack:** Python 3.11+, Tkinter/ttk (tema classico), pathlib/json/csv, threading/queue, PyInstaller.

---

### Task 1: Baseline de capacidades atuais

**Files:**
- Read: `system/main.py`
- Read: `system/cli.py`
- Read: `system/run_pipeline.ps1`
- Read: `system/src/config.py`

**Step 1: Consolidar matriz de capacidades atuais**

- Catalogar comandos disponiveis (`--status`, `--step`, `--all`, `--article`, `--dry-run`, `--force`, comandos Typer).
- Catalogar funcionalidades do pipeline (ingestao, extracao, validacao, QA, consolidacao, RAG).
- Catalogar lacunas de produto (sem GUI desktop, sem gerencia de workspace/projeto em camada de UX).

**Step 2: Definir capacidades-alvo de produto profissional**

- Workspace manager
- Project manager
- Job queue + monitoramento
- Config profiles
- Output explorer
- Diagnostics center

---

### Task 2: Contrato de workspace e projeto

**Files:**
- Create: `system/src/workspace.py`
- Create: `system/src/project_model.py`
- Create: `system/tests/test_workspace.py`

**Step 1: Escrever testes de contrato (RED)**

- Resolver `workspace_root`
- Listar projetos
- Criar projeto com estrutura padrao
- Validar consistencia de pastas obrigatorias

**Step 2: Implementar contrato minimo (GREEN)**

- Dataclasses para `WorkspaceConfig` e `ProjectConfig`
- Funcoes de descoberta/criacao/validacao

**Step 3: Validar**

- Rodar: `python -m pytest system/tests/test_workspace.py -v`

---

### Task 3: Layout dedicado de pastas por projeto

**Files:**
- Create: `system/src/project_layout.py`
- Modify: `system/src/config.py`
- Create: `system/tests/test_project_layout.py`

**Step 1: Escrever testes de estrutura (RED)**

- Estrutura esperada por projeto:
  - `projects/<project_id>/inputs/articles`
  - `projects/<project_id>/outputs/work`
  - `projects/<project_id>/outputs/yamls`
  - `projects/<project_id>/outputs/consolidated`
  - `projects/<project_id>/logs`
  - `projects/<project_id>/config/project.env`

**Step 2: Implementar mapeamento de paths (GREEN)**

- Integrar no `Paths` para operar em contexto de projeto ativo.

**Step 3: Validar**

- Rodar: `python -m pytest system/tests/test_project_layout.py -v`

---

### Task 4: Perfis de configuracao e presets

**Files:**
- Create: `system/src/settings_store.py`
- Create: `system/src/presets.py`
- Create: `system/tests/test_settings_store.py`

**Step 1: Escrever testes (RED)**

- Salvar/carregar perfil
- Merge de defaults + overrides de projeto
- Presets (`piloto`, `batch`, `local_only`, `api_only`)

**Step 2: Implementar persistencia (GREEN)**

- JSON para UI settings
- `.env` por projeto para runtime

**Step 3: Validar**

- Rodar: `python -m pytest system/tests/test_settings_store.py -v`

---

### Task 5: Shell GUI Win98 (janela principal)

**Files:**
- Create: `system/src/gui/app.py`
- Create: `system/src/gui/win98_theme.py`
- Create: `system/src/gui/layout_main.py`
- Create: `system/src/gui/resources/` (icones/bitmaps classicos)

**Step 1: Criar estrutura visual base**

- Menu bar (`File`, `Workspace`, `Project`, `Pipeline`, `Tools`, `Help`)
- Toolbar com botoes classicos (16x16)
- Status bar inferior
- Painel lateral (arvore de projeto)
- Area principal com tabs (`Overview`, `Run`, `Outputs`, `Logs`)

**Step 2: Aplicar tema Win98 consistente**

- Paleta cinza classica
- Bordas sunken/raised
- Fonte `MS Sans Serif` fallback segura
- Controles com spacing e dimensoes classicas

**Step 3: Smoke test manual**

- Abrir app e verificar responsividade em desktop e resolucoes menores.

---

### Task 6: Workspace selector + dropdowns de projeto

**Files:**
- Create: `system/src/gui/dialog_workspace.py`
- Create: `system/src/gui/dialog_project.py`
- Modify: `system/src/gui/app.py`

**Step 1: Implementar selecao de workspace**

- Dialog de escolha de pasta
- Ultimos workspaces
- Validacao de estrutura

**Step 2: Implementar selecao de projeto por lista suspensa**

- Dropdown de projeto ativo
- Acao `New Project...`
- Acao `Open Project Folder`

**Step 3: Persistir estado da sessao**

- Restaurar ultimo workspace/projeto na inicializacao.

---

### Task 7: Orquestrador de execucao com fila (job runner)

**Files:**
- Create: `system/src/job_runner.py`
- Create: `system/src/gui/panel_run.py`
- Modify: `system/main.py`
- Create: `system/tests/test_job_runner.py`

**Step 1: Escrever testes de fila/cancelamento (RED)**

- Enfileirar etapas
- Atualizar progresso
- Cancelar execucao
- Isolar erros por job

**Step 2: Implementar runner nao bloqueante (GREEN)**

- Thread worker + queue
- Eventos para GUI (progress, log, complete, failed)

**Step 3: Integrar com pipeline existente**

- Reuso de `step_1_configuracao`, `step_2_ingestao`, `step_3_extracao`, `step_5_consolidacao`.

---

### Task 8: Output explorer profissional

**Files:**
- Create: `system/src/gui/panel_outputs.py`
- Create: `system/src/gui/panel_logs.py`
- Create: `system/src/gui/panel_status.py`

**Step 1: Output explorer**

- Lista de artefatos (work/yamls/consolidated)
- Filtros por artigo/status/data
- Acoes: abrir arquivo, abrir pasta, copiar caminho

**Step 2: Logs e diagnostico**

- Viewer de logs com filtro (`INFO/WARN/ERROR`)
- Painel de erros recentes e recomendacoes

**Step 3: Dashboard de saude**

- Dependencias
- APIs
- Espaço em disco
- Ultima execucao

---

### Task 9: Guardrails de seguranca operacional

**Files:**
- Create: `system/src/safety_policy.py`
- Modify: `system/src/gui/panel_run.py`
- Create: `system/tests/test_safety_policy.py`

**Step 1: Regras de bloqueio**

- Bloquear operacoes destrutivas por padrao (`delete`, `force destructive cleanup`, etc.)
- Confirmacao dupla para operacoes sensiveis

**Step 2: Modo permissoes amplas seguras**

- Permitir build/test/run e automacoes guiadas
- Proibir execucao autonoma nao solicitada de scripts potencialmente perigosos

**Step 3: Validar**

- Rodar: `python -m pytest system/tests/test_safety_policy.py -v`

---

### Task 10: Empacotamento do `.exe` com GUI

**Files:**
- Modify: `system/SAEC-OG.spec`
- Modify: `system/build_exe.bat`
- Create: `system/gui_main.py`

**Step 1: Definir entrypoint GUI**

- `gui_main.py` inicializa shell Win98.

**Step 2: Ajustar PyInstaller**

- Incluir assets de UI
- `console=False` para app GUI (mantendo executavel CLI separado opcional)

**Step 3: Verificacao**

- Executar build e abrir `.exe` em ambiente limpo.

---

### Task 11: Plano de rollout incremental

**Files:**
- Create: `system/docs/win98-ui-rollout.md`

**Step 1: Fase 1 (MVP)**

- Workspace + Project selector + Run step-by-step + Output explorer simples.

**Step 2: Fase 2**

- Queue, logs ao vivo, presets, monitoramento.

**Step 3: Fase 3**

- RAG tools visuais, diagnostico avancado, templates de projeto.

---

### Task 12: Verificacao final de qualidade

**Files:**
- Modify: `system/README.md`

**Step 1: Testes e checks**

- `python -m pytest -v`
- `python -m mypy --config-file ../pyproject.toml src`

**Step 2: Checklist de produto**

- Fluxo completo sem terminal
- Projeto isolado por pasta
- Preservacao visual Win98
- Erros acionaveis para usuario nao tecnico
