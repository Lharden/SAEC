# SAEC-O&G — Documento de Design

**Data:** 2026-01-30
**Versão:** 1.0
**Status:** Aprovado para implementação

---

## 1. Visão Geral

**SAEC-O&G (Sistema Autônomo de Extração CIMO para Oil & Gas)** é uma ferramenta para processar artigos científicos, extraindo dados no framework CIMO (Contexto, Intervenção, Mecanismo, Outcome) e gerando YAML validado.

### 1.1 Objetivo

- Processar 38 artigos de uma RSL sobre IA + SCM/SCRM em Oil & Gas
- Gerar extrações consistentes, rastreáveis e auditáveis
- Saídas: YAML por artigo + Excel consolidado + relatórios de auditoria

### 1.2 Escopo

- Execução local com arquivos no disco
- Máximo 2 APIs externas: OpenAI e Anthropic
- Interface via Jupyter Notebooks para facilitar manutenção

---

## 2. Arquitetura

```
┌─────────────────────────────────────────────────────────────────┐
│                         SAEC-O&G                                │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
   ┌─────────┐          ┌─────────┐          ┌──────────┐
   │ system/ │          │02 T2/   │          │Extraction/│
   │         │          │         │          │          │
   │Notebooks│ ◄─lê───► │ PDFs    │ ─────►   │ outputs/ │
   │Prompts  │          │(38 arts)│          │ yamls/   │
   │.env     │          │         │          │ consol./ │
   └─────────┘          └─────────┘          └──────────┘
```

---

## 3. Decisões de Design

| Decisão | Escolha | Justificativa |
|---------|---------|---------------|
| Modo inicial | Interativo (piloto) | Validar prompt antes de batch |
| Modo produção | Batch após piloto | Eficiência após calibração |
| Formato código | Jupyter Notebooks | Facilita debug e iteração |
| Extração PDF | Vision-First | Captura texto + figuras + tabelas |
| LLM extração | Claude (Anthropic) | Melhor leitura longa, custo menor |
| LLM formatação | GPT-4o (OpenAI) | Melhor aderência a formato |
| Validação | 3 camadas | Parse + Schema + 12 Regras |
| Credenciais | Arquivo `.env` | Padrão seguro da indústria |
| Guia/Prompt | Versão condensada | Economia de tokens |

---

## 4. Estrutura de Pastas

```
00 Dados RSL/
│
├── 02 T2/                          # PDFs dos artigos
│   └── *.pdf (38 artigos)
│
├── Extraction/                      # Área de dados e outputs
│   ├── Guia_Extracao_v3_3.docx     # Original
│   ├── Masterdata_RSL_v3.xlsx      # Referência
│   ├── mapping.csv                  # ArtigoID ↔ PDF (auto-gerado)
│   │
│   └── outputs/
│       ├── work/                    # Intermediários por artigo
│       │   └── ART_XXX/
│       │       ├── pages/           # Imagens das páginas (PNG)
│       │       ├── draft.json       # Resposta bruta do LLM
│       │       ├── extraction.yaml  # YAML final aprovado
│       │       ├── validation.json  # Relatório de validação
│       │       └── log.txt          # Histórico de chamadas
│       │
│       ├── yamls/                   # Cópia dos YAMLs aprovados
│       │
│       └── consolidated/
│           ├── saec_consolidated.xlsx
│           └── audit_summary.csv
│
├── Guia v3.3.md                     # Versão completa
│
└── system/                          # Código e configuração
    ├── .env                         # API keys (não versionar)
    ├── docs/
    │   └── 2026-01-30-SAEC-OG-design.md
    ├── notebooks/
    │   ├── 01_Configuracao.ipynb
    │   ├── 02_Ingestao.ipynb
    │   ├── 03_Extracao_LLM.ipynb
    │   ├── 04_Validacao.ipynb
    │   └── 05_Consolidacao.ipynb
    ├── prompts/
    │   └── guia_v3_3_prompt.md      # Versão condensada
    ├── src/
    │   ├── __init__.py
    │   ├── config.py
    │   ├── pdf_vision.py
    │   ├── llm_client.py
    │   ├── validators.py
    │   └── consolidate.py
    └── README.md
```

---

## 5. Fluxo de Execução

### 5.1 Fase Piloto (1 artigo teste)

```
Artigo Teste ──► Extração LLM ──► Revisão Humana ──► Ajuste Prompt
                                        │
                    ◄───────────────────┘
                    (repete até resultado ideal)
```

### 5.2 Fase Batch (37 artigos restantes)

```
Para cada artigo:
  PDF ──► Imagens ──► Claude ──► Draft ──► GPT-4o ──► YAML ──► Validar
                                                                  │
                                            ┌─────────────────────┴─────────┐
                                            ▼                               ▼
                                       [APROVADO]                      [FALHOU]
                                            │                               │
                                       Salva YAML                    Revisão manual
```

