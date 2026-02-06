# SAEC-O&G Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implementar sistema de extração CIMO para 38 artigos científicos de Oil & Gas usando LLMs com visão.

**Architecture:** Pipeline em 5 notebooks Jupyter: Configuração → Ingestão (PDF→imagens) → Extração (Claude) → Validação (Pydantic + 12 regras) → Consolidação (Excel). Modo interativo para piloto, batch para produção.

**Tech Stack:** Python 3.10+, Jupyter, PyMuPDF, Anthropic API, OpenAI API, Pydantic, Pandas, OpenPyXL

---

## Estrutura do Plano

| Fase | Tasks | Descrição |
|------|-------|-----------|
| 1 | 1-4 | Setup: estrutura, dependências, .env, config |
| 2 | 5-7 | Prompt: versão condensada do Guia v3.3 |
| 3 | 8-11 | Módulos Python: config, pdf, llm, validators |
| 4 | 12-16 | Notebooks: 01 a 05 |
| 5 | 17-18 | Teste piloto e ajustes |

---

## FASE 1: Setup Inicial

### Task 1: Criar Estrutura de Pastas

**Files:**
- Create: `system/notebooks/` (diretório)
- Create: `system/src/` (diretório)
- Create: `system/prompts/` (diretório)
- Create: `Extraction/outputs/work/` (diretório)
- Create: `Extraction/outputs/yamls/` (diretório)
- Create: `Extraction/outputs/consolidated/` (diretório)

**Step 1: Criar diretórios**

```bash
mkdir -p "system/notebooks"
mkdir -p "system/src"
mkdir -p "system/prompts"
mkdir -p "Extraction/outputs/work"
mkdir -p "Extraction/outputs/yamls"
mkdir -p "Extraction/outputs/consolidated"
```

**Step 2: Verificar estrutura**

```bash
find system -type d
find Extraction/outputs -type d
```

Expected: Todos os diretórios listados

---

### Task 2: Criar requirements.txt

**Files:**
- Create: `system/requirements.txt`

**Step 1: Criar arquivo de dependências**

```text
# Core
python-dotenv>=1.0.0
pyyaml>=6.0
pydantic>=2.0

# PDF e Imagens
pymupdf>=1.24.0
pillow>=10.0

# LLM APIs
anthropic>=0.30.0
openai>=1.30.0

# Notebooks
ipywidgets>=8.0
ipython>=8.0

# Consolidação
openpyxl>=3.1.0
pandas>=2.0

# Utilitários
rich>=13.0
tqdm>=4.66.0
```

**Step 2: Instalar dependências**

```bash
cd system && pip install -r requirements.txt
```

Expected: Instalação sem erros

---

### Task 3: Criar Template .env

**Files:**
- Create: `system/.env.template`
- Create: `system/.env` (usuário preenche)

**Step 1: Criar template**

```env
# ===========================================
# SAEC-O&G - Configuração de APIs
# ===========================================
# Copie este arquivo para .env e preencha suas chaves

# Anthropic (Claude) - Obrigatório
ANTHROPIC_API_KEY=sk-ant-sua-chave-aqui

# OpenAI (GPT-4o) - Obrigatório para repair loop
OPENAI_API_KEY=sk-sua-chave-aqui

# ===========================================
# Modelos (não alterar sem necessidade)
# ===========================================
ANTHROPIC_MODEL=claude-sonnet-4-20250514
OPENAI_MODEL=gpt-4o

# ===========================================
# Estratégia de Extração
# ===========================================
# true = Claude extrai + GPT-4o formata
# false = usa apenas PRIMARY_PROVIDER
USE_TWO_PASS=true
PRIMARY_PROVIDER=anthropic

# ===========================================
# Limites
# ===========================================
MAX_REPAIR_ATTEMPTS=3
IMAGE_DPI=300
```

**Step 2: Criar .gitignore**

```gitignore
# Secrets
.env

# Python
__pycache__/
*.pyc
.ipynb_checkpoints/

# Outputs (opcional - comentar se quiser versionar)
# Extraction/outputs/
```

---

### Task 4: Criar Módulo de Configuração

**Files:**
- Create: `system/src/__init__.py`
- Create: `system/src/config.py`

**Step 1: Criar __init__.py**

```python
"""SAEC-O&G - Sistema Autônomo de Extração CIMO para Oil & Gas"""

__version__ = "1.0.0"
```

**Step 2: Criar config.py**

```python
"""Configuração central do SAEC-O&G."""

import os
from pathlib import Path
from dataclasses import dataclass
from dotenv import load_dotenv

# Carregar .env
load_dotenv()


@dataclass
class Paths:
    """Caminhos do projeto."""

    # Raiz do projeto (00 Dados RSL)
    PROJECT_ROOT: Path = Path(__file__).parent.parent.parent.parent

    # Pastas principais
    SYSTEM: Path = PROJECT_ROOT / "system"
    ARTICLES: Path = PROJECT_ROOT / "02 T2"
    EXTRACTION: Path = PROJECT_ROOT / "Extraction"

    # Outputs
    OUTPUTS: Path = EXTRACTION / "outputs"
    WORK: Path = OUTPUTS / "work"
    YAMLS: Path = OUTPUTS / "yamls"
    CONSOLIDATED: Path = OUTPUTS / "consolidated"

    # Arquivos importantes
    MAPPING_CSV: Path = EXTRACTION / "mapping.csv"
    GUIA_PROMPT: Path = SYSTEM / "prompts" / "guia_v3_3_prompt.md"

    def ensure_dirs(self):
        """Cria diretórios se não existirem."""
        for path in [self.WORK, self.YAMLS, self.CONSOLIDATED]:
            path.mkdir(parents=True, exist_ok=True)


@dataclass
class LLMConfig:
    """Configuração dos LLMs."""

    # APIs
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    # Modelos
    ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o")

    # Estratégia
    USE_TWO_PASS: bool = os.getenv("USE_TWO_PASS", "true").lower() == "true"
    PRIMARY_PROVIDER: str = os.getenv("PRIMARY_PROVIDER", "anthropic")

    # Limites
    MAX_REPAIR_ATTEMPTS: int = int(os.getenv("MAX_REPAIR_ATTEMPTS", "3"))

    def validate(self) -> list[str]:
        """Valida configuração. Retorna lista de erros."""
        errors = []
        if not self.ANTHROPIC_API_KEY:
            errors.append("ANTHROPIC_API_KEY não configurada")
        if not self.OPENAI_API_KEY and self.USE_TWO_PASS:
            errors.append("OPENAI_API_KEY não configurada (necessária para USE_TWO_PASS=true)")
        return errors


@dataclass
class ExtractionConfig:
    """Configuração de extração."""

    IMAGE_DPI: int = int(os.getenv("IMAGE_DPI", "300"))
    MIN_QUOTES: int = 3
    MAX_QUOTES: int = 8


# Instâncias globais
paths = Paths()
llm_config = LLMConfig()
extraction_config = ExtractionConfig()
```

**Step 3: Testar importação**

```python
# No Python ou notebook
import sys
sys.path.insert(0, str(Path("system/src")))
from config import paths, llm_config
print(f"Project root: {paths.PROJECT_ROOT}")
print(f"Articles: {paths.ARTICLES}")
```

Expected: Caminhos impressos corretamente

---

## FASE 2: Prompt Condensado

### Task 5: Criar Versão Condensada do Guia

**Files:**
- Create: `system/prompts/guia_v3_3_prompt.md`

**Step 1: Criar prompt condensado**

O prompt condensado deve manter:
- Template YAML completo
- Codebook (valores permitidos)
- 12 Regras de Validação
- Protocolo de Auto-Revisão
- Instruções críticas

Remover:
- Explicações detalhadas
- Exemplos redundantes
- Histórico de versões

