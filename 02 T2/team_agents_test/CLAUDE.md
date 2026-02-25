# Agent Team — Extração RSL (CIMO)

## Contexto do Projeto

Sistema de extração estruturada de artigos científicos sobre IA aplicada a Supply Chain Management no setor Oil & Gas. O framework de extração é o **CIMO** (Contexto-Intervenção-Mecanismo-Outcome).

Os artigos já foram **ingeridos** (texto e imagens extraídos do PDF). Esta equipe é responsável por:
1. **Extrair** os dados estruturados via LLM (cada extractor processa seu lote)
2. **Validar** os YAMLs gerados contra as 12 regras do Guia v3.3 (QA Reviewer)
3. **Consolidar** os aprovados em Excel final (Lead, ao término)

---

## Arquitetura de Autenticação

**Claude Code (Lead + teammates)** usa OAuth diretamente com a conta claude.ai — não passa pelo proxy LiteLLM. Não definir `ANTHROPIC_BASE_URL` nem `ANTHROPIC_API_KEY` no ambiente.

**extract_article.py** chama o LiteLLM em `http://localhost:4000` para acessar os modelos não-Anthropic via OpenRouter. O proxy deve estar rodando antes de iniciar qualquer extração.

```
Claude Code  →  OAuth (assinatura Pro/Max)        →  coordenação
extract_article.py  →  LiteLLM :4000  →  OpenRouter  →  extração
```

---

## Estrutura de Diretórios

```
team_agents_test/
├── extract_article.py     # Script de extração (use para cada artigo)
├── qa_validate.py         # Validação QA dos YAMLs
├── consolidate_test.py    # Geração do Excel final
├── CLAUDE.md              # Este arquivo
├── yamls/                 # Destino dos YAMLs extraídos
├── qa_report.csv          # Gerado pelo QA Reviewer
└── extracoes_final.xlsx   # Gerado ao final pelo Lead
```

---

## Pré-requisitos

**LiteLLM proxy deve estar rodando em http://localhost:4000 antes de iniciar qualquer extração.**

Iniciar o proxy (terminal dedicado, manter aberto):
```powershell
$env:OPENROUTER_API_KEY = "sk-or-v1-..."
~\litellm-env\Scripts\litellm.exe --config C:\Users\Leonardo\config.yaml --port 4000
```

Validar:
```powershell
Invoke-WebRequest -Uri "http://localhost:4000/v1/models" -UseBasicParsing | ConvertFrom-Json | Select-Object -ExpandProperty data | Select-Object id
```

---

## Modelos disponíveis no proxy LiteLLM (somente extração)

| model_name | Modelo real | Visão |
|---|---|---|
| `gemini-pro` | Gemini 3.1 Pro Preview (Google) | ✅ |
| `gpt-5` | GPT-5.2 (OpenAI) | ✅ |
| `kimi-k2.5` | Kimi K2.5 via DeepInfra | usar --text-only |
| `minimax-m2.5` | MiniMax M2.5 via SambaNova | usar --text-only |
| `glm-5` | GLM-5 (ZhipuAI) | usar --text-only |

**Nenhum modelo Claude está disponível no proxy** — Claude Code usa OAuth diretamente.

---

## Como extrair um artigo

```powershell
$TEAM = "C:/Users/Leonardo/Documents/Computing/Projeto_Mestrado/files/files/articles/00 Dados RSL/02 T2/team_agents_test"
$PYTHON = "$HOME/litellm-env/Scripts/python"

# Extração com visão (gemini-pro, gpt-5)
& $PYTHON "$TEAM/extract_article.py" --article ART_001 --model gemini-pro --output "$TEAM/yamls"

# Extração sem imagens (kimi-k2.5, minimax-m2.5, glm-5)
& $PYTHON "$TEAM/extract_article.py" --article ART_001 --model kimi-k2.5 --output "$TEAM/yamls" --text-only

# Limitar número de imagens (artigos muito longos)
& $PYTHON "$TEAM/extract_article.py" --article ART_001 --model gemini-pro --output "$TEAM/yamls" --max-images 6
```

---

## Distribuição de Artigos por Extractor

| Extractor | Modelo | Artigos | Modo |
|---|---|---|---|
| Extractor-A | `gemini-pro` | ART_001 a ART_010 | visão |
| Extractor-B | `gpt-5` | ART_011 a ART_020 | visão |
| Extractor-C | `kimi-k2.5` | ART_021 a ART_030 | --text-only |
| Extractor-D | `minimax-m2.5` | ART_031 a ART_038 | --text-only |

### Artigos já extraídos (não reprocessar)

