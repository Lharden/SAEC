# SAEC-O&G Custom Subagents

Subagents especializados para o projeto SAEC-O&G (Sistema Autônomo de Extração CIMO).

## Visão Geral

| Subagent | Função | Prioridade | Economia |
|----------|--------|------------|----------|
| [saec-test-generator](saec-test-generator.md) | Gera testes pytest automaticamente | Alta | 60% tempo testes |
| [saec-cimo-validator](saec-cimo-validator.md) | Valida extrações CIMO semanticamente | Alta | +25% precisão |
| [saec-pdf-analyzer](saec-pdf-analyzer.md) | Analisa qualidade de extração PDF | Média | 40% tempo debug |
| [saec-llm-cost-optimizer](saec-llm-cost-optimizer.md) | Otimiza custos de API LLM | Média | 15-30% custos |
| [saec-performance-profiler](saec-performance-profiler.md) | Perfila e otimiza performance | Média | 50% tempo profiling |

## Como Usar

### Via Task Tool (Recomendado)
```
Solicite ao Claude: "Use o subagent saec-test-generator para criar testes para validators.py"
```

### Via Prompt Direto
```
Leia o arquivo .claude/agents/saec-test-generator.md e siga as instruções para gerar testes.
```

## Workflow Integrado

```
┌─────────────────┐
│  Novo Código    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ saec-test-      │ ──▶ Gera testes automaticamente
│ generator       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Extração LLM    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ saec-cimo-      │ ──▶ Valida qualidade semântica
│ validator       │
└────────┬────────┘
         │
    ┌────┴────┐
    │ Falha?  │
    └────┬────┘
         │ Sim
         ▼
┌─────────────────┐
│ saec-pdf-       │ ──▶ Diagnostica problemas de PDF
│ analyzer        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Auditoria       │
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌────────┐ ┌────────┐
│ Cost   │ │ Perf   │
│Optimizer│ │Profiler│
└────────┘ └────────┘
```

## Manutenção

- **Atualizar**: Quando padrões do projeto mudarem
- **Versionar**: Incrementar versão em metadata ao modificar
- **Testar**: Validar instruções antes de commitar

## Contribuindo

1. Criar novo arquivo `saec-<nome>.md`
2. Seguir estrutura dos existentes
3. Adicionar à tabela neste README
4. Atualizar CLAUDE.md na raiz
