# SAEC — Sistema Autônomo de Extração CIMO

Sistema para extração de dados **CIMO** (Context–Intervention–Mechanism–Outcome) a partir de artigos científicos sobre IA + SCM/SCRM em diferentes domínios.

> Ambiente alvo: **Windows + PowerShell**.  
> Observação: este repositório foi estruturado para rodar via notebooks (01→05) e módulos Python em `system/src/`.

---

## Estrutura (visão geral)

```
00 Dados RSL/
  system/
    notebooks/
    prompts/
    src/
    requirements.txt
    .env.template
    README.md

  Extraction/
    mapping.csv
    outputs/
      work/
      yamls/
      consolidated/
```

- `Extraction/mapping.csv`: mapeia `ArtigoID` ↔ arquivo PDF.
- `Extraction/outputs/work/`: artefatos intermediários por artigo (ex.: imagens das páginas).
- `Extraction/outputs/yamls/`: YAMLs aprovados.
- `Extraction/outputs/consolidated/`: arquivos finais (ex.: Excel).

---

## Quick Start (PowerShell)

### 1) Criar/ativar ambiente Python (recomendado)

No PowerShell:

```powershell
cd "C:\Users\Leonardo\Documents\Computing\Projeto_Mestrado\files\files\articles\00 Dados RSL\system"

python -m venv .venv
.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 2) Configurar variáveis de ambiente (.env)

Copie o template e preencha suas chaves:

```powershell
cd "C:\Users\Leonardo\Documents\Computing\Projeto_Mestrado\files\files\articles\00 Dados RSL\system"
Copy-Item .env.template .env
notepad .env
```

> **Importante:** não versionar `.env` (contém segredos). O `.gitignore` já trata isso.

### 3) Executar notebooks (em ordem)

1. `01_Configuracao.ipynb` — setup inicial (paths, diretórios, mapping)
2. `02_Ingestao.ipynb` — PDF → imagens (vision-first)
3. `03_Extracao_LLM.ipynb` — extração principal + repair loop
4. `04_Validacao.ipynb` — validação/QA (opcional)
5. `05_Consolidacao.ipynb` — consolidar YAMLs em Excel

---

## Scripts (.bat/.ps1)

- `setup.bat`: cria `.venv`, instala dependências e cria `.env`.
- `run.bat`: abre os notebooks via Jupyter.
- `run_pipeline.bat`: modo interativo (menu guiado) ou execução automática via CLI.
- `run_pipeline.ps1`: script principal (interativo/automatizado) com logs e bootstrap de runtime isolado.
- `run_tests.ps1`: wrapper de pytest com runtime isolado (`.runtime/*`) para evitar conflitos de permissão.
- `scripts/build/build_exe.bat`: wrapper do build PowerShell (`scripts/build/build_exe.ps1`) com runtime isolado.
- `scripts/build/build_installer.ps1`: gera instalador (`Setup.exe`) via Inno Setup ou fallback portátil `.zip`.

## Desktop GUI (Win98 style)

Launch the desktop shell:

```powershell
cd "C:\Users\Leonardo\Documents\Computing\Projeto_Mestrado\files\files\articles\00 Dados RSL\system"
python gui_main.py
```

The GUI provides:

- Workspace selection and recent workspaces
- Project dropdown and quick project creation
- Dedicated project folders (`inputs/articles`, `outputs/*`, `logs`, `config`)
- Step/all pipeline execution with live log streaming
- Output explorer for YAML, consolidated files, and logs

## Perfis de Projeto (Universalização RSL)

Cada projeto agora possui um **perfil metodológico próprio** (framework, campos, regras, quotes e prompt).

- O perfil fica salvo no projeto e é carregado automaticamente ao abrir.
- Execução é bloqueada se o projeto não tiver perfil ativo.
- Projeto novo exige configuração de perfil (GUI) ou importação de YAML.
- Alterações de perfil são versionadas dentro de `config/profiles`.
- Se nenhum prompt próprio for informado, o sistema gera/aplica um **prompt universal base** automaticamente.

Fluxos suportados:

1. **GUI-first (recomendado):** construir perfil customizado no dialog de perfil.
2. **Import YAML (avançado):** importar um perfil declarativo validado.
3. **Import XLSX (template oficial):** preencher planilha guiada e importar com validação.
4. **Preset opcional:** usar perfil de biblioteca (ex.: `cimo_v3_3`) apenas como ponto de partida.

### Fluxo obrigatório em projeto novo

1. Crie/abra o projeto no GUI.
2. Configure perfil em `Project > Configure Profile...`:
   - `Use preset profile` (rápido),
   - `Import YAML` (avançado), ou
   - `Import XLSX template` (sem YAML manual), ou
   - `Build custom profile (GUI)` (sem editar arquivo).
3. Salve o perfil ativo.
4. Só depois execute pipeline (`Step 2/3/5` ou `--all`).

Sem perfil ativo válido, a execução é bloqueada por segurança.

### Exemplos de frameworks suportados

- `CIMO`: contexto, intervenção, mecanismo e outcome.
- `PICO` / `PECO`: população/exposição/intervenção/comparador/outcome.
- `SPIDER`: sample, phenomenon of interest, design, evaluation, research type.
- `SPICE`: setting, perspective, intervention, comparison, evaluation.
- `Custom`: campos e regras definidos pelo usuário para qualquer RSL.

### Compatibilidade e migração de schema

- Perfis agora possuem `schema_version` explícito.
- YAMLs legados (sem `schema_version` ou com chaves antigas) são migrados automaticamente na importação/carregamento.
- Se o `schema_version` for desconhecido, a importação falha com erro claro (sem crash).
- XLSX é convertido para perfil canônico interno antes da ativação (não executa direto da planilha).

### Reprodutibilidade (audit trail por execução)

Toda execução que exige perfil (`--all`, `--step 2`, `--step 3`, `--step 5`) salva snapshot imutável do perfil ativo em:

`<projeto>/outputs/consolidated/run_audit/<run_id>/`

Arquivos gerados:
- `profile_<id>_<version>.yaml`
- `extract_prompt.md` (quando existir)
- `profile_snapshot.json` (metadados + hashes)

Guia prático detalhado: `docs/guides/project-profile-setup.md`.

### Gerar executável (.exe)

```powershell
cd "C:\Users\Leonardo\Documents\Computing\Projeto_Mestrado\files\files\articles\00 Dados RSL"
.\scripts\build\build_exe.bat
```

### Rodar testes com runtime isolado

```powershell
cd "C:\Users\Leonardo\Documents\Computing\Projeto_Mestrado\files\files\articles\00 Dados RSL\system"
.\run_tests.ps1
```

Após o build:

```powershell
.\system\dist\SAEC\SAEC.exe
.\system\dist\SAEC-CLI\SAEC-CLI.exe --status
.\system\dist\SAEC-CLI\SAEC-CLI.exe --all
```

> Observação: o `.exe` usa os diretórios do projeto (`02 T2`, `Extraction`, `system/prompts`) no disco.
> Mantenha a estrutura de pastas do projeto junto ao executável.

### Gerar instalador (.exe de setup)

```powershell
cd "C:\Users\Leonardo\Documents\Computing\Projeto_Mestrado\files\files\articles\00 Dados RSL"
.\scripts\build\build_installer.ps1
```

- Se o Inno Setup 6 estiver instalado (`ISCC.exe`), o setup será gerado em `system/dist/installer`.
- Se não estiver instalado, o script gera automaticamente um pacote portátil `.zip` em `system/dist/installer`.

### Otimização de tamanho dos executáveis

O build usa perfil otimizado no PyInstaller (via `.spec`) com exclusão de dependências opcionais pesadas de notebook/ML local (ex.: `jupyter`, `torch`, `tensorflow`, `chromadb`).

- Isso reduz tamanho e tempo de build para o uso principal de pipeline GUI/CLI.
- Recursos opcionais de RAG/local heavy podem ficar indisponíveis no `.exe` (com fallback seguro no runtime).

---

## Changelog (resumo)

- **2026-02-04**: modularização do cliente LLM, script interativo de pipeline, limpeza de legacy (PDF/texto simples, sync antigo, `OLLAMA_MODEL`) e padronização de QA.

---

## Fluxo recomendado

### Piloto (1 artigo)
1. Execute 01 e 02
2. No 03, rode em modo **interativo** (um artigo) para validar prompt/saída
3. Ajuste o prompt somente se necessário

### Batch (restante)
1. No 02 e 03, habilite explicitamente o batch via **switch de segurança** (variável `RUN_BATCH = True`)
2. Processe pendentes
3. Consolide no 05

---

## Diagrama do Pipeline (Mermaid)

```mermaid
flowchart TD
  A[Configuração<br/>01_Configuracao] --> B[Ingestão PDF<br/>02_Ingestao]
  B --> C[Extração LLM<br/>03_Extracao_LLM]
  C --> D[Pós-processo determinístico<br/>postprocess.py]
  D --> E[Validação (schema + regras)<br/>validators.py]
  E --> F[QA de rastreabilidade<br/>qa_guideline.py]
  F --> G[Requote/Correções de quotes<br/>requote_from_texts.py]
  G --> H[Sync mapping.csv<br/>mapping_sync.py]
  H --> I[Consolidação Excel<br/>05_Consolidacao]
```

---

## Descritivo Técnico Consolidado

### Funcionamento

- **Configuração**: `config.py` carrega paths, `.env` e defaults (LLM, extração, limites).
- **Ingestão**: `pdf_vision.py` decide estratégia híbrida (texto vs. imagem) e salva artefatos em `outputs/work/<ART>/`.
- **Extração**: `LLMClient` gera YAML a partir do conteúdo híbrido.
- **Pós-processo**: normalização + correções determinísticas (complexidade, maturidade).
- **Validação**: schema + regras de negócio garantem consistência mínima.
- **QA**: rastreia quotes no `texts.json` e marca `OK/REVIEW/FAIL`.
- **Requote**: melhora quotes com base no texto extraído quando necessário.
- **Mapping Sync**: aprova somente se **validação + QA OK**.
- **Consolidação**: gera Excel e auditoria, opcionalmente filtrando por QA.

### Estrutura Principal

- `system/src/config.py`: paths + configuração LLM + helpers de mapping.
- `system/src/llm_client.py`: cliente principal, agora com mixins.
- `system/src/llm_client_types.py`: tipos, retry e exceções.
- `system/src/llm_client_postprocess.py`: normalização e pós-processamento.
- `system/src/llm_client_quotes.py`: quotes QC e reextração.
- `system/src/llm_utils.py`: parsing de YAML e logs.
- `system/src/validators.py`: schema + regras do guia.
- `system/src/qa_guideline.py`: QA semântico de quotes.
- `system/src/requote_from_texts.py`: requote via `texts.json`.
- `system/src/mapping_sync.py`: sincronização determinística do mapping.
- `system/src/consolidate.py`: consolidação em Excel + auditoria.
- `system/src/qa_utils.py`: utilidades compartilhadas de QA.

### Execução (CLI)

```powershell
python system\main.py --status
python system\main.py --step 1
python system\main.py --step 2
python system\main.py --step 3
python system\main.py --step 5
```

### Execução (Notebooks)

1. `01_Configuracao.ipynb`
2. `02_Ingestao.ipynb`
3. `03_Extracao_LLM.ipynb`
4. `04_Validacao.ipynb`
5. `05_Consolidacao.ipynb`

---

## Troubleshooting

### Erro de dependências
- Confirme que o `pip install -r requirements.txt` rodou dentro do `.venv`.

### Imagens não geradas
- Confirme `pymupdf` instalado.
- Verifique se o PDF está íntegro.

### YAML inválido após extração
- O pipeline tenta *repair* automaticamente (limitado por tentativas).
- Se ainda falhar, revise manualmente e revalide.

---

## Versão

- SAEC: 1.0.0
- Guia de Extração: v3.3
- Data: Janeiro/2026