| Extractor | Concluídos |
|---|---|
| Extractor-A | ART_001, ART_002, ART_003, ART_004 |
| Extractor-B | ART_011, ART_012, ART_013, ART_014, ART_015, ART_016 |
| Extractor-C | ART_021 |
| Extractor-D | ART_031, ART_032, ART_033, ART_034, ART_035, ART_036, ART_037, ART_038 ✅ |

### Artigos pendentes (19 total)

| Extractor | Pendentes |
|---|---|
| Extractor-A | ART_005, ART_006, ART_007, ART_008, ART_009, ART_010 |
| Extractor-B | ART_017, ART_018, ART_019, ART_020 |
| Extractor-C | ART_022, ART_023, ART_024, ART_025, ART_026, ART_027, ART_028, ART_029, ART_030 |

---

## Regras de Comportamento do Agent Team

**CRÍTICO — seguir obrigatoriamente:**

1. Cada extractor recebe sua lista completa de artigos no prompt de spawn — não depende de TaskList para saber o que fazer
2. Cada extractor executa os comandos bash em sequência, um por vez, aguardando cada um terminar
3. Se um artigo já tiver YAML em `./yamls/`, pular sem reprocessar
4. Se um extractor ficar idle por mais de 30 segundos sem executar comandos, **não relançar** — reportar ao Lead e aguardar instrução
5. **Não spawnar agentes duplicados** — se um agente já existe para um lote, não criar outro para o mesmo lote
6. QA Reviewer só inicia após confirmação explícita do Lead de que todos os extractors concluíram

---

## Papel do QA Reviewer

Execute após todos os extractors terminarem:

```powershell
$TEAM = "C:/Users/Leonardo/Documents/Computing/Projeto_Mestrado/files/files/articles/00 Dados RSL/02 T2/team_agents_test"
$PYTHON = "$HOME/litellm-env/Scripts/python"

& $PYTHON "$TEAM/qa_validate.py" --yamls "$TEAM/yamls" --output "$TEAM/qa_report.csv"
```

O relatório mostrará: status de cada artigo, regras violadas e comparativo por modelo.

---

## Papel do Lead (consolidação final)

Execute após o QA Reviewer terminar:

```powershell
$TEAM = "C:/Users/Leonardo/Documents/Computing/Projeto_Mestrado/files/files/articles/00 Dados RSL/02 T2/team_agents_test"
$PYTHON = "$HOME/litellm-env/Scripts/python"

& $PYTHON "$TEAM/consolidate_test.py" --yamls "$TEAM/yamls" --qa-report "$TEAM/qa_report.csv" --output "$TEAM/extracoes_final.xlsx"
```

---

## Artigos Disponíveis (38 total, todos ingeridos)

Dados ingeridos em:
`00 Dados RSL/data/Extraction/outputs/work/ART_XXX/`
- `hybrid.json` — estrutura por página (texto vs imagem)
- `texts.json` — texto extraído por página
- `pages/page_NNN.png` — imagens renderizadas

---

## Regras de Validação (Guia v3.3)

| Regra | Descrição |
|---|---|
| R1 | TipoRisco_SCRM preenchido → ObjetoCrítico obrigatório |
| R2 | ResultadoTipo Quantitativo → Resultados_Quant com métricas (formato: `métrica: valor`) |
| R3 | Maturidade válida: Conceito / Protótipo / Piloto / Produção |
| R4 | ClasseIA Híbrido → FamíliaModelo com múltiplas técnicas (`;` ou `+`) |
| R5 | Mecanismo_Inferido → cada sentença começa com `INFERIDO:` |
| R6 | Mecanismo_Estruturado é string única com `→` (sem quebras de linha) |
| R7 | ArtigoID no formato `ART_001` |
| R8 | Simulação com dados sintéticos incompatível com Maturidade Produção/Piloto |
| R9 | Complexidade_Justificativa contém F1=N, F2=N, F3=N e total consistente |
| R10 | Ambiente reflete onde a IA atua (não onde o ativo opera) |
| R11 | Limitações_Artigo não deve ser NR se o artigo mencionar limitações |
| R12 | Validação estrutural final |
| QUOTES | Mínimo 3, máximo 8, ao menos 1 do tipo "Mecanismo" |

---

## Observações Importantes

- **Não modifique** os arquivos em `data/Extraction/outputs/work/` (dados de ingestão originais)
- **Não modifique** o sistema SAEC em `system/` — os scripts apenas leem dele
- Se um artigo falhar repetidamente, registre e o Lead decide se reprocessa com outro modelo
- Os `.meta.json` gerados junto com cada YAML registram qual modelo foi usado — importante para o relatório comparativo
- Monitorar progresso real: `dir ./yamls/*.yaml | Measure-Object` deve chegar a 38