```markdown
# PROMPT — EXTRAÇÃO CIMO (Guia v3.3 Condensado)

## Papel
Você é o extrator de dados de uma RSL sobre IA + SCM/SCRM em Oil & Gas, seguindo o framework CIMO.

## Entrada
- **ArtigoID**: fornecido (formato: ART_001)
- **Artigo**: imagens das páginas do PDF

## Saída
- **Somente YAML** conforme Template (Seção 4)
- Validar pelas 12 Regras (Seção 5) e Auto-Revisão (Seção 6)
- Quotes: 3-8, literais, ≤3 linhas, com página

---

## 1. Framework CIMO

| Elemento | Questão | Campos |
|----------|---------|--------|
| C - Context | Onde a IA é aplicada? | SegmentoO&G, Ambiente, Complexidade, ProcessoSCM, TipoRisco, ObjetoCrítico |
| I - Intervention | Qual técnica? | ClasseIA, TarefaAnalítica, FamíliaModelo, TipoDado, Maturidade |
| M - Mechanism | COMO/POR QUE gera valor? | Mecanismo_Declarado, Mecanismo_Inferido, Mecanismo_Estruturado |
| O - Outcome | Quais resultados? | ResultadoTipo, Resultados_Quant, Resultados_Qual, NívelEvidência |

**CRÍTICO:** Mecanismo (M) é o campo mais importante. Priorize identificar HOW/WHY.

---

## 2. Codebook (Valores Permitidos)

### Contexto
- **SegmentoO&G**: Upstream (E&P), Midstream, Downstream, Cross-segment, NR
- **Ambiente**: Offshore, Onshore, Híbrido, NR
  - REGRA: Classificar onde a IA ATUA, não onde o ativo opera
- **Complexidade**: Alta, Média, Baixa, NR
  - F1: Offshore? (+1) | F2: ≥5 fornecedores? (+1) | F3: Risco alto/crítico? (+1)
  - 3pts=Alta, 2pts=Média, 0-1=Baixa
- **Confiança**: Alta, Média, Baixa

### ProcessoSCM_Alvo
Planejamento de demanda | Gestão de estoques | Seleção/qualificação de fornecedores | Gestão de contratos | Procurement/compras | Logística/transporte | Planejamento de produção | Manutenção/MRO | Gestão de riscos da cadeia | Monitoramento/visibilidade | Integração/coordenação | Outro | NR

### TipoRisco_SCRM
Risco de fornecimento | Risco de demanda | Risco operacional | Risco de transporte/logística | Risco de estoque | Risco financeiro | Risco de ativos | Risco ambiental/regulatório | Risco de segurança (security) | Risco de projeto | Risco geopolítico/externo | Múltiplos | NR

### Intervenção
- **ClasseIA**: ML supervisionado, ML não supervisionado, Deep Learning, NLP, Visão computacional, Otimização/heurísticas, Probabilístico/Bayesiano, Sistemas especialistas/regras, Digital Twin com IA, Híbrido, Outro, NR
- **TarefaAnalítica**: Previsão, Classificação, Regressão, Detecção de anomalia, Clustering, Extração de informação (NLP), Recomendação, Otimização, Simulação/what-if, Automação (RPA+IA), Outro, NR
- **FamíliaModelo**: Ensemble tree-based, SVM/Kernel, Regressão linear/logística, Redes neurais feedforward, Redes recorrentes, Redes convolucionais, Transformers/Attention, Clustering, Redes Bayesianas, Metaheurísticas, Programação matemática, MCDM/Decisão, CBR/Especialista, Simulação, Outro, NR
- **TipoDado**: Tabular/ERP, Séries temporais, Texto, Imagem/Vídeo, Multimodal, NR
- **Maturidade**: Conceito, Protótipo, Piloto, Produção, NR

### Mecanismo
- **CategoriaMecanismo**: Antecipação de risco, Detecção precoce/anomalias, Redução de incerteza, Priorização/alocação ótima, Integração de dados dispersos, Padronização/consistência, Otimização de trade-offs, Automação informacional (NLP), Outro, NR
- **Mecanismo_Fonte**: Declarado, Inferido, Misto

### Outcome
- **ResultadoTipo**: Quantitativo, Qualitativo, Misto, NR
- **NívelEvidência**: Estudo de caso real, Experimento com dados reais, Simulação com dados reais, Simulação com dados sintéticos, Survey/entrevistas, Proposta teórica/framework, Revisão conceitual, NR

### Quotes
- **TipoQuote**: Contexto, Intervenção, Mecanismo, Outcome, Limitação, Método, Outro

---

## 3. Regras Críticas de Preenchimento

### Mecanismo_Inferido
CADA sentença DEVE iniciar com "INFERIDO:"
```
✓ INFERIDO: O clustering reduz espaço de busca. INFERIDO: A padronização melhora consistência.
✗ INFERIDO: O clustering reduz espaço de busca. A padronização melhora consistência.
```

### Mecanismo_Estruturado
STRING ÚNICA no formato: "Entrada → Transformação → Mediação → Resultado"
```
✓ "Dados históricos → CBR + clustering → Recomendação → Seleção de fornecedor"
✗ Múltiplas linhas ou bloco YAML
```

### Resultados_Quant
Formato: "métrica: valor (vs. baseline: X)" ou "(baseline: NR)"
```
✓ "Acurácia: 92.5% (vs. baseline: 78.3%); F1-score: 0.89 (baseline: NR)"
✗ "Dataset: 1430 registros; 36 atributos" (isso vai em Dados_Descrição)
```

### Complexidade_Justificativa
DEVE conter pontuação F1/F2/F3
```
✓ "F1=0 (onshore), F2=1 (>7000 fornecedores), F3=1 (risco crítico mencionado)"
```

---

## 4. Template YAML

```yaml
---
# METADATA
ArtigoID: "ART_0XX"
Ano: XXXX
TipoPublicação: "Journal" | "Conference" | "Outro"
Referência_Curta: "Autor et al., Ano"
DOI: "https://doi.org/..."

# CONTEXTO (C)
SegmentoO&G: "..."
SegmentoO&G_Confiança: "Alta" | "Média" | "Baixa"
Ambiente: "Offshore" | "Onshore" | "Híbrido" | "NR"
Complexidade: "Alta" | "Média" | "Baixa" | "NR"
Complexidade_Justificativa: "F1=X, F2=X (detalhes), F3=X"
ProcessoSCM_Alvo: "..."
TipoRisco_SCRM: "..." | "NR"
ObjetoCrítico: "..."

# NARRATIVAS
ProblemaNegócio_Contexto: |
  [3-6 linhas: problema + contexto operacional]

# INTERVENÇÃO (I)
ClasseIA: "..."
ClasseIA_Confiança: "Alta" | "Média" | "Baixa"
TarefaAnalítica: "..."
FamíliaModelo: "..."
TipoDado: "..."
Maturidade: "Conceito" | "Protótipo" | "Piloto" | "Produção"
Maturidade_Confiança: "Alta" | "Média" | "Baixa"

Intervenção_Descrição: |
  [2-5 linhas: solução de IA]

Dados_Descrição: |
  [2-6 linhas: fontes, volume, período]

# MECANISMO (M)
CategoriaMecanismo: "..."
Mecanismo_Fonte: "Declarado" | "Inferido" | "Misto"
Mecanismo_Declarado: |
  [transcrição ou NR]
Mecanismo_Inferido: |
  INFERIDO: [cada sentença com prefixo]
Mecanismo_Estruturado: "Entrada → Transformação → Mediação → Resultado"

# OUTCOME (O)
ResultadoTipo: "Quantitativo" | "Qualitativo" | "Misto"
Resultados_Quant: "métrica: valor (vs. baseline: X)"
Resultados_Qual: "..."
NívelEvidência: "..."
Limitações_Artigo: |
  [apenas declaradas pelos autores ou NR]

# OPCIONAL
Observação: |
  [notas se necessário]

# QUOTES (3-8)
Quotes:
  - QuoteID: Q001
    TipoQuote: "Mecanismo"
    Trecho: "..."
    Página: "p.X"
---
```

---

## 5. Regras de Validação (12 Essenciais)

| # | Regra |
|---|-------|
| 1 | TipoRisco_SCRM ≠ NR → ObjetoCrítico DEVE estar preenchido |
| 2 | ResultadoTipo = Quantitativo → Resultados_Quant no formato "métrica: valor (vs. baseline)" |
| 3 | Maturidade = Produção → NívelEvidência = "Estudo de caso real" OU "Experimento com dados reais" |
| 4 | ClasseIA = Híbrido → especificar técnicas em Intervenção_Descrição E FamíliaModelo |
| 5 | Mecanismo_Inferido preenchido → CADA sentença com prefixo "INFERIDO:" |
| 6 | Mecanismo_Estruturado = string única "Entrada → Transformação → Mediação → Resultado" |
| 7 | ArtigoID = ID fornecido pelo solicitante |
| 8 | NívelEvidência = "Simulação com dados sintéticos" → Maturidade ≠ Produção/Piloto |
| 9 | Complexidade_Justificativa DEVE ter pontuação F1/F2/F3 |
| 10 | Ambiente = onde a IA ATUA, não onde o ativo opera |
| 11 | Limitações_Artigo = NR → confirmar ausência de: limit*, restrict*, challeng*, only |
| 12 | Nomes de campos EXATOS do template |

---

## 6. Protocolo de Auto-Revisão

### FASE 1: Maior Risco
- [ ] Ambiente reflete onde a IA ATUA?
- [ ] Complexidade_Justificativa tem F1/F2/F3?
- [ ] Mecanismo_Estruturado é string única?
- [ ] Mecanismo_Inferido tem "INFERIDO:" em CADA sentença?
- [ ] Limitações_Artigo não usa NR prematuramente?
- [ ] Nomes de campos EXATOS?

### FASE 2: Risco Moderado
- [ ] ClasseIA = Híbrido → técnicas em FamíliaModelo E Intervenção_Descrição?
- [ ] Maturidade consistente com NívelEvidência?
- [ ] Resultados_Quant sem características de dataset?
- [ ] Quotes LITERAIS (cópia exata)?
- [ ] TipoRisco ≠ NR → ObjetoCrítico preenchido?

### FASE 3: Completude
- [ ] Campos obrigatórios preenchidos?
- [ ] Campos de Confiança presentes?
- [ ] 3-8 quotes extraídos?
- [ ] Pelo menos 1 quote de Mecanismo?
- [ ] ProblemaNegócio_Contexto tem 3-6 linhas?

### FASE 4: Validação Final
- [ ] 12 Regras verificadas?
- [ ] ArtigoID correto?

**Se TODAS passam → Extração aprovada**
**Se QUALQUER falha → CORRIGIR antes de entregar**

---

## 7. Inferência de Mecanismo (quando não declarado)

Se o artigo não explica o "porquê", use estes padrões:

| Padrão da IA | Mecanismo Provável |
|--------------|-------------------|
| Prevê antes de ocorrer | Antecipação de risco |
| Detecta anomalia | Detecção precoce |
| Melhora acurácia de forecast | Redução de incerteza |
| Processa múltiplas fontes | Integração de dados dispersos |
| Padroniza avaliação | Padronização/consistência |
| Otimiza múltiplos objetivos | Otimização de trade-offs |

---

**FIM DO GUIA CONDENSADO — v3.3**
```

