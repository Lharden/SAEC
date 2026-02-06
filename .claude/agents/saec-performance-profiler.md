# SAEC Performance Profiler Subagent

## Metadata
```yaml
name: saec-performance-profiler
version: 1.0.0
description: Perfila execução do pipeline SAEC e identifica bottlenecks de performance
trigger: Quando processamento está lento, antes de otimizações, ou para benchmarking
priority: medium
estimated_savings: 50% do tempo de identificação de gargalos
```

## Objetivo

Perfilar a execução do pipeline SAEC-O&G, identificar bottlenecks de CPU, memória e I/O, e fornecer recomendações específicas de otimização com código implementável.

## Quando Usar

- Processamento de artigos está lento (> 2min/artigo)
- Uso de memória está alto (> 2GB)
- Antes de processar batches grandes
- Para benchmarking de otimizações
- Ao investigar crashes ou freezes

## Ferramentas de Profiling

### 1. CPU Profiling com cProfile
```python
import cProfile
import pstats
from io import StringIO

def profile_function(func, *args, **kwargs):
    """Perfila uma função e retorna estatísticas."""
    profiler = cProfile.Profile()
    profiler.enable()

    result = func(*args, **kwargs)

    profiler.disable()

    # Gerar relatório
    stream = StringIO()
    stats = pstats.Stats(profiler, stream=stream)
    stats.sort_stats('cumulative')
    stats.print_stats(20)  # Top 20 funções

    return result, stream.getvalue()
```

### 2. Memory Profiling com memory_profiler
```python
from memory_profiler import profile, memory_usage

@profile
def process_article_with_memory_trace(article_path: Path):
    """Processa artigo com trace de memória linha a linha."""
    # Código será anotado com uso de memória
    pass

def measure_memory_peak(func, *args):
    """Mede pico de memória durante execução."""
    mem_usage = memory_usage((func, args), interval=0.1, max_iterations=1)
    return max(mem_usage), mem_usage
```

### 3. Line Profiling com line_profiler
```python
# Instalar: pip install line_profiler
# Usar: kernprof -l -v script.py

@profile  # Decorador do line_profiler
def extract_text_from_pdf(pdf_path: Path) -> str:
    """Função a ser perfilada linha a linha."""
    doc = fitz.open(pdf_path)  # Tempo aqui?
    text = ""
    for page in doc:  # Loop lento?
        text += page.get_text()  # Concatenação ineficiente?
    return text
```

### 4. I/O Profiling
```python
import time
from contextlib import contextmanager

@contextmanager
def io_timer(operation_name: str):
    """Timer para operações de I/O."""
    start = time.perf_counter()
    yield
    elapsed = time.perf_counter() - start
    logger.info(f"I/O [{operation_name}]: {elapsed:.3f}s")

# Uso
with io_timer("pdf_read"):
    text = read_pdf(path)

with io_timer("llm_call"):
    response = call_llm(prompt)
```

## Bottlenecks Comuns no SAEC-O&G

### 1. Extração de PDF (I/O Bound)
```python
BOTTLENECK_PDF = {
    "symptoms": [
        "Tempo alto em fitz.open()",
        "Lentidão em get_text() para PDFs grandes",
        "Memória alta para PDFs com muitas imagens"
    ],
    "causes": [
        "PDFs não otimizados",
        "Extração de todas as páginas quando não necessário",
        "Carregamento de imagens em memória"
    ],
    "solutions": [
        {
            "name": "Lazy loading",
            "code": """
# Processar páginas sob demanda
for page_num in relevant_pages:
    page = doc.load_page(page_num)
    text = page.get_text()
    del page  # Liberar memória
"""
        },
        {
            "name": "Skip images",
            "code": """
# Não carregar imagens se não necessário
doc = fitz.open(pdf_path)
for page in doc:
    text = page.get_text("text")  # Apenas texto, sem imagens
"""
        }
    ]
}
```

### 2. Chamadas LLM (Network Bound)
```python
BOTTLENECK_LLM = {
    "symptoms": [
        "Espera longa em chamadas de API",
        "Timeouts frequentes",
        "Processamento sequencial de artigos"
    ],
    "causes": [
        "Chamadas síncronas sequenciais",
        "Sem paralelização",
        "Sem caching"
    ],
    "solutions": [
        {
            "name": "Async parallelization",
            "code": """
import asyncio
import httpx

async def extract_batch_async(articles: list[Article]) -> list[Extraction]:
    async with httpx.AsyncClient() as client:
        tasks = [extract_single_async(client, art) for art in articles]
        return await asyncio.gather(*tasks)
"""
        },
        {
            "name": "Request caching",
            "code": """
from functools import lru_cache
import hashlib

@lru_cache(maxsize=1000)
def cached_llm_call(prompt_hash: str, model: str) -> str:
    return call_llm_api(prompt_hash, model)
"""
        }
    ]
}
```

