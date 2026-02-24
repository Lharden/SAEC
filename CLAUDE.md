# SAEC - Sistema Autônomo de Extração CIMO

Pipeline Python para extração de dados CIMO (Contexto, Intervenção, Mecanismo, Outcome) de artigos científicos sobre IA + SCM/SCRM no setor de Óleo & Gás.

---

## REGRAS PROATIVAS OBRIGATÓRIAS

> **IMPORTANTE**: As regras abaixo são OBRIGATÓRIAS e devem ser seguidas AUTOMATICAMENTE sem que o usuário precise solicitar.

### Triggers Automáticos de Skills

| Quando Detectar | Ação Obrigatória |
|-----------------|------------------|
| Bug, erro, falha, teste falhando | Usar `/superpowers:systematic-debugging` ANTES de propor fix |
| Implementar feature nova | Usar `/superpowers:test-driven-development` - testes primeiro |
| Prestes a commitar ou declarar "pronto" | Usar `/superpowers:verification-before-completion` |
| Tarefa com 3+ etapas | Usar `/superpowers:writing-plans` para planejar |
| Código complexo ou legado | Usar `EnterPlanMode` antes de modificar |

### Triggers Automáticos de Subagents

| Quando Detectar | Subagent a Usar | Como |
|-----------------|-----------------|------|
| Criar/editar arquivo em `system/src/*.py` | `saec-test-generator` | Gerar testes após implementação |
| Extração CIMO concluída | `saec-cimo-validator` | Validar qualidade da extração |
| Erro em leitura de PDF | `saec-pdf-analyzer` | Diagnosticar problema |
| Modificar prompts LLM | `saec-llm-cost-optimizer` | Verificar impacto em custos |
| Processamento lento (> 2min) | `saec-performance-profiler` | Identificar bottleneck |

### Checklist de Qualidade (Verificar SEMPRE antes de finalizar)

- [ ] Testes existem para código novo?
- [ ] Type hints em funções públicas?
- [ ] Exceções apropriadas (`IngestError`, `ExtractError`, etc.)?
- [ ] Logging com campos estruturados?
- [ ] Timeout configurado em chamadas externas?

### Frases que Ativam Subagents

Quando o usuário disser algo parecido com:
- "não está funcionando" / "deu erro" → `systematic-debugging`
- "cria/implementa/adiciona" → `test-driven-development`
- "terminei" / "pronto" / "pode commitar" → `verification-before-completion`
- "tá lento" / "demora muito" → `saec-performance-profiler`
- "extração ficou ruim" → `saec-cimo-validator` + `saec-pdf-analyzer`
- "quanto tá custando" / "otimiza custos" → `saec-llm-cost-optimizer`

---

## Stack Técnico

- **Python**: 3.11+
- **LLM Providers**: Anthropic Claude, OpenAI, Ollama (local)
- **PDF Processing**: PyMuPDF (fitz), pdf2image
- **Data Validation**: Pydantic v2
- **Testing**: pytest
- **Type Checking**: mypy, pyright

## Estrutura do Projeto

```
system/
├── src/
│   ├── context.py          # AppContext (DI container)
│   ├── config.py           # Configurações e constantes
│   ├── exceptions.py       # Hierarquia de exceções
│   ├── llm_client_types.py # Cliente LLM com retry/timeout
│   ├── validators.py       # Validação de extrações (14 regras)
│   ├── processors.py       # ArticleProcessor principal
│   └── pipeline_*.py       # Etapas do pipeline
tests/
└── test_*.py               # Testes unitários
```

## Convenções de Código

- Type hints em todas as funções públicas
- Docstrings apenas onde a lógica não é auto-evidente
- Logging estruturado com campos `artigo_id`, `provider`, `action`
- Exceções específicas: `IngestError`, `ExtractError`, `ValidationError`, `LLMError`
- Timeout padrão: 120s total (10s connect, 110s read)
- Retry: 3 tentativas com exponential backoff + jitter

## Skills Proativas (USAR AUTOMATICAMENTE)

### Antes de Debugar
```
/superpowers:systematic-debugging
```
Investiga bugs metodicamente antes de propor correções.

### Antes de Implementar Features
```
/superpowers:test-driven-development
```
Escreve testes primeiro, depois implementação.

### Antes de Finalizar/Commitar
```
/superpowers:verification-before-completion
```
Verifica que tudo funciona antes de declarar conclusão.

### Para Tarefas Complexas
```
/superpowers:writing-plans
```
Cria plano de implementação antes de codificar.

### Para Refatoração
```
Skill: code-refactoring-refactor-clean
```
Aplica princípios SOLID e clean code.

## Subagents Disponíveis

### Agents Nativos do Claude Code