**Step 2: Verificar tamanho**

O prompt condensado deve ter ~50% menos tokens que o original (~300 linhas vs ~640).

---

### Task 6: Criar Schema Pydantic

**Files:**
- Create: `system/src/schemas.py`

**Step 1: Criar schemas de validação**

```python
"""Schemas Pydantic para validação de YAML extraído."""

from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator, model_validator
import re


# Enums como Literals
SegmentoOG = Literal[
    "Upstream (E&P)", "Midstream", "Downstream", "Cross-segment", "NR"
]
Ambiente = Literal["Offshore", "Onshore", "Híbrido", "NR"]
Complexidade = Literal["Alta", "Média", "Baixa", "NR"]
Confianca = Literal["Alta", "Média", "Baixa"]
TipoPublicacao = Literal["Journal", "Conference", "Relatório técnico", "Tese/Dissertação", "Outro", "NR"]

ClasseIA = Literal[
    "ML supervisionado", "ML não supervisionado", "Deep Learning", "NLP",
    "Visão computacional", "Otimização/heurísticas", "Probabilístico/Bayesiano",
    "Sistemas especialistas/regras", "Digital Twin com IA", "Híbrido", "Outro", "NR"
]

TarefaAnalitica = Literal[
    "Previsão", "Classificação", "Regressão", "Detecção de anomalia",
    "Clustering", "Extração de informação (NLP)", "Recomendação",
    "Otimização", "Simulação/what-if", "Automação (RPA+IA)", "Outro", "NR"
]

Maturidade = Literal["Conceito", "Protótipo", "Piloto", "Produção", "NR"]
TipoDado = Literal["Tabular/ERP", "Séries temporais", "Texto", "Imagem/Vídeo", "Multimodal", "NR"]
MecanismoFonte = Literal["Declarado", "Inferido", "Misto"]
ResultadoTipo = Literal["Quantitativo", "Qualitativo", "Misto", "NR"]

NivelEvidencia = Literal[
    "Estudo de caso real", "Experimento com dados reais", "Simulação com dados reais",
    "Simulação com dados sintéticos", "Survey/entrevistas", "Proposta teórica/framework",
    "Revisão conceitual", "NR"
]

CategoriaMecanismo = Literal[
    "Antecipação de risco", "Detecção precoce/anomalias", "Redução de incerteza",
    "Priorização/alocação ótima", "Integração de dados dispersos", "Padronização/consistência",
    "Otimização de trade-offs", "Automação informacional (NLP)", "Outro", "NR"
]

TipoQuote = Literal["Contexto", "Intervenção", "Mecanismo", "Outcome", "Limitação", "Método", "Outro"]


class Quote(BaseModel):
    """Schema para uma quote."""
    QuoteID: str = Field(..., pattern=r"^Q\d{3}$")
    TipoQuote: TipoQuote
    Trecho: str = Field(..., min_length=10, max_length=500)
    Página: str = Field(..., pattern=r"^p\.\d+.*$")


class ExtractionSchema(BaseModel):
    """Schema completo para extração CIMO."""

    # METADATA
    ArtigoID: str = Field(..., pattern=r"^ART_\d{3}$")
    Ano: int = Field(..., ge=1990, le=2030)
    TipoPublicação: TipoPublicacao
    Referência_Curta: str = Field(..., min_length=5)
    DOI: Optional[str] = None

    # CONTEXTO
    SegmentoO_G: SegmentoOG = Field(..., alias="SegmentoO&G")
    SegmentoO_G_Confiança: Confianca = Field(..., alias="SegmentoO&G_Confiança")
    Ambiente: Ambiente
    Complexidade: Complexidade
    Complexidade_Justificativa: str
    ProcessoSCM_Alvo: str
    TipoRisco_SCRM: str
    ObjetoCrítico: Optional[str] = None

    # NARRATIVAS
    ProblemaNegócio_Contexto: str = Field(..., min_length=50)

    # INTERVENÇÃO
    ClasseIA: ClasseIA
    ClasseIA_Confiança: Confianca
    TarefaAnalítica: TarefaAnalitica
    FamíliaModelo: str
    TipoDado: TipoDado
    Maturidade: Maturidade
    Maturidade_Confiança: Confianca
    Intervenção_Descrição: str = Field(..., min_length=30)
    Dados_Descrição: str = Field(..., min_length=30)

    # MECANISMO
    CategoriaMecanismo: CategoriaMecanismo
    Mecanismo_Fonte: MecanismoFonte
    Mecanismo_Declarado: str
    Mecanismo_Inferido: Optional[str] = None
    Mecanismo_Estruturado: str

    # OUTCOME
    ResultadoTipo: ResultadoTipo
    Resultados_Quant: Optional[str] = None
    Resultados_Qual: Optional[str] = None
    NívelEvidência: NivelEvidencia
    Limitações_Artigo: str

    # OPCIONAL
    Observação: Optional[str] = None

    # QUOTES
    Quotes: list[Quote] = Field(..., min_length=3, max_length=8)

    class Config:
        populate_by_name = True

    @field_validator("Complexidade_Justificativa")
    @classmethod
    def validate_complexidade_justificativa(cls, v: str) -> str:
        """Regra 9: Deve ter F1/F2/F3."""
        if not re.search(r"F1\s*=", v) or not re.search(r"F2\s*=", v) or not re.search(r"F3\s*=", v):
            raise ValueError("Complexidade_Justificativa deve conter F1=, F2=, F3=")
        return v

    @field_validator("Mecanismo_Estruturado")
    @classmethod
    def validate_mecanismo_estruturado(cls, v: str) -> str:
        """Regra 6: Deve ser string única com →."""
        if "\n" in v.strip():
            raise ValueError("Mecanismo_Estruturado deve ser string única (sem quebras de linha)")
        if "→" not in v:
            raise ValueError("Mecanismo_Estruturado deve conter '→' (Entrada → Transformação → Mediação → Resultado)")
        return v

    @field_validator("Mecanismo_Inferido")
    @classmethod
    def validate_mecanismo_inferido(cls, v: Optional[str]) -> Optional[str]:
        """Regra 5: Cada sentença deve iniciar com INFERIDO:"""
        if v and v != "NR":
            sentences = [s.strip() for s in v.split(".") if s.strip()]
            for sentence in sentences:
                if sentence and not sentence.startswith("INFERIDO:"):
                    raise ValueError(f"Cada sentença de Mecanismo_Inferido deve iniciar com 'INFERIDO:'. Encontrado: '{sentence[:50]}...'")
        return v

    @model_validator(mode="after")
    def validate_cross_field_rules(self):
        """Validações que envolvem múltiplos campos."""

        # Regra 1: TipoRisco ≠ NR → ObjetoCrítico preenchido
        if self.TipoRisco_SCRM != "NR" and not self.ObjetoCrítico:
            raise ValueError("Regra 1: Se TipoRisco_SCRM ≠ 'NR', ObjetoCrítico DEVE estar preenchido")

        # Regra 2: ResultadoTipo = Quantitativo → Resultados_Quant com formato correto
        if self.ResultadoTipo in ["Quantitativo", "Misto"]:
            if not self.Resultados_Quant or self.Resultados_Quant == "NR":
                raise ValueError("Regra 2: Se ResultadoTipo é Quantitativo/Misto, Resultados_Quant deve estar preenchido")

        # Regra 3: Maturidade = Produção → NívelEvidência compatível
        if self.Maturidade == "Produção":
            valid_evidences = ["Estudo de caso real", "Experimento com dados reais"]
            if self.NívelEvidência not in valid_evidences:
                raise ValueError(f"Regra 3: Se Maturidade='Produção', NívelEvidência deve ser {valid_evidences}")

        # Regra 4: ClasseIA = Híbrido → técnicas especificadas
        if self.ClasseIA == "Híbrido":
            if ";" not in self.FamíliaModelo and "+" not in self.FamíliaModelo:
                raise ValueError("Regra 4: Se ClasseIA='Híbrido', FamíliaModelo deve listar múltiplas técnicas")

        # Regra 8: Simulação sintética → Maturidade não pode ser Produção/Piloto
        if self.NívelEvidência == "Simulação com dados sintéticos":
            if self.Maturidade in ["Produção", "Piloto"]:
                raise ValueError("Regra 8: Se NívelEvidência='Simulação com dados sintéticos', Maturidade não pode ser Produção/Piloto")

        return self
```

