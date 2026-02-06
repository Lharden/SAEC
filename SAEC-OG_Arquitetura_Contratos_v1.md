# SAEC-O&G — Documento de Arquitetura + Contratos (v1)

**SAEC-O&G (Sistema Autônomo de Extração CIMO para Oil & Gas)** é uma ferramenta local para processar artigos científicos em lote, extraindo dados no framework **CIMO** (Contexto, Intervenção, Mecanismo, Outcome) e entregando **somente YAML** validado por um **Rule Engine (12 regras)** e por um **Protocolo de Auto‑Revisão**.  
Base conceitual: **Especificação do Sistema SAEC-O&G** e **Guia de Extração v3.3**.

---

## 1. Objetivo, premissas e escopo

### 1.1 Objetivo
- Processar em lote (ex.: ~38 artigos) e gerar extrações consistentes, rastreáveis e auditáveis para uma RSL.
- Saídas: **YAML por artigo** + **planilha Excel consolidada** + **relatórios de auditoria**.

### 1.2 Premissas de execução (conforme solicitado)
- **Sem colaboração**: tudo **local**, com arquivos no disco.
- **Entrada já delimitada**: pasta de artigos:
  - `C:\Users\Leonardo\Documents\Computing\Projeto_Mestrado\files\files\articles\00 Dados RSL\02 T2`
- **No máximo 2 APIs externas**:
  - **OpenAI** e **Anthropic**
- O sistema deve embutir as melhorias e contornos de falhas mais comuns (YAML inválido, regra violada, quotes ausentes, contexto longo etc.).

### 1.3 Escopo funcional (alto nível)
A arquitetura segue quatro módulos integrados:
1) **Ingestão Multimodal** (texto + tabelas/figuras)  
2) **LLM Core** (aplicação do Codebook/Guia v3.3 e geração de YAML)  
3) **Validação e Auditoria** (schema + 12 regras + auto‑revisão)  
4) **Consolidação** (YAML → Excel + relatórios)

---

## 2. Visão geral do funcionamento

### 2.1 Fluxo operacional “set and forget”
1. Sistema varre a pasta de artigos e monta uma **fila** de execução (um job por PDF).
2. Para cada PDF:
   - faz ingestão (texto + tabelas) com mapeamento de páginas;
   - executa extração com LLM;
   - valida YAML (parse + schema + regras + checklist);
   - salva artefatos (YAML final, quotes, logs, auditoria).
3. Ao final do lote:
   - consolida todos os YAML aprovados em **Excel**;
   - gera relatório (pass/fail por artigo e por regra).

---

## 3. Estrutura de pastas (local)

> Sugestão de estrutura para execução robusta e idempotente (rodar duas vezes não “bagunça” a saída).

```
saec-og/
  input/
    articles/                         # apontar para a pasta real do usuário (02 T2) via config
  work/
    ART_001/
      ingest/
        extracted_text.txt
        page_map.json
        tables.json
        figures/                      # opcional
      llm/
        prompt_v3.3.txt
        draft.yaml
        repair_attempt_01.yaml
        repair_attempt_02.yaml
      audit/
        schema_report.json
        rules_report.json
        autoreview_report.json
      final/
        ART_001.yaml
  output/
    yamls/                            # cópia dos YAML finais
    consolidated/
      saec_consolidated.xlsx
      audit_summary.csv
  logs/
    saec_run.log
  config/
    saec.yaml
  src/
    saec/
      __init__.py
      config.py
      ingest.py
      llm_core.py
      validators.py
      rule_engine.py
      autoreview.py
      consolidate.py
      contracts.py
      runner.py
```

### 3.1 Por que esta estrutura funciona bem
- **Idempotência por ArtigoID**: cada artigo tem um diretório próprio em `work/ART_xxx/`.
- **Cache por etapa**: ingestão e respostas LLM podem ser reaproveitadas.
- **Auditoria completa**: relatórios de validação ficam juntos do YAML final.

---

## 4. Inputs necessários

### 4.1 Inputs obrigatórios
1. **Pasta de PDFs** (já delimitada pelo usuário).
2. **ArtigoID** por PDF  
   - O Guia exige controle de ArtigoID no formato `ART_0nn`.  
   - Recomendação prática: mapear ArtigoID ↔ arquivo por um `mapping.csv` local (opcional, mas muito útil).

**Exemplo `mapping.csv` (opcional)**
```
ArtigoID,ArquivoPDF
ART_001,A hybrid data envelopment analysis and artificial intelligence framework....pdf
ART_002,Applying Machine Learning to the Fuel Theft Problem on Pipelines.pdf
...
```