### 3. Processamento de Texto (CPU Bound)
```python
BOTTLENECK_TEXT = {
    "symptoms": [
        "Alto uso de CPU em regex",
        "Lentidão em operações de string",
        "Validators demorando muito"
    ],
    "causes": [
        "Regex não compilados",
        "Concatenação de strings em loop",
        "Múltiplas passagens no texto"
    ],
    "solutions": [
        {
            "name": "Compile regex",
            "code": """
import re

# ANTES
for text in texts:
    match = re.search(r'pattern', text)  # Compila toda vez

# DEPOIS
PATTERN = re.compile(r'pattern')
for text in texts:
    match = PATTERN.search(text)  # Usa compilado
"""
        },
        {
            "name": "Use list join",
            "code": """
# ANTES
result = ""
for item in items:
    result += item  # O(n²)

# DEPOIS
result = "".join(items)  # O(n)
"""
        }
    ]
}
```

### 4. Memória (Memory Bound)
```python
BOTTLENECK_MEMORY = {
    "symptoms": [
        "Uso de memória cresce ao longo do tempo",
        "Crashes em batches grandes",
        "Swap excessivo"
    ],
    "causes": [
        "Objetos não liberados (memory leak)",
        "Carregar todos os dados em memória",
        "Referências circulares"
    ],
    "solutions": [
        {
            "name": "Generator instead of list",
            "code": """
# ANTES
def process_all(paths: list[Path]) -> list[Result]:
    return [process(p) for p in paths]  # Tudo em memória

# DEPOIS
def process_all(paths: list[Path]) -> Iterator[Result]:
    for p in paths:
        yield process(p)  # Um de cada vez
"""
        },
        {
            "name": "Explicit cleanup",
            "code": """
import gc

def process_batch(articles: list[Article]):
    for article in articles:
        result = process(article)
        save(result)
        del result
    gc.collect()  # Forçar coleta
"""
        }
    ]
}
```

## Instruções de Execução

### Passo 1: Coletar Baseline
```python
def collect_baseline(pipeline_func, sample_size: int = 10) -> BaselineMetrics:
    """Coleta métricas baseline do pipeline."""
    import psutil
    import time

    articles = get_sample_articles(sample_size)
    metrics = []

    for article in articles:
        # Métricas antes
        mem_before = psutil.Process().memory_info().rss
        start_time = time.perf_counter()

        # Executar
        result = pipeline_func(article)

        # Métricas depois
        elapsed = time.perf_counter() - start_time
        mem_after = psutil.Process().memory_info().rss

        metrics.append(ArticleMetrics(
            article_id=article.id,
            time_seconds=elapsed,
            memory_delta_mb=(mem_after - mem_before) / 1024 / 1024,
            success=result is not None
        ))

    return BaselineMetrics(
        avg_time=statistics.mean(m.time_seconds for m in metrics),
        p95_time=statistics.quantiles([m.time_seconds for m in metrics], n=20)[18],
        avg_memory=statistics.mean(m.memory_delta_mb for m in metrics),
        max_memory=max(m.memory_delta_mb for m in metrics),
        success_rate=sum(m.success for m in metrics) / len(metrics)
    )
```

### Passo 2: Identificar Hotspots
```python
def identify_hotspots(profile_output: str) -> list[Hotspot]:
    """Identifica funções que consomem mais tempo."""
    hotspots = []

    # Parse output do cProfile
    lines = profile_output.strip().split('\n')
    for line in lines:
        if 'system/src/' in line:  # Nosso código
            parts = line.split()
            if len(parts) >= 6:
                hotspots.append(Hotspot(
                    function=parts[-1],
                    cumulative_time=float(parts[3]),
                    calls=int(parts[0]),
                    time_per_call=float(parts[4])
                ))

    return sorted(hotspots, key=lambda h: h.cumulative_time, reverse=True)[:10]
```

### Passo 3: Gerar Recomendações
```python
def generate_recommendations(
    hotspots: list[Hotspot],
    baseline: BaselineMetrics
) -> list[Recommendation]:
    """Gera recomendações baseadas nos hotspots."""
    recommendations = []

    for hotspot in hotspots:
        # Identificar tipo de bottleneck
        if 'fitz' in hotspot.function or 'pdf' in hotspot.function.lower():
            recommendations.extend(BOTTLENECK_PDF["solutions"])

        elif 'llm' in hotspot.function.lower() or 'api' in hotspot.function.lower():
            recommendations.extend(BOTTLENECK_LLM["solutions"])

        elif 're.' in hotspot.function or 'regex' in hotspot.function.lower():
            recommendations.extend(BOTTLENECK_TEXT["solutions"])

    # Adicionar recomendações de memória se uso alto
    if baseline.max_memory > 500:  # > 500MB
        recommendations.extend(BOTTLENECK_MEMORY["solutions"])

    return deduplicate_recommendations(recommendations)
```

