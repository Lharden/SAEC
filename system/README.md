# SAEC — Sistema de Análise e Extração por Cascata

Pipeline automatizado de extração estruturada de artigos científicos (RSL) usando modelos LLM em cascata (local Ollama + cloud APIs).

## Visão Geral

```
PDF → Ingestão → Extração LLM (Cascade) → Validação YAML → Consolidação XLSX
```

O SAEC processa PDFs de artigos científicos e extrai dados estruturados no formato YAML, seguindo um perfil de extração configurável (CIMO/PICO). A extração usa uma estratégia de cascata: primeiro tenta modelos locais via Ollama, em seguida escala para APIs cloud (OpenAI, Anthropic) quando necessário.

## Estrutura do Projeto

```
system/
├── main.py              # CLI principal do pipeline
├── cli.py               # Interface de linha de comando
├── gui_main.py          # Lançador da GUI desktop
├── .env                 # Configurações e chaves de API
├── requirements.txt     # Dependências Python
│
├── src/                 # Código-fonte
│   ├── config.py        # Configuração central (LLMConfig, LocalProcessingConfig)
│   ├── llm_client.py    # Cliente LLM multi-provedor (Ollama/OpenAI/Anthropic)
│   ├── processors.py    # Processador de artigos (extração, reparo, validação)
│   ├── pipeline_cascade.py  # Lógica de cascata local→cloud
│   ├── pipeline_ingest.py   # Step 2: Ingestão de PDFs
│   ├── pipeline_extract.py  # Step 3: Extração LLM
│   ├── consolidate.py       # Step 5: Consolidação XLSX
│   ├── validators.py        # Validação de YAML contra schema
│   ├── presets.py            # Presets de execução (pilot, batch, etc.)
│   ├── job_runner.py         # Runner de jobs com tracking de progresso
│   │
│   ├── adapters/
│   │   └── ollama_adapter.py  # Adaptador Ollama com modelos padrão
│   │
│   └── gui/                   # Interface gráfica (Tkinter/ttk)
│       ├── app.py             # Janela principal
│       ├── dialog_setup.py    # Configuração (abas: Credenciais | Modelos)
│       ├── panel_status.py    # Painel de progresso com %, ETA, atividade
│       ├── panel_run.py       # Controles de execução do pipeline
│       ├── i18n.py            # Internacionalização (PT-BR / EN-UK)
│       ├── win98_theme.py     # Tema visual moderno (flat, Segoe UI)
│       └── project_config.py  # Persistência de config por projeto (.env)
│
└── tests/               # Suite de testes (274 testes)
```

## Requisitos

- **Python** ≥ 3.12
- **Ollama** (opcional, para modelos locais): [ollama.com](https://ollama.com)
- **GPU**: RTX 3080 10GB é suficiente para modelos via cloud proxy (sem VRAM para extração)

## Instalação

```bash
cd system
pip install -r requirements.txt
```

### Modelos Ollama recomendados

```bash
# Extração principal (cloud proxy — sem VRAM)
ollama pull qwen3-coder-next:cloud

# Fallback diverso
ollama pull glm-5:cloud

# Visão (6.1 GB VRAM)
ollama pull qwen3-vl:8b

# OCR (2.2 GB)
ollama pull glm-ocr:latest

# Embeddings RAG (0.9 GB)
ollama pull nomic-embed-text-v2-moe

# Reranker (0.4 GB)
ollama pull qllama/bge-reranker-v2-m3:q4_k_m
```

## Uso

### GUI Desktop

```bash
python gui_main.py
```

### CLI

```bash
# Pipeline completo
python main.py --all

# Etapa específica
python main.py --step 2          # Ingestão
python main.py --step 3          # Extração
python main.py --step 5          # Consolidação

# Artigo único
python main.py --step 3 --article ART_001

# Simulação (sem escrita)
python main.py --all --dry-run
```

## Configuração

As configurações ficam no arquivo `.env` (veja `.env.template` para referência):

| Variável | Descrição | Padrão |
|----------|-----------|--------|
| `PRIMARY_PROVIDER` | Provedor principal | `ollama` |
| `PROVIDER_EXTRACT` | Roteamento de extração | `auto` |
| `PROVIDER_REPAIR` | Roteamento de reparo YAML | `openai` |
| `PROVIDER_QUOTES` | Roteamento de verificação | `anthropic` |
| `OLLAMA_MODEL_CLOUD` | Modelo principal | `qwen3-coder-next:cloud` |
| `OPENAI_API_KEY` | Chave API OpenAI | — |
| `ANTHROPIC_API_KEY` | Chave API Anthropic | — |

## Pipeline de Extração

1. **Setup** (Step 1): Verifica dependências e configura workspace
2. **Ingestão** (Step 2): Converte PDFs → JSON híbrido (texto + visão)
3. **Extração** (Step 3): LLM extrai dados estruturados → YAML validado
4. **Consolidação** (Step 5): Agrega YAMLs → XLSX consolidado

### Estratégia de Cascata

```
Ollama Local → OpenAI API → Anthropic API
     ↓              ↓              ↓
  VRAM-aware    GPT-5.2 400K   Claude (quotes)
```

## Testes

```bash
cd system
python -m pytest tests/ -x -q
```

**274 testes** cobrem validação, extração, cascata, GUI, i18n, e configuração.

## Licença

Projeto de mestrado — uso acadêmico.