### 4.2 Inputs implícitos (embutidos no sistema)
- **Guia v3.3**: prompt mestre + template YAML + regras + auto‑revisão.
- **Schemas/contratos**: definição de campos e validações programáticas.

---

## 5. Contratos de dados (YAML) — fonte de verdade

### 5.1 Template YAML (obrigatório)
O output final por artigo deve seguir o **template YAML v3.3** (campos e nomes exatamente iguais), incluindo:
- METADATA (ArtigoID, Ano, TipoPublicação, Referência_Curta, DOI)
- CONTEXTO (SegmentoO&G, Ambiente, Complexidade, Complexidade_Justificativa, ProcessoSCM_Alvo, TipoRisco_SCRM, ObjetoCrítico)
- NARRATIVAS CONTEXTUAIS (ProblemaNegócio_Contexto)
- INTERVENÇÃO (ClasseIA, ClasseIA_Confiança, TarefaAnalítica, FamíliaModelo, TipoDado, Maturidade, Maturidade_Confiança, Intervenção_Descrição, Dados_Descrição)
- MECANISMO (CategoriaMecanismo, Mecanismo_Fonte, Mecanismo_Declarado, Mecanismo_Inferido, Mecanismo_Estruturado)
- OUTCOME (ResultadoTipo, Resultados_Quant, Resultados_Qual, NívelEvidência, Limitações_Artigo)
- OPCIONAL (Observação)
- QUOTES (3–8 itens, literais, com página/seção)

> Regras-chave de formato (exemplos):
- `Mecanismo_Estruturado` deve ser **linha única** no formato `"Entrada → Transformação → Mediação → Resultado"`.
- Se `TipoRisco_SCRM` ≠ `NR`, então `ObjetoCrítico` é obrigatório.
- `Quotes`: 3 a 8, literais, ≤3 linhas, com página/seção.

### 5.2 Schema programático (Pydantic) — contrato
Definir um `ExtractionSchema` em `src/saec/contracts.py` que:
- valida presença/ausência de campos;
- valida enums (Ambiente, Complexidade, Confiança etc.);
- valida tipos (string, listas, etc.).

---

## 6. Pipeline detalhado por módulos (A → D)

## 6.A Módulo de Ingestão Multimodal (PDF → evidências)

### Objetivo
Extrair conteúdo preservando rastreabilidade de **páginas** (necessário para quotes) e capturar tabelas/figuras quando relevantes.

### Passos
1. **Leitura e extração de texto**
   - produzir `extracted_text.txt`
2. **Mapeamento de páginas**
   - gerar `page_map.json` (trecho → página)
3. **Extração de tabelas**
   - gerar `tables.json` (mesmo que vazio)
4. **Fallback opcional (somente quando necessário)**
   - renderizar páginas relevantes como imagem e enviar para LLM com visão (preferencialmente OpenAI, se suportar no stack escolhido).

### Falhas comuns e contornos
- **Texto ruim (PDF escaneado)**: tentar OCR (somente nesses casos).
- **Tabelas ilegíveis por parser**: renderizar páginas e extrair via visão.
- **Páginas não mapeadas**: se não houver page_map confiável, marcar `Confiança` como baixa e registrar em `Observação`.

---

## 6.B Módulo LLM Core (extração → YAML)

### Objetivo
Aplicar o Guia v3.3 e preencher o YAML com coerência CIMO e evidências, incluindo:
- Segmento e Ambiente onde a IA atua;
- Complexidade via F1/F2/F3;
- Mecanismo declarado + inferido (com prefixo **INFERIDO:** quando não explícito);
- Resultados quant/qual com formato padronizado;
- Quotes literais com página/seção.

### Estratégia “lisa” (recomendação): **2 passagens**
**Passo 1 — Draft factual (conteúdo)**
- o LLM gera um rascunho com:
  - campos principais (com placeholders quando faltar dado),
  - lista de evidências (trechos e página),
  - dúvidas/ambiguidade sinalizadas.

**Passo 2 — Formatação estrita (YAML final)**
- o LLM recebe:
  - template YAML fixo,
  - draft do passo 1,
  - regras (12) + auto‑revisão,
  - e deve produzir **somente YAML** final.

### Loop de correção (repair loop)
Se o YAML:
- não parseia; ou
- falha no schema; ou
- viola alguma regra;  
então o sistema executa até N tentativas (ex.: N=3) com prompts de correção que pedem:
- **corrigir apenas os campos quebrados**, mantendo os demais intactos;
- manter nomes de campos e formato do template.

---

## 6.C Módulo de Validação e Auditoria (Rule Engine)