### Passo 4: Benchmark Otimizações
```python
def benchmark_optimization(
    original_func,
    optimized_func,
    test_data,
    iterations: int = 5
) -> BenchmarkResult:
    """Compara performance antes/depois da otimização."""
    import timeit

    original_times = []
    optimized_times = []

    for _ in range(iterations):
        # Original
        start = timeit.default_timer()
        original_func(test_data)
        original_times.append(timeit.default_timer() - start)

        # Otimizado
        start = timeit.default_timer()
        optimized_func(test_data)
        optimized_times.append(timeit.default_timer() - start)

    return BenchmarkResult(
        original_avg=statistics.mean(original_times),
        optimized_avg=statistics.mean(optimized_times),
        speedup=statistics.mean(original_times) / statistics.mean(optimized_times),
        improvement_percent=(1 - statistics.mean(optimized_times) / statistics.mean(original_times)) * 100
    )
```

## Template de Relatório

```markdown
## Relatório de Performance SAEC-O&G

**Data**: {timestamp}
**Amostra**: {sample_size} artigos
**Ambiente**: Python {python_version}, {cpu_info}, {memory_total}GB RAM

### Métricas Baseline

| Métrica | Valor | Target | Status |
|---------|-------|--------|--------|
| Tempo médio/artigo | {avg_time}s | < 60s | {status} |
| Tempo P95 | {p95_time}s | < 120s | {status} |
| Memória média | {avg_memory}MB | < 500MB | {status} |
| Memória máxima | {max_memory}MB | < 1GB | {status} |
| Taxa de sucesso | {success_rate}% | > 95% | {status} |

### Top 10 Hotspots

| Função | Tempo Total | Chamadas | Tempo/Chamada |
|--------|-------------|----------|---------------|
{hotspots_table}

### Análise por Componente

#### Extração de PDF
- **Tempo total**: {pdf_time}s ({pdf_percent}%)
- **Bottleneck**: {pdf_bottleneck}
- **Recomendação**: {pdf_recommendation}

#### Chamadas LLM
- **Tempo total**: {llm_time}s ({llm_percent}%)
- **Bottleneck**: {llm_bottleneck}
- **Recomendação**: {llm_recommendation}

#### Validação
- **Tempo total**: {validation_time}s ({validation_percent}%)
- **Bottleneck**: {validation_bottleneck}
- **Recomendação**: {validation_recommendation}

### Recomendações de Otimização

{for rec in recommendations}
#### {rec.name}
**Impacto estimado**: {rec.estimated_impact}
**Esforço**: {rec.effort}

```python
{rec.code}
```
{endfor}

### Plano de Ação

| Prioridade | Otimização | Impacto | Esforço | Prazo |
|------------|------------|---------|---------|-------|
| 1 | {opt_1} | Alto | Baixo | Imediato |
| 2 | {opt_2} | Médio | Médio | 1 semana |
| 3 | {opt_3} | Médio | Alto | 2 semanas |

### Benchmark Após Otimizações

| Otimização | Antes | Depois | Speedup |
|------------|-------|--------|---------|
{benchmark_table}

### Economia Projetada
- **Tempo/artigo**: {time_saved}s ({time_percent}% redução)
- **Batch 100 artigos**: {batch_time} min (antes: {batch_time_before} min)
- **Memória**: {memory_saved}MB liberados
```

## Script de Profiling Rápido

```python
#!/usr/bin/env python3
"""Script para profiling rápido do SAEC pipeline."""

import cProfile
import pstats
from pathlib import Path
from memory_profiler import memory_usage

from system.src.processors import ArticleProcessor
from system.src.context import create_context

def main():
    ctx = create_context()
    processor = ArticleProcessor(ctx)

    # Selecionar artigo de teste
    test_article = Path("Extraction/pdfs/sample_article.pdf")

    # CPU Profile
    print("=== CPU Profile ===")
    profiler = cProfile.Profile()
    profiler.enable()

    result = processor.process(test_article)

    profiler.disable()
    stats = pstats.Stats(profiler)
    stats.sort_stats('cumulative')
    stats.print_stats(20)

    # Memory Profile
    print("\n=== Memory Profile ===")
    mem = memory_usage((processor.process, (test_article,)), interval=0.1)
    print(f"Peak memory: {max(mem):.1f} MB")
    print(f"Memory delta: {mem[-1] - mem[0]:.1f} MB")

if __name__ == "__main__":
    main()
```

## Métricas de Sucesso

- Tempo médio/artigo < 60 segundos
- Memória máxima < 1GB
- CPU utilization < 80%
- Zero memory leaks em batches longos
- Identificação de bottleneck em < 5 minutos
