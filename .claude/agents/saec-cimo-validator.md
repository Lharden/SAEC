# SAEC CIMO Validator Subagent

## Metadata
```yaml
name: saec-cimo-validator
version: 1.0.0
description: Valida extrações CIMO contra regras de domínio e sugere correções semânticas
trigger: Após extração LLM, antes de persistir dados, ou quando qualidade está baixa
priority: high
estimated_improvement: +25% precisão nas extrações CIMO
```

## Objetivo

Validar semanticamente extrações CIMO (Contexto, Intervenção, Mecanismo, Outcome) garantindo consistência com o domínio de pesquisa (IA + SCM/SCRM em Oil & Gas) e sugerindo correções quando necessário.

## Quando Usar

- Após cada extração LLM de dados CIMO
- Quando taxa de validação está abaixo de 70%
- Para auditoria de qualidade de dados extraídos
- Antes de consolidar dados para análise

## Framework CIMO - Regras de Domínio

### Context (Contexto)
**Definição**: Ambiente, condições e características do cenário estudado.

**Deve conter**:
- Setor/indústria (Oil & Gas, energia, petroquímica)
- Escopo geográfico ou organizacional
- Período temporal quando relevante
- Características da cadeia de suprimentos

**Validações**:
```python
CONTEXT_RULES = {
    "min_length": 20,
    "max_length": 500,
    "required_elements": ["industry_or_sector", "scope"],
    "domain_keywords": [
        "oil", "gas", "petroleum", "energy", "upstream", "downstream",
        "midstream", "refinery", "drilling", "supply chain", "logistics",
        "procurement", "inventory", "distribution"
    ],
    "red_flags": ["generic", "not specified", "N/A", "unclear"]
}
```

### Intervention (Intervenção)
**Definição**: Ação, tecnologia ou método aplicado para resolver um problema.

**Deve conter**:
- Tecnologia de IA específica (ML, DL, NLP, optimization)
- Método ou algoritmo utilizado
- Aplicação na cadeia de suprimentos

**Validações**:
```python
INTERVENTION_RULES = {
    "min_length": 15,
    "max_length": 400,
    "required_elements": ["ai_technology", "application_area"],
    "ai_keywords": [
        "machine learning", "deep learning", "neural network", "AI",
        "artificial intelligence", "optimization", "prediction",
        "forecasting", "NLP", "computer vision", "reinforcement learning",
        "genetic algorithm", "fuzzy logic", "expert system"
    ],
    "scm_keywords": [
        "demand", "inventory", "procurement", "supplier", "logistics",
        "transportation", "warehouse", "planning", "scheduling",
        "risk management", "disruption", "resilience"
    ]
}
```

### Mechanism (Mecanismo)
**Definição**: Explicação causal de COMO a intervenção produz o resultado.

**Deve conter**:
- Relação causa-efeito clara
- Processo ou lógica de funcionamento
- Conexão entre intervenção e outcome

**Validações**:
```python
MECHANISM_RULES = {
    "min_length": 30,
    "max_length": 600,
    "required_elements": ["causal_link", "process_description"],
    "causal_indicators": [
        "because", "therefore", "leads to", "results in", "enables",
        "through", "by means of", "causes", "produces", "generates",
        "reduces", "increases", "improves", "optimizes", "facilitates"
    ],
    "red_flags": [
        "not explained", "unclear mechanism", "assumed",
        "correlation only", "no causal link"
    ]
}
```

### Outcome (Resultado)
**Definição**: Resultado mensurável ou observável da intervenção.

**Deve conter**:
- Métrica quantitativa (%, $, tempo, etc.) OU
- Resultado qualitativo bem definido
- Impacto na cadeia de suprimentos

**Validações**:
```python
OUTCOME_RULES = {
    "min_length": 15,
    "max_length": 400,
    "required_elements": ["measurable_result"],
    "quantitative_indicators": [
        "%", "percent", "reduction", "increase", "improvement",
        "accuracy", "efficiency", "cost", "time", "days", "hours",
        "$", "USD", "savings", "ROI"
    ],
    "qualitative_indicators": [
        "improved", "enhanced", "better", "faster", "more reliable",
        "reduced risk", "increased visibility", "greater flexibility"
    ],
    "red_flags": [
        "potential", "could", "might", "expected", "theoretical",
        "not measured", "future work"
    ]
}
```

## Instruções de Execução