### Objetivo
Garantir que o output atende:
1) YAML válido  
2) Schema válido (contratos)  
3) 12 regras essenciais  
4) Auto‑revisão (fases 1–4)

### Camadas de validação
1. **Parse YAML**
2. **Schema (Pydantic)**
3. **Rule Engine (12 regras)**  
4. **Auto‑Revisão (checklist)**

### Saídas do módulo
- `schema_report.json` (erros estruturais)
- `rules_report.json` (pass/fail por regra)
- `autoreview_report.json` (pass/fail por fase)
- status final: **APPROVED** ou **NEEDS_REPAIR** ou **REJECTED** (após N tentativas)

### Principais contornos embutidos (falhas)
- **Mecanismo inferido sem “INFERIDO:”**: corrigir automaticamente.
- **Mecanismo_Estruturado multilinha**: reformatar para linha única.
- **Quotes insuficientes**: forçar reextração de quotes (sem regenerar todo YAML).
- **Resultados quant fora do padrão**: normalização/repair específico.

---

## 6.D Módulo de Consolidação (YAML → Excel)

### Objetivo
Converter YAML aprovados em:
- `saec_consolidated.xlsx` (aba principal: 1 linha por ArtigoID)
- `audit_summary.csv` (pass/fail por regra)
- (opcional) aba `Quotes` (uma linha por quote)

### Regras de consolidação
- Só consolidar artigos **APPROVED**.
- Incluir metadados: data/hora, modelo, versão do guia.

---

## 7. Onde entra cada API (OpenAI e Anthropic) — divisão recomendada

> Meta: usar **as duas** onde fazem mais diferença, mantendo o máximo local.

### 7.1 OpenAI — recomendado para **formatação estrita e reparos**
**Uso ideal**
- Passo 2 (YAML estrito): o modelo deve ser muito bom em obedecer formato.
- Repair loop: correções cirúrgicas (campo X/Y), mantendo YAML válido.
- (Opcional) visão para páginas com tabelas/figuras quando necessário.

**Entradas típicas**
- template YAML + draft + erros do rule engine + instruções de correção
**Saída**
- YAML estrito (somente YAML)

### 7.2 Anthropic — recomendado para **interpretação longa e mecanismo**
**Uso ideal**
- Passo 1 (draft factual): leitura extensa, síntese e inferência bem explicada.
- Construção do **Mecanismo_Inferido** (com prefixo INFERIDO: em cada sentença).
- Ajuda a evitar “NR prematuro” (tendência que o checklist alerta).

**Entradas típicas**
- texto do artigo (ou chunks) + perguntas-guia do codebook
**Saída**
- draft com campos e evidências (não precisa ser YAML perfeito)

### 7.3 Embeddings / RAG — local (sem API extra)
Como você limitou a 2 APIs (OpenAI e Anthropic), o fallback de contexto pode ser **local**:
- embeddings locais (ex.: `bge-small`, `e5-base`) + FAISS
- ou BM25 (rápido e simples)
Isso permite:
- chunking e recuperação de trechos para apoiar quotes e campos difíceis,
- sem “terceira API”.

---

## 8. Estratégias incorporadas para deixar o sistema “liso”

### 8.1 Idempotência e reprocessamento seletivo
- Rodar lote novamente não reprocessa tudo: apenas o que:
  - falhou,
  - ou mudou versão do guia/prompt,
  - ou foi marcado como “reprocessar”.

### 8.2 Cache de chamadas LLM
- Hash do (ArtigoID + versão guia + prompt + input) → reutiliza resposta.
- Reduz custo e aumenta consistência.

### 8.3 Observabilidade e auditoria de confiança
- Campos de confiança para SegmentoO&G, ClasseIA, Maturidade devem existir.
- Se houver incerteza, o sistema deve:
  - escolher `Confiança: Baixa`
  - justificar em `Observação` (escape rule)

### 8.4 Normalização de resultados quantitativos
Forçar o formato:
- `"métrica: valor (vs. baseline: X)"`  
e impedir que “métrica” vire “tamanho do dataset”.

### 8.5 Quotes rastreáveis
- Quotes literais, ≤3 linhas, com página/seção.
- Pelo menos 1 quote de Mecanismo, se existir no artigo.

---

## 9. Documento de Arquitetura + Contratos (implementação)

### 9.1 Contratos de ferramentas (interfaces)
Definir contratos claros para cada etapa (chamáveis por CLI e por OpenClaw):

#### `ingest_pdf`
**Input**
- `pdf_path: str`
- `artigo_id: str`
**Output**
- `extracted_text_path: str`
- `page_map_path: str`
- `tables_path: str`
- `status: str`

