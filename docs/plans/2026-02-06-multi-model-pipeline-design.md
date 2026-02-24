# Design: Pipeline Multi-Modelo para Economia e Qualidade

**Data**: 2026-02-06
**Status**: Aprovado
**Contexto**: RTX 3080 10GB VRAM, modelos cloud via Ollama disponíveis

---

## Problema

Pipeline atual usa modelos grandes (18-51GB) localmente em GPU de 10GB VRAM, causando offload para RAM e timeouts. Modelos de extração CIMO precisam de alta qualidade mas não precisam rodar localmente.

## Solução

Fragmentar o pipeline em 4 camadas, roteando cada tarefa para o modelo mais adequado em termos de custo/qualidade/velocidade.

## Arquitetura

```
CAMADA 1: PRE-PROCESSAMENTO (Local - GPU cabe)
  PDF -> glm-ocr (2.2GB)           -> texto extraido
         nomic-embed (957MB)        -> embeddings para RAG
         Python puro                -> limpeza headers/footers

CAMADA 2: EXTRACAO CIMO (Cloud - qualidade maxima)
  Prioridade:
  1. glm-4.7:cloud   (via Ollama)
  2. kimi-k2.5:cloud (via Ollama)
  3. Cloud API (provider 1)      (fallback pago)
  4. Cloud API (provider 2)      (fallback pago)

CAMADA 3: REPAIR / VALIDACAO (Cloud-lite ou Local)
  1. Validacao Python pura (14 regras, zero LLM)
  2. Se falhar -> repair com glm-4.7:cloud
  3. Se falhar -> qwen3-vl:8b local (6.1GB, cabe na GPU)
  4. Ultimo recurso -> Cloud API (provider 1)

CAMADA 4: VERIFICACAO DE QUOTES (Local + RAG)
  1. RAG + embeddings local -> localizar trechos exatos
  2. Se necessario -> qwen3-vl:8b para conferir
```

## Mapeamento de Modelos

| Tarefa | Modelo | Tamanho | Onde Roda | Custo |
|--------|--------|---------|-----------|-------|
| OCR | glm-ocr | 2.2GB | GPU local | $0 |
| Embeddings | nomic-embed-text-v2-moe | 957MB | GPU local | $0 |
| Reranking | bge-reranker-v2-m3 | 438MB | GPU local | $0 |
| Extracao CIMO | glm-4.7:cloud | - | Cloud Zhipu | Gratis/barato |
| Extracao (fallback 1) | kimi-k2.5:cloud | - | Cloud Moonshot | Gratis/barato |
| Extracao (fallback 2) | Cloud API (provider 1) | - | Cloud provider 1 | ~$0.10/artigo |
| Repair YAML | glm-4.7:cloud | - | Cloud Zhipu | Gratis/barato |
| Repair (fallback) | qwen3-vl:8b | 6.1GB | GPU local | $0 |
| Visao local | qwen3-vl:8b | 6.1GB | GPU local | $0 |
| Limpeza texto | Python puro | - | CPU | $0 |

## Fases de Implementacao

### Fase 1: Configuracao de modelos por tarefa
- Arquivos: config.py, .env
- Novos campos: OLLAMA_MODEL_EXTRACT, separar modelos por funcao

### Fase 2: Roteamento inteligente
- Arquivos: llm_client.py, pipeline_cascade.py, ollama_adapter.py
- Usar modelo cloud para extracao, local para tarefas leves

### Fase 3: Ativar RAG
- Arquivos: .env (RAG_ENABLED=true)
- Codigo ja existe, so precisa ativar

### Fase 4: Ativar cascade
- Arquivos: .env (USE_CASCADE=true, EXTRACTION_STRATEGY=local_first)
- Codigo ja existe em pipeline_cascade.py

### Fase 5: Ajustar timeouts
- Arquivos: .env
- Mais margem para latencia de rede

## Modelos para Remover (opcional, economia de disco)

- qwen3-coder-next (51GB) - nao cabe na GPU
- qwen3-coder (18GB) - nao cabe na GPU
- qwen3-vl:30b (19GB) - nao cabe na GPU
- Total: ~56GB de disco

## Metricas de Sucesso

- Extracao CIMO completa sem timeout
- Qualidade >= resultado atual com provedores cloud configurados
- Custo por artigo < $0.05 (vs ~$0.10 atual)
- Tempo por artigo < 60s (vs timeout atual)