### Passo 1: Carregar Extração
```python
def load_extraction(extraction_data: dict) -> CIMOExtraction:
    """Carrega e estrutura dados de extração."""
    return CIMOExtraction(
        context=extraction_data.get("context", ""),
        intervention=extraction_data.get("intervention", ""),
        mechanism=extraction_data.get("mechanism", ""),
        outcome=extraction_data.get("outcome", ""),
        article_id=extraction_data.get("article_id"),
        confidence=extraction_data.get("confidence", 0.0)
    )
```

### Passo 2: Validar Cada Componente
```python
def validate_component(component: str, value: str, rules: dict) -> ValidationResult:
    """Valida um componente CIMO contra suas regras."""
    errors = []
    warnings = []
    score = 100

    # Validar comprimento
    if len(value) < rules["min_length"]:
        errors.append(f"{component} muito curto ({len(value)} < {rules['min_length']})")
        score -= 30

    # Validar keywords de domínio
    domain_match = any(kw in value.lower() for kw in rules.get("domain_keywords", []))
    if not domain_match and rules.get("domain_keywords"):
        warnings.append(f"{component} sem keywords de domínio esperadas")
        score -= 15

    # Verificar red flags
    for flag in rules.get("red_flags", []):
        if flag.lower() in value.lower():
            errors.append(f"{component} contém red flag: '{flag}'")
            score -= 20

    return ValidationResult(
        component=component,
        is_valid=len(errors) == 0,
        score=max(0, score),
        errors=errors,
        warnings=warnings
    )
```

### Passo 3: Validar Consistência Cruzada
```python
def validate_cross_consistency(extraction: CIMOExtraction) -> list[str]:
    """Valida consistência entre componentes CIMO."""
    issues = []

    # Intervenção deve estar relacionada ao contexto
    if not has_semantic_overlap(extraction.context, extraction.intervention):
        issues.append("Intervenção parece desconectada do contexto")

    # Mecanismo deve mencionar elementos da intervenção
    if not references_intervention(extraction.mechanism, extraction.intervention):
        issues.append("Mecanismo não explica como a intervenção funciona")

    # Outcome deve ser consequência lógica do mecanismo
    if not is_logical_consequence(extraction.mechanism, extraction.outcome):
        issues.append("Outcome não parece resultar do mecanismo descrito")

    return issues
```

### Passo 4: Gerar Sugestões de Correção
```python
def suggest_corrections(validation_result: FullValidationResult) -> list[Suggestion]:
    """Gera sugestões de correção baseadas nos erros encontrados."""
    suggestions = []

    for error in validation_result.errors:
        if "muito curto" in error:
            suggestions.append(Suggestion(
                type="expand",
                message="Solicitar re-extração com prompt mais detalhado",
                prompt_hint="Extraia mais detalhes sobre {component}"
            ))
        elif "red flag" in error:
            suggestions.append(Suggestion(
                type="reextract",
                message="Conteúdo genérico detectado, re-extrair com foco",
                prompt_hint="Seja específico sobre {component}, evite termos genéricos"
            ))

    return suggestions
```

## Template de Relatório

```markdown
## Relatório de Validação CIMO

**Artigo**: {article_id}
**Data**: {timestamp}
**Score Geral**: {overall_score}/100

### Context
- **Status**: {valid/invalid}
- **Score**: {score}/100
- **Erros**: {errors}
- **Avisos**: {warnings}

### Intervention
- **Status**: {valid/invalid}
- **Score**: {score}/100
- **Erros**: {errors}
- **Avisos**: {warnings}

### Mechanism
- **Status**: {valid/invalid}
- **Score**: {score}/100
- **Erros**: {errors}
- **Avisos**: {warnings}

### Outcome
- **Status**: {valid/invalid}
- **Score**: {score}/100
- **Erros**: {errors}
- **Avisos**: {warnings}

### Consistência Cruzada
{cross_validation_issues}

### Sugestões de Correção
{suggestions}

### Decisão
- [ ] Aprovado para uso
- [ ] Requer re-extração parcial
- [ ] Requer re-extração completa
- [ ] Requer revisão manual
```

## Scores e Thresholds

| Score | Classificação | Ação |
|-------|--------------|------|
| 90-100 | Excelente | Aprovar |
| 75-89 | Bom | Aprovar com avisos |
| 60-74 | Aceitável | Revisar manualmente |
| 40-59 | Baixo | Re-extrair componentes |
| 0-39 | Inaceitável | Re-extrair completo |

## Métricas de Sucesso

- Taxa de aprovação automática >= 70%
- Precisão de validação >= 90%
- Falsos positivos (rejeição indevida) < 5%
- Falsos negativos (aprovação indevida) < 10%