---

### Task 7: Criar Validador de Regras de Negócio

**Files:**
- Create: `system/src/validators.py`

**Step 1: Criar validador das 12 regras**

```python
"""Validador das 12 regras de negócio do Guia v3.3."""

import re
import yaml
from dataclasses import dataclass
from typing import Any
from .schemas import ExtractionSchema
from pydantic import ValidationError


@dataclass
class ValidationResult:
    """Resultado de validação."""
    is_valid: bool
    errors: list[str]
    warnings: list[str]

    def __str__(self) -> str:
        if self.is_valid:
            return "✅ APROVADO"
        return f"❌ REPROVADO\n  Erros: {self.errors}"


class YAMLValidator:
    """Validador completo para YAML de extração."""

    LIMITATION_KEYWORDS = ["limit", "restrict", "challeng", "only", "constrain", "caveat"]

    def validate(self, yaml_content: str) -> ValidationResult:
        """Valida YAML em 3 camadas: parse, schema, regras."""
        errors = []
        warnings = []

        # Camada 1: Parse YAML
        try:
            data = yaml.safe_load(yaml_content)
        except yaml.YAMLError as e:
            return ValidationResult(
                is_valid=False,
                errors=[f"YAML inválido: {str(e)}"],
                warnings=[]
            )

        if not isinstance(data, dict):
            return ValidationResult(
                is_valid=False,
                errors=["YAML deve ser um dicionário"],
                warnings=[]
            )

        # Camada 2: Schema Pydantic
        try:
            extraction = ExtractionSchema(**data)
        except ValidationError as e:
            for error in e.errors():
                field = ".".join(str(loc) for loc in error["loc"])
                errors.append(f"Schema - {field}: {error['msg']}")
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

        # Camada 3: Regras adicionais de negócio
        self._validate_rule_11(data, errors, warnings)
        self._validate_quotes(data, errors, warnings)
        self._validate_narratives_length(data, warnings)

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )

    def _validate_rule_11(self, data: dict, errors: list, warnings: list):
        """Regra 11: Se Limitações = NR, verificar ausência de keywords."""
        limitacoes = data.get("Limitações_Artigo", "").strip()
        if limitacoes == "NR":
            # Verificar no texto completo se há menções a limitações
            warnings.append(
                "Regra 11: Limitações_Artigo='NR' - confirme que o artigo não menciona: "
                "limit*, restrict*, challeng*, only"
            )

    def _validate_quotes(self, data: dict, errors: list, warnings: list):
        """Validar quotes: quantidade e presença de Mecanismo."""
        quotes = data.get("Quotes", [])

        if len(quotes) < 3:
            errors.append(f"Quotes insuficientes: {len(quotes)} < 3 mínimo")
        elif len(quotes) > 8:
            errors.append(f"Quotes excedentes: {len(quotes)} > 8 máximo")

        # Verificar se há quote de Mecanismo
        has_mechanism_quote = any(q.get("TipoQuote") == "Mecanismo" for q in quotes)
        if not has_mechanism_quote:
            warnings.append("Recomendado: incluir pelo menos 1 quote de tipo 'Mecanismo'")

    def _validate_narratives_length(self, data: dict, warnings: list):
        """Verificar extensão dos campos narrativos."""
        problema = data.get("ProblemaNegócio_Contexto", "")
        lines = len([l for l in problema.split("\n") if l.strip()])
        if lines < 3:
            warnings.append(f"ProblemaNegócio_Contexto curto: {lines} linhas (mínimo 3)")
        elif lines > 6:
            warnings.append(f"ProblemaNegócio_Contexto longo: {lines} linhas (máximo 6)")


def validate_yaml(yaml_content: str) -> ValidationResult:
    """Função helper para validação rápida."""
    validator = YAMLValidator()
    return validator.validate(yaml_content)
```

---

## FASE 3: Módulos Python

### Task 8: Criar Cliente PDF com Visão

**Files:**
- Create: `system/src/pdf_vision.py`

**Step 1: Criar módulo de renderização PDF**

```python
"""Renderização de PDF como imagens para LLM com visão."""

import base64
from pathlib import Path
from typing import Generator
import fitz  # PyMuPDF


def extract_hybrid(
    pdf_path: Path,
    output_dir: Path,
    dpi: int = 300
) -> list[Path]:
    """
    Renderiza todas as páginas do PDF como imagens PNG.

    Args:
        pdf_path: Caminho do PDF
        output_dir: Diretório para salvar imagens
        dpi: Resolução (default 300)

    Returns:
        Lista de caminhos das imagens geradas
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(pdf_path)
    image_paths = []

    # Matriz de escala para DPI desejado
    zoom = dpi / 72  # 72 é o DPI padrão do PDF
    matrix = fitz.Matrix(zoom, zoom)

    for page_num in range(len(doc)):
        page = doc[page_num]
        pix = page.get_pixmap(matrix=matrix)

        image_path = output_dir / f"page_{page_num + 1:03d}.png"
        pix.save(str(image_path))
        image_paths.append(image_path)

    doc.close()
    return image_paths


def encode_image_base64(image_path: Path) -> str:
    """Codifica imagem em base64 para API."""
    with open(image_path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")


def get_images_for_llm(
    image_paths: list[Path],
    max_pages: int | None = None
) -> list[dict]:
    """
    Prepara imagens no formato esperado pelas APIs de visão.

    Returns:
        Lista de dicts com type e base64 data
    """
    paths = image_paths[:max_pages] if max_pages else image_paths

    return [
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": encode_image_base64(p)
            }
        }
        for p in paths
    ]


def get_pdf_info(pdf_path: Path) -> dict:
    """Retorna informações básicas do PDF."""
    doc = fitz.open(pdf_path)
    info = {
        "num_pages": len(doc),
        "title": doc.metadata.get("title", ""),
        "author": doc.metadata.get("author", ""),
    }
    doc.close()
    return info
```

---

### Task 9: Criar Cliente LLM Unificado

**Files:**
- Create: `system/src/llm_client.py`

**Step 1: Criar cliente com suporte a Anthropic e OpenAI**