### 5.3 Consolidação

```
Todos YAMLs aprovados ──► Excel consolidado + Relatório de auditoria
```

---

## 6. Estratégia de LLM (2 Passagens)

### 6.1 Passagem 1: Extração (Claude)

**Input:** Imagens do PDF + Guia condensado
**Tarefa:** Ler artigo, identificar CIMO, extrair evidências
**Output:** Draft estruturado (JSON)

**Por que Claude:**
- Melhor compreensão de texto longo e complexo
- Superior em inferir mecanismos não explícitos
- Mais barato para visão (~$0.15/artigo)

### 6.2 Passagem 2: Formatação (GPT-4o)

**Input:** Draft do Claude + Template YAML + Erros de validação
**Tarefa:** Formatar YAML estrito, corrigir campos
**Output:** YAML final validado

**Por que GPT-4o:**
- Excelente em aderir a formatos específicos
- Melhor em correções cirúrgicas
- Mais determinístico para estruturas

### 6.3 Quando Usar Cada API

| Etapa | API | Motivo |
|-------|-----|--------|
| Extração inicial | Claude | Leitura + inferência + custo menor |
| Formatação YAML | GPT-4o | Aderência estrita ao template |
| Repair loop | GPT-4o | Correções pontuais precisas |
| Reextração de quotes | Claude | Precisa reler o artigo |

---

## 7. Validação (3 Camadas)

### Camada 1: Parse YAML
- YAML sintaticamente válido
- Sem erros de indentação/quotes

### Camada 2: Schema (Pydantic)
- Campos obrigatórios presentes
- Tipos corretos
- Valores de enums válidos (Codebook)

### Camada 3: Regras de Negócio (12 Regras)
1. TipoRisco ≠ NR → ObjetoCrítico preenchido
2. ResultadoTipo = Quantitativo → formato correto em Resultados_Quant
3. Maturidade = Produção → NívelEvidência compatível
4. ClasseIA = Híbrido → técnicas especificadas
5. Mecanismo_Inferido → prefixo "INFERIDO:" em cada sentença
6. Mecanismo_Estruturado → string única
7. ArtigoID único e correto
8. Simulação sintética → Maturidade ≠ Produção/Piloto
9. Complexidade_Justificativa com F1/F2/F3
10. Ambiente reflete onde IA atua
11. Limitações_Artigo = NR → confirmar ausência de keywords
12. Nomes de campos exatos do template

### Resultado da Validação
- ✅ **APROVADO** → Salva YAML final
- ⚠️ **REPARÁVEL** → Envia para GPT-4o (até 3 tentativas)
- ❌ **REJEITADO** → Revisão humana

---

## 8. Notebooks

| Notebook | Responsabilidade |
|----------|------------------|
| **01_Configuracao.ipynb** | Setup: paths, APIs, gerar mapping.csv |
| **02_Ingestao.ipynb** | PDF → imagens das páginas (300 DPI) |
| **03_Extracao_LLM.ipynb** | Extração principal (piloto e batch) |
| **04_Validacao.ipynb** | Schema + 12 regras (integrado no 03) |
| **05_Consolidacao.ipynb** | YAML → Excel + relatórios |

---

## 9. Configuração

### 9.1 Arquivo `.env`

```env
# APIs
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...

# Modelos
ANTHROPIC_MODEL=claude-sonnet-4-20250514
OPENAI_MODEL=gpt-4o

# Estratégia
USE_TWO_PASS=true
PRIMARY_PROVIDER=anthropic
```

### 9.2 Dependências Python

```
python-dotenv>=1.0.0
pyyaml>=6.0
pydantic>=2.0
pymupdf>=1.24.0
pillow>=10.0
anthropic>=0.30.0
openai>=1.30.0
ipywidgets>=8.0
openpyxl>=3.1.0
pandas>=2.0
```

---

## 10. Estimativa de Custo

| Fase | Artigos | Custo Estimado |
|------|---------|----------------|
| Piloto | 1-3 | ~$1-2 |
| Batch | 35-37 | ~$7-12 |
| **Total** | **38** | **~$8-14** |

---

## 11. Próximos Passos

1. [ ] Criar estrutura de pastas
2. [ ] Criar arquivo `.env` template
3. [ ] Criar versão condensada do Guia (`guia_v3_3_prompt.md`)
4. [ ] Implementar notebooks na ordem 01 → 05
5. [ ] Testar com 1 artigo piloto
6. [ ] Ajustar prompts conforme necessário
7. [ ] Executar batch nos artigos restantes
8. [ ] Consolidar resultados em Excel

---

## 12. Referências

- `SAEC-OG_Arquitetura_Contratos_v1.md` — Documento de arquitetura original
- `Guia v3.3.md` — Guia de extração completo
- `Guia_Extracao_v3_3.docx` — Guia original (Word)

---

**Documento gerado durante sessão de brainstorming com Claude.**
