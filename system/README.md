# SAEC-O&G — Sistema Autônomo de Extração CIMO

Sistema para extração de dados **CIMO** (Context–Intervention–Mechanism–Outcome) a partir de artigos científicos sobre IA + SCM/SCRM em Oil & Gas.

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
- `run_pipeline.ps1`: script principal (interativo/automatizado) com logs.
- `build_exe.bat`: gera executáveis otimizados `dist/SAEC-OG.exe` (GUI) e `dist/SAEC-OG-CLI.exe` (CLI).
- `build_installer.ps1`: gera instalador (`Setup.exe`) via Inno Setup ou fallback portátil `.zip`.

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

### Gerar executável (.exe)

```powershell
cd "C:\Users\Leonardo\Documents\Computing\Projeto_Mestrado\files\files\articles\00 Dados RSL\system"
.\build_exe.bat
```

Após o build:

```powershell
.\dist\SAEC-OG.exe
.\dist\SAEC-OG-CLI.exe --status
.\dist\SAEC-OG-CLI.exe --all
```

> Observação: o `.exe` usa os diretórios do projeto (`02 T2`, `Extraction`, `system/prompts`) no disco.
> Mantenha a estrutura de pastas do projeto junto ao executável.

### Gerar instalador (.exe de setup)

```powershell
cd "C:\Users\Leonardo\Documents\Computing\Projeto_Mestrado\files\files\articles\00 Dados RSL\system"
.\build_installer.ps1
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

- SAEC-O&G: 1.0.0
- Guia de Extração: v3.3
- Data: Janeiro/2026