```python
"""Cliente unificado para LLMs (Anthropic e OpenAI)."""

import json
from pathlib import Path
from typing import Literal
from anthropic import Anthropic
from openai import OpenAI
from .config import llm_config


Provider = Literal["anthropic", "openai"]


class LLMClient:
    """Cliente unificado para chamadas de LLM."""

    def __init__(self):
        self.anthropic = Anthropic(api_key=llm_config.ANTHROPIC_API_KEY)
        self.openai = OpenAI(api_key=llm_config.OPENAI_API_KEY)

    def extract_with_vision(
        self,
        images: list[dict],
        prompt: str,
        artigo_id: str,
        provider: Provider = "anthropic"
    ) -> str:
        """
        Extrai dados do artigo usando LLM com visão.

        Args:
            images: Lista de imagens em formato base64
            prompt: Prompt do Guia v3.3
            artigo_id: ID do artigo (ART_001, etc.)
            provider: "anthropic" ou "openai"

        Returns:
            Resposta do LLM (texto com YAML)
        """
        if provider == "anthropic":
            return self._call_anthropic_vision(images, prompt, artigo_id)
        else:
            return self._call_openai_vision(images, prompt, artigo_id)

    def _call_anthropic_vision(
        self,
        images: list[dict],
        prompt: str,
        artigo_id: str
    ) -> str:
        """Chamada para Claude com visão."""
        # Construir conteúdo com imagens + texto
        content = []

        # Adicionar imagens
        for img in images:
            content.append(img)

        # Adicionar prompt
        content.append({
            "type": "text",
            "text": f"ArtigoID: {artigo_id}\n\n{prompt}\n\nAnalise as páginas acima e extraia os dados CIMO. Retorne SOMENTE o YAML."
        })

        response = self.anthropic.messages.create(
            model=llm_config.ANTHROPIC_MODEL,
            max_tokens=8000,
            messages=[
                {"role": "user", "content": content}
            ]
        )

        return response.content[0].text

    def _call_openai_vision(
        self,
        images: list[dict],
        prompt: str,
        artigo_id: str
    ) -> str:
        """Chamada para GPT-4o com visão."""
        # Converter formato de imagem para OpenAI
        content = []

        for img in images:
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{img['source']['media_type']};base64,{img['source']['data']}",
                    "detail": "high"
                }
            })

        content.append({
            "type": "text",
            "text": f"ArtigoID: {artigo_id}\n\n{prompt}\n\nAnalise as páginas acima e extraia os dados CIMO. Retorne SOMENTE o YAML."
        })

        response = self.openai.chat.completions.create(
            model=llm_config.OPENAI_MODEL,
            max_tokens=8000,
            messages=[
                {"role": "user", "content": content}
            ]
        )

        return response.choices[0].message.content

    def repair_yaml(
        self,
        yaml_content: str,
        errors: list[str],
        template: str,
        provider: Provider = "openai"
    ) -> str:
        """
        Repara YAML com erros de validação.

        Args:
            yaml_content: YAML com erros
            errors: Lista de erros encontrados
            template: Template YAML de referência
            provider: LLM para usar (default: openai para repairs)

        Returns:
            YAML corrigido
        """
        repair_prompt = f"""Corrija o YAML abaixo que apresentou os seguintes erros de validação:

ERROS:
{chr(10).join(f"- {e}" for e in errors)}

YAML COM ERROS:
```yaml
{yaml_content}
```

TEMPLATE DE REFERÊNCIA:
```yaml
{template}
```

INSTRUÇÕES:
1. Corrija APENAS os campos com erro
2. Mantenha todos os outros campos intactos
3. Retorne SOMENTE o YAML corrigido, sem explicações
4. Use os nomes de campos EXATOS do template
"""

        if provider == "openai":
            response = self.openai.chat.completions.create(
                model=llm_config.OPENAI_MODEL,
                max_tokens=8000,
                messages=[
                    {"role": "system", "content": "Você é um assistente especializado em corrigir YAML. Retorne apenas YAML válido."},
                    {"role": "user", "content": repair_prompt}
                ]
            )
            return response.choices[0].message.content
        else:
            response = self.anthropic.messages.create(
                model=llm_config.ANTHROPIC_MODEL,
                max_tokens=8000,
                messages=[
                    {"role": "user", "content": repair_prompt}
                ]
            )
            return response.content[0].text


def extract_yaml_from_response(response: str) -> str:
    """Extrai bloco YAML de uma resposta do LLM."""
    # Tentar extrair de code block
    if "```yaml" in response:
        start = response.find("```yaml") + 7
        end = response.find("```", start)
        return response[start:end].strip()
    elif "```" in response:
        start = response.find("```") + 3
        end = response.find("```", start)
        return response[start:end].strip()

    # Se não tiver code block, assumir que é YAML puro
    # Remover possível texto antes do ---
    if "---" in response:
        start = response.find("---")
        return response[start:].strip()

    return response.strip()
```

---

### Task 10: Criar Módulo de Consolidação

**Files:**
- Create: `system/src/consolidate.py`

**Step 1: Criar conversor YAML → Excel**

```python
"""Consolidação de YAMLs em Excel."""

import yaml
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Any


