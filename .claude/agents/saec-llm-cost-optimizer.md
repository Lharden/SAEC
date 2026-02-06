# SAEC LLM Cost Optimizer Subagent

## Metadata
```yaml
name: saec-llm-cost-optimizer
version: 1.0.0
description: Analisa prompts e chamadas LLM para otimizar custos e eficiência de tokens
trigger: Antes de modificar prompts, ao adicionar chamadas LLM, ou para auditoria de custos
priority: medium
estimated_savings: 15-30% redução em custos de API
```

## Objetivo

Analisar e otimizar o uso de APIs LLM (Anthropic Claude, OpenAI, Ollama) no projeto SAEC-O&G, reduzindo custos através de prompts mais eficientes, caching inteligente, e seleção apropriada de modelos.

## Quando Usar

- Antes de criar ou modificar prompts
- Quando custos de API estão altos
- Para auditoria periódica de eficiência
- Ao adicionar novas chamadas LLM
- Para comparar estratégias de extração

## Contexto de Custos (2024-2025)

### Preços por 1M Tokens
| Provider | Model | Input | Output |
|----------|-------|-------|--------|
| Anthropic | claude-3-5-sonnet | $3.00 | $15.00 |
| Anthropic | claude-3-haiku | $0.25 | $1.25 |
| OpenAI | gpt-4o | $2.50 | $10.00 |
| OpenAI | gpt-4o-mini | $0.15 | $0.60 |
| Ollama | Local | $0.00 | $0.00 |

### Custo Estimado por Artigo (SAEC-O&G)
```
Extração CIMO completa:
- Input: ~4000 tokens (contexto + prompt)
- Output: ~1500 tokens (extração estruturada)
- Custo Claude Sonnet: ~$0.035/artigo
- Custo GPT-4o-mini: ~$0.0015/artigo
```

## Estratégias de Otimização

### 1. Otimização de Prompts

#### Reduzir Redundância
```python
# ANTES (redundante) - ~800 tokens
PROMPT_VERBOSE = """
You are an expert researcher specializing in systematic literature reviews.
Your task is to extract CIMO components from scientific articles.
CIMO stands for Context, Intervention, Mechanism, and Outcome.
Please carefully read the following text and extract each component.
Make sure to be thorough and accurate in your extraction.
The context should describe the setting and conditions.
The intervention should describe what action was taken.
...
"""

# DEPOIS (otimizado) - ~200 tokens
PROMPT_OPTIMIZED = """
Extract CIMO from this text:
- Context: Setting/conditions
- Intervention: Action/technology applied
- Mechanism: How intervention produces outcome
- Outcome: Measurable result

Return JSON: {"context": "", "intervention": "", "mechanism": "", "outcome": ""}
"""
```

#### Usar Few-Shot Eficiente
```python
# ANTES - exemplos longos
examples = [full_article_1, full_article_2, full_article_3]  # ~6000 tokens

# DEPOIS - exemplos condensados
examples = [
    {"input": "brief_context_1", "output": {"c": "...", "i": "...", "m": "...", "o": "..."}},
    {"input": "brief_context_2", "output": {"c": "...", "i": "...", "m": "...", "o": "..."}}
]  # ~500 tokens
```

### 2. Seleção de Modelo por Tarefa

```python
MODEL_SELECTION = {
    # Tarefas simples -> modelo barato
    "classification": {
        "model": "gpt-4o-mini",  # ou "claude-3-haiku"
        "tasks": ["is_relevant", "language_detection", "section_classification"]
    },

    # Tarefas de extração -> modelo médio
    "extraction": {
        "model": "gpt-4o",  # ou "claude-3-5-sonnet"
        "tasks": ["cimo_extraction", "quote_extraction"]
    },

    # Tarefas complexas -> modelo premium (apenas se necessário)
    "complex_reasoning": {
        "model": "claude-3-5-sonnet",
        "tasks": ["mechanism_inference", "cross_validation"]
    },

    # Tarefas de volume -> modelo local
    "high_volume": {
        "model": "ollama/llama3",
        "tasks": ["preprocessing", "chunking", "basic_extraction"]
    }
}

def select_model(task_type: str) -> str:
    """Seleciona modelo apropriado para a tarefa."""
    for category, config in MODEL_SELECTION.items():
        if task_type in config["tasks"]:
            return config["model"]
    return "gpt-4o-mini"  # Default barato
```

### 3. Caching Inteligente

```python
import hashlib
from functools import lru_cache
from pathlib import Path

CACHE_DIR = Path("Extraction/cache/llm_responses")

def get_cache_key(prompt: str, model: str) -> str:
    """Gera chave de cache determinística."""
    content = f"{model}:{prompt}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]

def cached_llm_call(prompt: str, model: str) -> str:
    """Chamada LLM com cache em disco."""
    cache_key = get_cache_key(prompt, model)
    cache_file = CACHE_DIR / f"{cache_key}.json"

    if cache_file.exists():
        return json.loads(cache_file.read_text())["response"]

    response = call_llm(prompt, model)

    cache_file.write_text(json.dumps({
        "prompt_hash": cache_key,
        "model": model,
        "response": response,
        "timestamp": datetime.now().isoformat()
    }))

    return response
```

### 4. Batching de Requisições