#### `llm_draft_extract`
**Input**
- `artigo_id: str`
- `extracted_text_path: str`
- `tables_path: str`
- `guide_version: str = "v3.3"`
- `provider: "anthropic"`
**Output**
- `draft_path: str`
- `status: str`

#### `llm_format_yaml_strict`
**Input**
- `artigo_id: str`
- `draft_path: str`
- `template_version: str = "v3.3"`
- `provider: "openai"`
**Output**
- `yaml_candidate_path: str`
- `status: str`

#### `validate_and_audit`
**Input**
- `yaml_path: str`
**Output**
- `schema_report_path: str`
- `rules_report_path: str`
- `autoreview_report_path: str`
- `status: "APPROVED" | "NEEDS_REPAIR" | "REJECTED"`
- `errors: list[str]`

#### `repair_yaml`
**Input**
- `yaml_path: str`
- `errors: list[str]`
- `provider: "openai"`
**Output**
- `yaml_repaired_path: str`
- `status: str`

#### `consolidate_excel`
**Input**
- `yamls_dir: str`
- `excel_out_path: str`
**Output**
- `excel_out_path: str`
- `audit_summary_path: str`

### 9.2 Contratos de configuração (`config/saec.yaml`)
Exemplo:
```yaml
paths:
  articles_dir: "C:\\Users\\Leonardo\\Documents\\Computing\\Projeto_Mestrado\\files\\files\\articles\\00 Dados RSL\\02 T2"
  project_root: "C:\\Users\\Leonardo\\Documents\\Computing\\saec-og"
llm:
  openai_model: "gpt-4.1-mini"       # exemplo
  anthropic_model: "claude-3.5-sonnet"
  max_repair_attempts: 3
rag_local:
  enabled: true
  method: "bm25"                     # ou "faiss"
validation:
  enforce_autoreview: true
  min_quotes: 3
  max_quotes: 8
```

### 9.3 Variáveis de ambiente
- `OPENAI_API_KEY=...`
- `ANTHROPIC_API_KEY=...`

---

## 10. Execução (CLI local)

### 10.1 Rodar lote
```
python -m saec.runner batch --config config/saec.yaml
```

### 10.2 Reprocessar apenas falhas
```
python -m saec.runner retry-failed --config config/saec.yaml
```

### 10.3 Consolidar Excel (apenas aprovados)
```
python -m saec.runner consolidate --config config/saec.yaml
```

---

## 11. Integração com OpenClaw (opcional)
O OpenClaw entra como orquestrador, chamando os comandos CLI acima e exibindo:
- status por ArtigoID,
- resumo das falhas por regra,
- links/pastas dos artefatos.

Como a execução é local e a pasta já existe, o OpenClaw é útil para:
- disparar o lote via comando único;
- monitorar e reprocessar automaticamente falhas;
- operar via TUI/WhatsApp (se desejado).

---

## 12. Critérios de “pronto para produção” (MVP forte)
- 100% dos YAML aprovados parseiam e passam schema.
- Regra 1 (TipoRisco_SCRM ↔ ObjetoCrítico) consistente em todo lote.
- `Mecanismo_Estruturado` sempre em linha única no formato correto.
- Quotes: 3–8, literais, com página/seção, com pelo menos 1 de mecanismo quando existir.
- Excel consolidado gerado sem erros.
- Relatório de auditoria por regra e por artigo.

---

## 13. Apêndice — lista de falhas e correções automáticas (resumo)

| Falha | Detecção | Correção automática |
|---|---|---|
| YAML inválido | parse falha | reformat via OpenAI (somente formato) |
| Campo ausente | schema | repair somente do campo |
| Campo com nome errado | schema/rules | renomear conforme template |
| Mecanismo sem “INFERIDO:” | regra/checklist | patch no texto (prefixo por sentença) |
| Mecanismo_Estruturado multilinha | regra | reescrever como string única |
| Quotes < 3 | checklist | reextração de quotes (sem regenerar tudo) |
| ObjetoCrítico vazio com TipoRisco ≠ NR | regra | exigir preenchimento ou reclassificar com justificativa |
| Resultados_Quant fora do padrão | regra | normalizar formato exigido |
| NR prematuro | checklist | reexecutar perguntas-guia / inferência |

---

## 14. Decisão de design (por que esta divisão OpenAI/Anthropic)
- **Anthropic**: melhor para leitura longa e explicação (draft + mecanismo).
- **OpenAI**: melhor para **obedecer formato rígido** e executar reparos cirúrgicos em YAML.
- **RAG local** evita terceira API e dá robustez em artigos longos.

---

**Fim do documento.**