def load_yaml(yaml_path: Path) -> dict:
    """Carrega um arquivo YAML."""
    with open(yaml_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def flatten_extraction(data: dict) -> dict:
    """Achata estrutura do YAML para linha de DataFrame."""
    flat = {}

    # Campos simples
    simple_fields = [
        "ArtigoID", "Ano", "TipoPublicação", "Referência_Curta", "DOI",
        "SegmentoO&G", "SegmentoO&G_Confiança", "Ambiente", "Complexidade",
        "Complexidade_Justificativa", "ProcessoSCM_Alvo", "TipoRisco_SCRM",
        "ObjetoCrítico", "ClasseIA", "ClasseIA_Confiança", "TarefaAnalítica",
        "FamíliaModelo", "TipoDado", "Maturidade", "Maturidade_Confiança",
        "CategoriaMecanismo", "Mecanismo_Fonte", "Mecanismo_Estruturado",
        "ResultadoTipo", "Resultados_Quant", "Resultados_Qual",
        "NívelEvidência"
    ]

    for field in simple_fields:
        flat[field] = data.get(field, "")

    # Campos narrativos (limpar quebras de linha)
    narrative_fields = [
        "ProblemaNegócio_Contexto", "Intervenção_Descrição", "Dados_Descrição",
        "Mecanismo_Declarado", "Mecanismo_Inferido", "Limitações_Artigo", "Observação"
    ]

    for field in narrative_fields:
        value = data.get(field, "")
        if isinstance(value, str):
            flat[field] = " ".join(value.split())  # Normaliza espaços
        else:
            flat[field] = str(value) if value else ""

    # Quotes como texto concatenado
    quotes = data.get("Quotes", [])
    flat["Quotes_Count"] = len(quotes)
    flat["Quotes_Text"] = " | ".join(
        f"[{q.get('TipoQuote', '')}] {q.get('Trecho', '')[:100]}..."
        for q in quotes
    )

    return flat


def consolidate_yamls(
    yamls_dir: Path,
    output_excel: Path,
    output_audit: Path | None = None
) -> pd.DataFrame:
    """
    Consolida todos os YAMLs em um Excel.

    Args:
        yamls_dir: Diretório com YAMLs aprovados
        output_excel: Caminho do Excel de saída
        output_audit: Caminho opcional do CSV de auditoria

    Returns:
        DataFrame consolidado
    """
    rows = []
    errors = []

    yaml_files = sorted(yamls_dir.glob("*.yaml"))

    for yaml_path in yaml_files:
        try:
            data = load_yaml(yaml_path)
            flat = flatten_extraction(data)
            flat["_source_file"] = yaml_path.name
            rows.append(flat)
        except Exception as e:
            errors.append({
                "file": yaml_path.name,
                "error": str(e)
            })

    # Criar DataFrame
    df = pd.DataFrame(rows)

    # Ordenar por ArtigoID
    if "ArtigoID" in df.columns:
        df = df.sort_values("ArtigoID")

    # Salvar Excel
    output_excel.parent.mkdir(parents=True, exist_ok=True)

    with pd.ExcelWriter(output_excel, engine="openpyxl") as writer:
        # Aba principal
        df.drop(columns=["_source_file"], errors="ignore").to_excel(
            writer, sheet_name="Extrações", index=False
        )

        # Aba de quotes expandida
        quotes_rows = []
        for yaml_path in yaml_files:
            try:
                data = load_yaml(yaml_path)
                for q in data.get("Quotes", []):
                    quotes_rows.append({
                        "ArtigoID": data.get("ArtigoID", ""),
                        "QuoteID": q.get("QuoteID", ""),
                        "TipoQuote": q.get("TipoQuote", ""),
                        "Trecho": q.get("Trecho", ""),
                        "Página": q.get("Página", "")
                    })
            except:
                pass

        if quotes_rows:
            pd.DataFrame(quotes_rows).to_excel(
                writer, sheet_name="Quotes", index=False
            )

        # Aba de metadados
        meta_df = pd.DataFrame([{
            "Data Consolidação": datetime.now().isoformat(),
            "Total Artigos": len(df),
            "Versão Guia": "v3.3",
            "Erros": len(errors)
        }])
        meta_df.to_excel(writer, sheet_name="Metadata", index=False)

    # Salvar auditoria se solicitado
    if output_audit and errors:
        pd.DataFrame(errors).to_csv(output_audit, index=False)

    return df


def generate_audit_report(
    yamls_dir: Path,
    output_path: Path
) -> pd.DataFrame:
    """
    Gera relatório de auditoria por regra.

    Returns:
        DataFrame com status de cada regra por artigo
    """
    # Implementação simplificada - pode ser expandida
    from .validators import YAMLValidator

    validator = YAMLValidator()
    results = []

    for yaml_path in sorted(yamls_dir.glob("*.yaml")):
        with open(yaml_path, "r", encoding="utf-8") as f:
            content = f.read()

        result = validator.validate(content)

        results.append({
            "ArtigoID": yaml_path.stem,
            "Status": "APROVADO" if result.is_valid else "REPROVADO",
            "Erros": "; ".join(result.errors) if result.errors else "",
            "Warnings": "; ".join(result.warnings) if result.warnings else ""
        })

    df = pd.DataFrame(results)
    df.to_csv(output_path, index=False)
    return df
```

---

### Task 11: Criar Gerador de Mapping CSV

**Files:**
- Modify: `system/src/config.py` (adicionar função)

**Step 1: Adicionar função para gerar mapping.csv**

```python
# Adicionar ao final de config.py

import csv
from pathlib import Path


def generate_mapping_csv(
    articles_dir: Path,
    output_path: Path,
    overwrite: bool = False
) -> Path:
    """
    Gera mapping.csv com ArtigoID para cada PDF.

    Args:
        articles_dir: Pasta com PDFs
        output_path: Caminho do CSV de saída
        overwrite: Se True, sobrescreve existente

    Returns:
        Path do CSV gerado
    """
    if output_path.exists() and not overwrite:
        print(f"Mapping já existe: {output_path}")
        return output_path

    # Listar PDFs em ordem alfabética
    pdfs = sorted(articles_dir.glob("*.pdf"))

    if not pdfs:
        raise ValueError(f"Nenhum PDF encontrado em {articles_dir}")

    # Gerar mapeamento
    rows = []
    for i, pdf in enumerate(pdfs, start=1):
        rows.append({
            "ArtigoID": f"ART_{i:03d}",
            "Arquivo": pdf.name,
            "Processado": "Não",
            "Status": ""
        })

    # Salvar CSV
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["ArtigoID", "Arquivo", "Processado", "Status"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Mapping gerado: {output_path} ({len(rows)} artigos)")
    return output_path


def load_mapping(mapping_path: Path) -> list[dict]:
    """Carrega mapping.csv como lista de dicts."""
    with open(mapping_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def update_mapping_status(
    mapping_path: Path,
    artigo_id: str,
    processado: bool,
    status: str
):
    """Atualiza status de um artigo no mapping."""
    rows = load_mapping(mapping_path)

    for row in rows:
        if row["ArtigoID"] == artigo_id:
            row["Processado"] = "Sim" if processado else "Não"
            row["Status"] = status
            break

    with open(mapping_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["ArtigoID", "Arquivo", "Processado", "Status"])
        writer.writeheader()
        writer.writerows(rows)
```

---

## FASE 4: Notebooks

### Task 12: Criar Notebook 01_Configuracao

**Files:**
- Create: `system/notebooks/01_Configuracao.ipynb`

**Step 1: Criar notebook de configuração**

```python
# Célula 1 - Título
"""
# 01 - Configuração SAEC-O&G

Este notebook configura o ambiente para extração CIMO.

**Executar uma vez no início do projeto.**
"""

# Célula 2 - Imports e Setup de Path
import sys
from pathlib import Path

# Adicionar src ao path
SYSTEM_DIR = Path.cwd().parent if "notebooks" in str(Path.cwd()) else Path.cwd() / "system"
SRC_DIR = SYSTEM_DIR / "src"
sys.path.insert(0, str(SRC_DIR))

print(f"System dir: {SYSTEM_DIR}")
print(f"Src dir: {SRC_DIR}")

# Célula 3 - Verificar Dependências
"""## 1. Verificar Dependências"""

import importlib

deps = [
    "dotenv", "yaml", "pydantic", "fitz", "PIL",
    "anthropic", "openai", "pandas", "openpyxl"
]

for dep in deps:
    try:
        importlib.import_module(dep)
        print(f"✅ {dep}")
    except ImportError:
        print(f"❌ {dep} - execute: pip install {dep}")

# Célula 4 - Carregar Configuração
"""## 2. Carregar Configuração"""

from config import paths, llm_config

# Verificar paths
print("📁 Caminhos configurados:")
print(f"  Project root: {paths.PROJECT_ROOT}")
print(f"  Articles: {paths.ARTICLES}")
print(f"  Outputs: {paths.OUTPUTS}")

# Criar diretórios
paths.ensure_dirs()
print("\n✅ Diretórios criados/verificados")

# Célula 5 - Verificar APIs
"""## 3. Verificar APIs"""

errors = llm_config.validate()

if errors:
    print("❌ Erros de configuração:")
    for e in errors:
        print(f"  - {e}")
    print("\n⚠️ Edite o arquivo .env com suas chaves de API")
else:
    print("✅ APIs configuradas")
    print(f"  Anthropic: {llm_config.ANTHROPIC_MODEL}")
    print(f"  OpenAI: {llm_config.OPENAI_MODEL}")
    print(f"  Two-pass: {llm_config.USE_TWO_PASS}")

# Célula 6 - Gerar Mapping
"""## 4. Gerar Mapping de Artigos"""

from config import generate_mapping_csv

mapping_path = generate_mapping_csv(
    articles_dir=paths.ARTICLES,
    output_path=paths.MAPPING_CSV,
    overwrite=False  # Mude para True para regenerar
)

# Mostrar preview
import pandas as pd
df = pd.read_csv(mapping_path)
print(f"\n📊 {len(df)} artigos mapeados:")
df.head(10)

# Célula 7 - Resumo
"""## 5. Resumo da Configuração"""

print("=" * 50)
print("SAEC-O&G - Configuração Completa")
print("=" * 50)
print(f"Artigos para processar: {len(df)}")
print(f"Modo: {'Two-pass (Claude + GPT-4o)' if llm_config.USE_TWO_PASS else 'Single-pass'}")
print(f"Mapping: {mapping_path}")
print(f"Outputs: {paths.OUTPUTS}")
print("=" * 50)
print("\n✅ Pronto para executar 02_Ingestao.ipynb")
```

---

### Task 13: Criar Notebook 02_Ingestao

**Files:**
- Create: `system/notebooks/02_Ingestao.ipynb`

**Step 1: Criar notebook de ingestão**

```python
# Célula 1 - Título
"""
# 02 - Ingestão de PDFs

Este notebook renderiza PDFs como imagens para o LLM com visão.
"""

# Célula 2 - Setup
import sys
from pathlib import Path

SYSTEM_DIR = Path.cwd().parent if "notebooks" in str(Path.cwd()) else Path.cwd() / "system"
sys.path.insert(0, str(SYSTEM_DIR / "src"))

from config import paths, load_mapping
from pdf_vision import extract_hybrid, get_pdf_info

# Célula 3 - Carregar Mapping
"""## 1. Carregar Artigos"""

mapping = load_mapping(paths.MAPPING_CSV)
print(f"📚 {len(mapping)} artigos no mapping")

# Filtrar não processados
pending = [m for m in mapping if m["Processado"] != "Sim"]
print(f"⏳ {len(pending)} pendentes de ingestão")

# Célula 4 - Função de Ingestão
"""## 2. Função de Ingestão"""

def ingest_article(artigo_id: str, arquivo: str) -> dict:
    """Ingere um artigo: PDF → imagens."""
    pdf_path = paths.ARTICLES / arquivo
    work_dir = paths.WORK / artigo_id
    pages_dir = work_dir / "pages"

    # Verificar se já foi ingerido
    if pages_dir.exists() and list(pages_dir.glob("*.png")):
        existing = list(pages_dir.glob("*.png"))
        print(f"  ⏭️ Já ingerido ({len(existing)} páginas)")
        return {"status": "cached", "pages": len(existing)}

    # Info do PDF
    info = get_pdf_info(pdf_path)
    print(f"  📄 {info['num_pages']} páginas")

    # Renderizar
    image_paths = extract_hybrid(pdf_path, pages_dir, dpi=300)
    print(f"  ✅ {len(image_paths)} imagens geradas")

    return {"status": "success", "pages": len(image_paths)}

# Célula 5 - Ingerir Artigo Teste (Piloto)
"""## 3. Ingerir Artigo Teste"""

# Pegar primeiro artigo para teste
test_article = mapping[0]
print(f"🧪 Artigo teste: {test_article['ArtigoID']}")
print(f"   Arquivo: {test_article['Arquivo'][:50]}...")

result = ingest_article(test_article["ArtigoID"], test_article["Arquivo"])
print(f"\n   Resultado: {result}")

# Célula 6 - Ingerir Todos (Batch)
"""## 4. Ingerir Todos os Artigos (Batch)

⚠️ Execute apenas quando pronto para processar todos.
"""

# DESCOMENTE PARA EXECUTAR BATCH
# from tqdm.notebook import tqdm
#
# for article in tqdm(mapping, desc="Ingerindo"):
#     print(f"\n{article['ArtigoID']}: {article['Arquivo'][:40]}...")
#     try:
#         result = ingest_article(article["ArtigoID"], article["Arquivo"])
#     except Exception as e:
#         print(f"  ❌ Erro: {e}")

print("\n✅ Ingestão completa. Próximo: 03_Extracao_LLM.ipynb")
```

---

### Task 14: Criar Notebook 03_Extracao_LLM (Principal)

**Files:**
- Create: `system/notebooks/03_Extracao_LLM.ipynb`

**Step 1: Criar notebook principal de extração**

```python
# Célula 1 - Título
"""
# 03 - Extração LLM (Principal)

Este é o notebook principal para extração CIMO.

**Modos:**
- `interativo`: processa 1 artigo, mostra resultado, espera aprovação
- `batch`: processa todos automaticamente
"""

# Célula 2 - Configuração
import sys
from pathlib import Path
from IPython.display import display, Markdown, HTML
import ipywidgets as widgets

SYSTEM_DIR = Path.cwd().parent if "notebooks" in str(Path.cwd()) else Path.cwd() / "system"
sys.path.insert(0, str(SYSTEM_DIR / "src"))

from config import paths, llm_config, load_mapping, update_mapping_status
from pdf_vision import get_images_for_llm
from llm_client import LLMClient, extract_yaml_from_response
from validators import validate_yaml, ValidationResult

# Célula 3 - Parâmetros
"""## 1. Parâmetros de Execução"""

# ========== CONFIGURAR AQUI ==========
MODO = "interativo"  # "interativo" ou "batch"
ARTIGO_TESTE = "ART_001"  # Para modo interativo/piloto
PROVIDER_EXTRACAO = "anthropic"  # "anthropic" ou "openai"
PROVIDER_REPAIR = "openai"  # Para repair loop
MAX_REPAIR_ATTEMPTS = 3
# =====================================

print(f"📋 Modo: {MODO}")
print(f"🤖 Extração: {PROVIDER_EXTRACAO}")
print(f"🔧 Repair: {PROVIDER_REPAIR}")

# Célula 4 - Carregar Prompt
"""## 2. Carregar Prompt do Guia"""

prompt_path = paths.GUIA_PROMPT
with open(prompt_path, "r", encoding="utf-8") as f:
    GUIA_PROMPT = f.read()

print(f"✅ Prompt carregado: {len(GUIA_PROMPT)} caracteres")

# Célula 5 - Inicializar Cliente LLM
"""## 3. Inicializar Cliente LLM"""

client = LLMClient()
print("✅ Cliente LLM inicializado")

# Célula 6 - Função de Extração
"""## 4. Função de Extração"""

def extract_article(artigo_id: str) -> tuple[str, ValidationResult]:
    """
    Executa extração completa de um artigo.

    Returns:
        (yaml_content, validation_result)
    """
    work_dir = paths.WORK / artigo_id
    pages_dir = work_dir / "pages"

    # Carregar imagens
    image_paths = sorted(pages_dir.glob("*.png"))
    if not image_paths:
        raise ValueError(f"Nenhuma imagem encontrada em {pages_dir}")

    print(f"📷 Carregando {len(image_paths)} páginas...")
    images = get_images_for_llm(image_paths)

    # Chamar LLM para extração
    print(f"🤖 Chamando {PROVIDER_EXTRACAO}...")
    response = client.extract_with_vision(
        images=images,
        prompt=GUIA_PROMPT,
        artigo_id=artigo_id,
        provider=PROVIDER_EXTRACAO
    )

    # Extrair YAML da resposta
    yaml_content = extract_yaml_from_response(response)

    # Salvar draft
    draft_path = work_dir / "draft.yaml"
    with open(draft_path, "w", encoding="utf-8") as f:
        f.write(yaml_content)
    print(f"💾 Draft salvo: {draft_path}")

    # Validar
    print("🔍 Validando...")
    result = validate_yaml(yaml_content)

    return yaml_content, result


def repair_yaml_loop(
    yaml_content: str,
    errors: list[str],
    artigo_id: str,
    max_attempts: int = 3
) -> tuple[str, ValidationResult]:
    """
    Loop de repair até validar ou esgotar tentativas.
    """
    work_dir = paths.WORK / artigo_id

    # Carregar template para referência
    # (extrair do prompt ou ter separado)
    template = "..."  # Simplificado

    for attempt in range(1, max_attempts + 1):
        print(f"🔧 Repair tentativa {attempt}/{max_attempts}...")

        repaired = client.repair_yaml(
            yaml_content=yaml_content,
            errors=errors,
            template=template,
            provider=PROVIDER_REPAIR
        )

        repaired_yaml = extract_yaml_from_response(repaired)

        # Salvar tentativa
        repair_path = work_dir / f"repair_attempt_{attempt:02d}.yaml"
        with open(repair_path, "w", encoding="utf-8") as f:
            f.write(repaired_yaml)

        # Validar
        result = validate_yaml(repaired_yaml)

        if result.is_valid:
            print(f"✅ Repair bem-sucedido na tentativa {attempt}")
            return repaired_yaml, result

        yaml_content = repaired_yaml
        errors = result.errors

    print(f"❌ Repair falhou após {max_attempts} tentativas")
    return yaml_content, result

# Célula 7 - Exibição de Resultados
"""## 5. Funções de Exibição"""

def display_yaml(yaml_content: str):
    """Exibe YAML com syntax highlighting."""
    display(Markdown(f"```yaml\n{yaml_content}\n```"))

def display_validation(result: ValidationResult):
    """Exibe resultado da validação."""
    if result.is_valid:
        display(HTML("<h3 style='color: green'>✅ VALIDAÇÃO: APROVADO</h3>"))
    else:
        display(HTML("<h3 style='color: red'>❌ VALIDAÇÃO: REPROVADO</h3>"))
        display(HTML("<b>Erros:</b><ul>" + "".join(f"<li>{e}</li>" for e in result.errors) + "</ul>"))

    if result.warnings:
        display(HTML("<b>Avisos:</b><ul>" + "".join(f"<li>{w}</li>" for w in result.warnings) + "</ul>"))

# Célula 8 - Extração Interativa
"""## 6. Extração Interativa (Piloto)

Execute a célula abaixo para processar o artigo teste.
"""

# Executar extração
print(f"🚀 Extraindo {ARTIGO_TESTE}...")
yaml_content, result = extract_article(ARTIGO_TESTE)

# Exibir resultado
print("\n" + "="*50)
print("RESULTADO DA EXTRAÇÃO")
print("="*50 + "\n")

display_yaml(yaml_content)
display_validation(result)

# Célula 9 - Ações Pós-Extração
"""## 7. Ações"""

def save_approved(artigo_id: str, yaml_content: str):
    """Salva YAML aprovado."""
    # Salvar em work/
    work_path = paths.WORK / artigo_id / "extraction.yaml"
    with open(work_path, "w", encoding="utf-8") as f:
        f.write(yaml_content)

    # Copiar para yamls/
    final_path = paths.YAMLS / f"{artigo_id}.yaml"
    with open(final_path, "w", encoding="utf-8") as f:
        f.write(yaml_content)

    # Atualizar mapping
    update_mapping_status(paths.MAPPING_CSV, artigo_id, True, "Aprovado")

    print(f"✅ Salvo: {final_path}")

# Botões de ação
btn_approve = widgets.Button(description="✅ Aprovar", button_style="success")
btn_repair = widgets.Button(description="🔧 Reparar", button_style="warning")
btn_skip = widgets.Button(description="⏭️ Pular", button_style="")

def on_approve(b):
    save_approved(ARTIGO_TESTE, yaml_content)

def on_repair(b):
    global yaml_content, result
    yaml_content, result = repair_yaml_loop(yaml_content, result.errors, ARTIGO_TESTE)
    display_yaml(yaml_content)
    display_validation(result)

def on_skip(b):
    update_mapping_status(paths.MAPPING_CSV, ARTIGO_TESTE, False, "Pulado")
    print("⏭️ Artigo pulado")

btn_approve.on_click(on_approve)
btn_repair.on_click(on_repair)
btn_skip.on_click(on_skip)

display(widgets.HBox([btn_approve, btn_repair, btn_skip]))

# Célula 10 - Batch Mode
"""## 8. Modo Batch

⚠️ Execute apenas após validar o prompt no modo piloto.
"""

# DESCOMENTE PARA EXECUTAR BATCH
# from tqdm.notebook import tqdm
#
# mapping = load_mapping(paths.MAPPING_CSV)
# pending = [m for m in mapping if m["Processado"] != "Sim"]
#
# print(f"🚀 Processando {len(pending)} artigos em batch...")
#
# for article in tqdm(pending, desc="Extraindo"):
#     artigo_id = article["ArtigoID"]
#     try:
#         yaml_content, result = extract_article(artigo_id)
#
#         if not result.is_valid:
#             yaml_content, result = repair_yaml_loop(
#                 yaml_content, result.errors, artigo_id
#             )
#
#         if result.is_valid:
#             save_approved(artigo_id, yaml_content)
#         else:
#             update_mapping_status(paths.MAPPING_CSV, artigo_id, False, "Falhou validação")
#
#     except Exception as e:
#         update_mapping_status(paths.MAPPING_CSV, artigo_id, False, f"Erro: {e}")
#         print(f"❌ {artigo_id}: {e}")
#
# print("\n✅ Batch completo!")
```

---

### Task 15: Criar Notebook 04_Validacao

**Files:**
- Create: `system/notebooks/04_Validacao.ipynb`

**Step 1: Criar notebook de validação standalone**

```python
# Célula 1 - Título
"""
# 04 - Validação de YAMLs

Notebook para validar YAMLs individualmente ou em lote.
Útil para re-validar após edições manuais.
"""

# Célula 2 - Setup
import sys
from pathlib import Path

SYSTEM_DIR = Path.cwd().parent if "notebooks" in str(Path.cwd()) else Path.cwd() / "system"
sys.path.insert(0, str(SYSTEM_DIR / "src"))

from config import paths
from validators import validate_yaml, YAMLValidator

# Célula 3 - Validar YAML Individual
"""## 1. Validar YAML Individual"""

# Carregar um YAML específico
artigo_id = "ART_001"
yaml_path = paths.YAMLS / f"{artigo_id}.yaml"

if yaml_path.exists():
    with open(yaml_path, "r", encoding="utf-8") as f:
        content = f.read()

    result = validate_yaml(content)
    print(f"Validação de {artigo_id}:")
    print(result)
else:
    print(f"Arquivo não encontrado: {yaml_path}")

# Célula 4 - Validar Todos
"""## 2. Validar Todos os YAMLs"""

import pandas as pd

results = []
for yaml_path in sorted(paths.YAMLS.glob("*.yaml")):
    with open(yaml_path, "r", encoding="utf-8") as f:
        content = f.read()

    result = validate_yaml(content)
    results.append({
        "ArtigoID": yaml_path.stem,
        "Status": "✅" if result.is_valid else "❌",
        "Erros": len(result.errors),
        "Avisos": len(result.warnings)
    })

df = pd.DataFrame(results)
print(f"\n📊 Resumo: {len(df)} YAMLs")
print(f"   Aprovados: {len(df[df['Status'] == '✅'])}")
print(f"   Reprovados: {len(df[df['Status'] == '❌'])}")

df

# Célula 5 - Detalhes de Erros
"""## 3. Detalhes de Erros"""

for yaml_path in sorted(paths.YAMLS.glob("*.yaml")):
    with open(yaml_path, "r", encoding="utf-8") as f:
        content = f.read()

    result = validate_yaml(content)
    if not result.is_valid:
        print(f"\n❌ {yaml_path.stem}:")
        for e in result.errors:
            print(f"   - {e}")
```

---

### Task 16: Criar Notebook 05_Consolidacao

**Files:**
- Create: `system/notebooks/05_Consolidacao.ipynb`

**Step 1: Criar notebook de consolidação**

```python
# Célula 1 - Título
"""
# 05 - Consolidação

Gera Excel consolidado e relatórios de auditoria.
"""

# Célula 2 - Setup
import sys
from pathlib import Path
from datetime import datetime

SYSTEM_DIR = Path.cwd().parent if "notebooks" in str(Path.cwd()) else Path.cwd() / "system"
sys.path.insert(0, str(SYSTEM_DIR / "src"))

from config import paths
from consolidate import consolidate_yamls, generate_audit_report

# Célula 3 - Verificar YAMLs
"""## 1. Verificar YAMLs Disponíveis"""

yamls = list(paths.YAMLS.glob("*.yaml"))
print(f"📁 {len(yamls)} YAMLs prontos para consolidação")

for y in yamls[:5]:
    print(f"   - {y.name}")
if len(yamls) > 5:
    print(f"   ... e mais {len(yamls) - 5}")

# Célula 4 - Consolidar
"""## 2. Consolidar em Excel"""

timestamp = datetime.now().strftime("%Y%m%d_%H%M")
excel_path = paths.CONSOLIDATED / f"saec_consolidated_{timestamp}.xlsx"
audit_path = paths.CONSOLIDATED / f"audit_summary_{timestamp}.csv"

df = consolidate_yamls(
    yamls_dir=paths.YAMLS,
    output_excel=excel_path,
    output_audit=audit_path
)

print(f"\n✅ Excel gerado: {excel_path}")
print(f"✅ Auditoria: {audit_path}")
print(f"\n📊 {len(df)} artigos consolidados")

# Célula 5 - Preview
"""## 3. Preview dos Dados"""

# Mostrar primeiras colunas
cols_preview = ["ArtigoID", "Ano", "SegmentoO&G", "ClasseIA", "Maturidade"]
df[cols_preview].head(10)

# Célula 6 - Estatísticas
"""## 4. Estatísticas Descritivas"""

print("📊 Distribuição por SegmentoO&G:")
print(df["SegmentoO&G"].value_counts())

print("\n📊 Distribuição por ClasseIA:")
print(df["ClasseIA"].value_counts())

print("\n📊 Distribuição por Maturidade:")
print(df["Maturidade"].value_counts())

# Célula 7 - Relatório Final
"""## 5. Relatório Final"""

print("=" * 60)
print("SAEC-O&G - RELATÓRIO DE CONSOLIDAÇÃO")
print("=" * 60)
print(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
print(f"Total de artigos: {len(df)}")
print(f"Excel: {excel_path.name}")
print(f"Versão do Guia: v3.3")
print("=" * 60)
```

---

## FASE 5: Teste e Ajustes

### Task 17: Criar README

**Files:**
- Create: `system/README.md`

**Step 1: Criar guia de uso**

```markdown
# SAEC-O&G — Sistema Autônomo de Extração CIMO

Sistema para extração de dados CIMO (Context-Intervention-Mechanism-Outcome) de artigos científicos sobre IA + SCM/SCRM em Oil & Gas.

## Quick Start

### 1. Instalar Dependências

```bash
cd system
pip install -r requirements.txt
```

### 2. Configurar APIs

```bash
# Copiar template
cp .env.template .env

# Editar com suas chaves
notepad .env  # ou code .env
```

### 3. Executar Notebooks (em ordem)

1. **01_Configuracao.ipynb** — Setup inicial (executar uma vez)
2. **02_Ingestao.ipynb** — Converter PDFs em imagens
3. **03_Extracao_LLM.ipynb** — Extração principal
4. **04_Validacao.ipynb** — Validar YAMLs (opcional)
5. **05_Consolidacao.ipynb** — Gerar Excel final

## Fluxo Recomendado

### Fase Piloto (1 artigo)
1. Execute notebooks 01 e 02
2. No notebook 03, use `MODO = "interativo"` e `ARTIGO_TESTE = "ART_001"`
3. Revise o resultado e ajuste prompts se necessário
4. Repita até resultado satisfatório

### Fase Batch (demais artigos)
1. No notebook 03, descomente a seção "Modo Batch"
2. Execute para processar todos os artigos pendentes
3. Revise artigos que falharam validação
4. Execute notebook 05 para consolidar

## Estrutura de Pastas

```
system/
├── .env                 # API keys (NÃO versionar)
├── notebooks/           # Jupyter notebooks
├── prompts/             # Prompt do Guia v3.3
├── src/                 # Módulos Python
└── README.md

Extraction/
├── mapping.csv          # Mapeamento ArtigoID ↔ PDF
└── outputs/
    ├── work/            # Intermediários por artigo
    ├── yamls/           # YAMLs aprovados
    └── consolidated/    # Excel final
```

## Solução de Problemas

### API Key inválida
- Verifique se `.env` está preenchido corretamente
- Confirme que as chaves têm créditos disponíveis

### YAML inválido após extração
- O sistema tenta reparar automaticamente (3 tentativas)
- Se falhar, revise manualmente e re-valide com notebook 04

### Imagens não geradas
- Verifique se PyMuPDF está instalado: `pip install pymupdf`
- Confirme que os PDFs não estão corrompidos

## Custo Estimado

- ~$0.20-0.35 por artigo (Claude + GPT-4o)
- ~$8-14 para 38 artigos

## Versão

- SAEC-O&G: 1.0.0
- Guia de Extração: v3.3
- Data: Janeiro 2026
```

---

### Task 18: Executar Teste Piloto

**Step 1: Verificar setup completo**

```bash
# Na pasta system/
python -c "from src.config import paths, llm_config; print('OK')"
```

**Step 2: Executar notebooks em ordem**

1. Abrir Jupyter: `jupyter notebook`
2. Executar `01_Configuracao.ipynb`
3. Executar `02_Ingestao.ipynb` (apenas artigo teste)
4. Executar `03_Extracao_LLM.ipynb` em modo interativo
5. Revisar resultado e ajustar se necessário

**Step 3: Critérios de sucesso do piloto**

- [ ] YAML gerado é válido (parse OK)
- [ ] Schema Pydantic valida sem erros
- [ ] 12 regras passam (ou erros são reparáveis)
- [ ] Quotes são literais e têm página
- [ ] Mecanismo_Estruturado é string única
- [ ] Complexidade_Justificativa tem F1/F2/F3

---

## Resumo do Plano

| Fase | Tasks | Descrição | Tempo Est. |
|------|-------|-----------|------------|
| 1 | 1-4 | Setup inicial | 30 min |
| 2 | 5-7 | Prompt e validação | 45 min |
| 3 | 8-11 | Módulos Python | 60 min |
| 4 | 12-16 | Notebooks | 90 min |
| 5 | 17-18 | README e teste | 30 min |

**Total estimado: ~4-5 horas de implementação**

---

**Plano completo e salvo em `system/docs/2026-01-30-SAEC-OG-implementation-plan.md`.**

**Duas opções de execução:**

1. **Subagent-Driven (esta sessão)** — Eu executo task por task, revisamos entre cada uma, iteração rápida

2. **Manual** — Você executa as tasks seguindo o plano, me chama quando precisar de ajuda

**Qual abordagem você prefere?**