```python
async def batch_extractions(
    articles: list[Article],
    batch_size: int = 5
) -> list[Extraction]:
    """Processa artigos em batches para otimizar throughput."""
    results = []

    for i in range(0, len(articles), batch_size):
        batch = articles[i:i + batch_size]

        # Processar batch em paralelo
        tasks = [extract_cimo_async(article) for article in batch]
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)

        results.extend(batch_results)

        # Rate limiting entre batches
        await asyncio.sleep(1)

    return results
```

### 5. Truncamento Inteligente

```python
def smart_truncate(text: str, max_tokens: int = 3000) -> str:
    """Trunca texto preservando seções importantes."""
    # Estimar tokens (~4 chars por token)
    estimated_tokens = len(text) // 4

    if estimated_tokens <= max_tokens:
        return text

    # Preservar seções importantes
    sections_priority = [
        "abstract", "introduction", "methodology", "results",
        "discussion", "conclusion"
    ]

    preserved = []
    remaining_tokens = max_tokens

    for section in sections_priority:
        section_text = extract_section(text, section)
        section_tokens = len(section_text) // 4

        if section_tokens <= remaining_tokens:
            preserved.append(section_text)
            remaining_tokens -= section_tokens

    return "\n\n".join(preserved)
```

## Instruções de Execução

### Passo 1: Auditar Uso Atual
```python
def audit_llm_usage(log_file: Path) -> UsageReport:
    """Analisa logs de uso de LLM."""
    logs = parse_llm_logs(log_file)

    return UsageReport(
        total_calls=len(logs),
        total_input_tokens=sum(l.input_tokens for l in logs),
        total_output_tokens=sum(l.output_tokens for l in logs),
        total_cost=sum(l.cost for l in logs),
        by_model=group_by_model(logs),
        by_task=group_by_task(logs),
        cache_hit_rate=calculate_cache_hits(logs)
    )
```

### Passo 2: Identificar Oportunidades
```python
def identify_optimizations(report: UsageReport) -> list[Optimization]:
    """Identifica oportunidades de otimização."""
    optimizations = []

    # Verificar uso de modelo caro para tarefas simples
    for task, stats in report.by_task.items():
        if task in SIMPLE_TASKS and stats.model in EXPENSIVE_MODELS:
            optimizations.append(Optimization(
                type="model_downgrade",
                task=task,
                current_model=stats.model,
                suggested_model=get_cheaper_model(task),
                estimated_savings=calculate_savings(stats)
            ))

    # Verificar baixo cache hit rate
    if report.cache_hit_rate < 0.3:
        optimizations.append(Optimization(
            type="improve_caching",
            description="Cache hit rate baixo, implementar caching mais agressivo",
            estimated_savings=report.total_cost * 0.2
        ))

    # Verificar prompts longos
    avg_input = report.total_input_tokens / report.total_calls
    if avg_input > 2000:
        optimizations.append(Optimization(
            type="prompt_optimization",
            description="Prompts médios muito longos, otimizar",
            current_avg=avg_input,
            target_avg=1500,
            estimated_savings=report.total_cost * 0.15
        ))

    return optimizations
```

### Passo 3: Aplicar Otimizações
```python
def apply_optimization(opt: Optimization, codebase_path: Path):
    """Aplica otimização no código."""
    if opt.type == "model_downgrade":
        # Atualizar configuração de modelo
        update_model_config(opt.task, opt.suggested_model)

    elif opt.type == "improve_caching":
        # Adicionar/melhorar cache
        add_caching_layer(codebase_path)

    elif opt.type == "prompt_optimization":
        # Sugerir prompts otimizados
        suggest_optimized_prompts(codebase_path)
```

## Template de Relatório

```markdown
## Relatório de Otimização de Custos LLM

**Período**: {start_date} - {end_date}
**Custo Total**: ${total_cost}

### Uso por Modelo
| Modelo | Chamadas | Tokens In | Tokens Out | Custo |
|--------|----------|-----------|------------|-------|
{model_table}

### Uso por Tarefa
| Tarefa | Modelo Atual | Chamadas | Custo | Modelo Sugerido | Economia |
|--------|--------------|----------|-------|-----------------|----------|
{task_table}

### Métricas de Eficiência
- **Cache Hit Rate**: {cache_rate}%
- **Tokens médios/chamada**: {avg_tokens}
- **Custo médio/artigo**: ${avg_cost_per_article}

### Otimizações Recomendadas

{for opt in optimizations}
#### {opt.type}
- **Descrição**: {opt.description}
- **Economia Estimada**: ${opt.estimated_savings}/mês
- **Implementação**: {opt.implementation_steps}
{endfor}

### Economia Total Estimada
- **Mensal**: ${monthly_savings}
- **Anual**: ${annual_savings}
- **Percentual**: {savings_percentage}%

### Próximos Passos
1. {step_1}
2. {step_2}
3. {step_3}
```

## Checklist de Otimização

- [ ] Prompts otimizados (< 500 tokens de instruções)
- [ ] Modelo apropriado para cada tarefa
- [ ] Cache implementado com hit rate > 30%
- [ ] Batching para processamento em volume
- [ ] Truncamento inteligente de textos longos
- [ ] Monitoramento de custos ativo
- [ ] Fallback para modelos locais quando possível

## Métricas de Sucesso

- Redução de custos >= 20%
- Cache hit rate >= 40%
- Tokens médios por chamada < 2000
- Zero impacto na qualidade de extração