| Agent | Uso |
|-------|-----|
| **Explore** | Buscar código e entender a codebase |
| **Plan** | Planejar implementações complexas |
| **Bash** | Executar comandos de terminal |

```
Task(subagent_type="Explore", prompt="Find all LLM API calls and their error handling")
Task(subagent_type="Plan", prompt="Plan implementation of parallel article processing")
```

### Subagents Customizados SAEC

Definidos em `.claude/agents/`:

| Subagent | Trigger | Economia |
|----------|---------|----------|
| **saec-test-generator** | Após editar `system/src/` | 60% tempo testes |
| **saec-cimo-validator** | Após extração LLM | +25% precisão |
| **saec-pdf-analyzer** | Quando PDF falha | 40% tempo debug |
| **saec-llm-cost-optimizer** | Auditoria de custos | 15-30% custos API |
| **saec-performance-profiler** | Pipeline lento | 50% tempo profiling |

**Uso**:
```
"Use o subagent saec-test-generator para criar testes para validators.py"
"Aplique saec-cimo-validator na última extração"
"Execute saec-performance-profiler no pipeline completo"
```

## Comandos Úteis

```bash
# Rodar testes
python -m pytest tests/ -v

# Type checking
python -m mypy --config-file pyproject.toml system/

# Executar pipeline completo
python system/main.py

# Executar extração específica
python system/src/processors.py --article-id <ID>
```

## Padrões de Qualidade

- Cobertura de testes: mínimo 80%
- Zero erros mypy em código novo
- Funções com máximo 50 linhas
- Máximo 3 níveis de indentação
- Nomes descritivos em inglês

## Pastas Ignoradas (NÃO explorar/listar)

- `02 T2/` - Contém PDFs dos artigos. **Ignorar completamente** exceto se o usuário solicitar explicitamente.

## Arquivos Sensíveis (NUNCA EDITAR)

- `.env*` - Variáveis de ambiente
- `*credentials*` - Credenciais
- `*_key*` - API keys
- `*.lock` - Lock files de dependências

## Fluxo de Trabalho Ideal

1. **Entender**: Use Explore agent para contexto
2. **Planejar**: Use Plan agent ou `/superpowers:writing-plans`
3. **Testar**: Use `/superpowers:test-driven-development`
4. **Implementar**: Código incremental com verificação
5. **Validar**: Use `/superpowers:verification-before-completion`
6. **Revisar**: Use `/superpowers:requesting-code-review`
7. **Commitar**: Use `/commit` com mensagem descritiva

---

## LEMBRETE FINAL (SEMPRE CONSULTAR)

```
╔══════════════════════════════════════════════════════════════════╗
║  ANTES DE CADA RESPOSTA, VERIFICAR:                              ║
║                                                                  ║
║  □ É um bug? → systematic-debugging PRIMEIRO                     ║
║  □ É feature? → test-driven-development PRIMEIRO                 ║
║  □ Vou finalizar? → verification-before-completion PRIMEIRO      ║
║  □ Editei system/src/? → Gerar testes com saec-test-generator    ║
║  □ Extração CIMO? → Validar com saec-cimo-validator              ║
║  □ PDF com problema? → Analisar com saec-pdf-analyzer            ║
║  □ Performance ruim? → Usar saec-performance-profiler            ║
║  □ Custos de API? → Usar saec-llm-cost-optimizer                 ║
║                                                                  ║
║  SE DETECTAR PADRÃO → USAR AUTOMAÇÃO → INFORMAR USUÁRIO          ║
╚══════════════════════════════════════════════════════════════════╝
```

### Frases-Gatilho do Usuário

| Se o usuário disser... | Eu devo automaticamente... |
|------------------------|---------------------------|
| "erro", "bug", "não funciona", "quebrou" | Aplicar systematic-debugging |
| "implementa", "cria", "adiciona", "faz" | Aplicar TDD (testes primeiro) |
| "pronto", "terminei", "pode commitar" | Aplicar verification-before-completion |
| "lento", "demora", "travando" | Usar saec-performance-profiler |
| "extração ruim", "dados errados" | Usar saec-cimo-validator |
| "PDF", "não lê", "texto errado" | Usar saec-pdf-analyzer |
| "caro", "custo", "tokens" | Usar saec-llm-cost-optimizer |
| "refatora", "melhora", "limpa" | Usar EnterPlanMode primeiro |

### Formato de Resposta Proativa

Quando detectar um trigger, começar a resposta com:

```
🔄 **Automação Ativada**: [nome do skill/subagent]
📋 **Motivo**: [por que foi ativado]
⏳ **Ação**: [o que será feito]
```

Exemplo:
```
🔄 **Automação Ativada**: systematic-debugging
📋 **Motivo**: Detectei relato de erro no código
⏳ **Ação**: Vou investigar metodicamente antes de propor correção
```

