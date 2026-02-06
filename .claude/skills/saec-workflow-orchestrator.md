---
name: saec-workflow-orchestrator
description: Orquestra automaticamente o uso de subagents, skills e validações no projeto SAEC-O&G. USE PROATIVAMENTE no início de cada sessão ou tarefa complexa.
autoInvoke: true
triggers:
  - session_start
  - complex_task
  - code_modification
---

# SAEC Workflow Orchestrator

## Propósito
Este skill garante que todas as automações do projeto SAEC-O&G sejam aplicadas consistentemente, sem depender da memória do usuário.

## Ativação Automática

Este skill deve ser mentalmente ativado (seguir suas regras) sempre que:
1. Uma nova sessão começar neste projeto
2. O usuário pedir para implementar algo
3. O usuário reportar um problema
4. Código for modificado

## Matriz de Decisão

```
┌─────────────────────────────────────────────────────────────────┐
│                    TAREFA RECEBIDA                               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │ É um BUG/ERRO?  │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │ SIM          │              │ NÃO
              ▼              │              ▼
┌─────────────────────┐      │    ┌─────────────────────┐
│ /superpowers:       │      │    │ É IMPLEMENTAÇÃO?    │
│ systematic-debugging│      │    └──────────┬──────────┘
└─────────────────────┘      │               │
                             │    ┌──────────┼──────────┐
                             │    │ SIM      │          │ NÃO
                             │    ▼          │          ▼
                             │ ┌────────────────┐  ┌────────────────┐
                             │ │ /superpowers:  │  │ É REFATORAÇÃO? │
                             │ │ test-driven-   │  └───────┬────────┘
                             │ │ development    │          │
                             │ └────────────────┘   ┌──────┼──────┐
                             │                      │ SIM  │      │ NÃO
                             │                      ▼      │      ▼
                             │              ┌────────────┐ │ ┌────────────┐
                             │              │EnterPlanMode│ │ │ Continuar  │
                             │              └────────────┘ │ │ normalmente│
                             │                             │ └────────────┘
                             │                             │
                             └─────────────────────────────┘
```

## Regras de Execução

### ANTES de Escrever Código
1. Verificar se existe teste para a funcionalidade
2. Se não existe → Criar teste primeiro (TDD)
3. Se complexo → Usar EnterPlanMode

### DURANTE Escrita de Código
1. Monitorar arquivos modificados
2. Se `system/src/*.py` → Preparar para gerar testes
3. Se `llm_client*.py` → Verificar timeouts e retry
4. Se prompts → Considerar impacto em custos

### APÓS Escrever Código
1. Rodar testes relacionados
2. Verificar type hints (mypy)
3. Se extração CIMO → Validar com saec-cimo-validator
4. Se PDF processing → Verificar com saec-pdf-analyzer

### ANTES de Declarar Conclusão
1. **OBRIGATÓRIO**: Rodar `/superpowers:verification-before-completion`
2. Confirmar que testes passam
3. Confirmar que não há erros mypy
4. Se commit solicitado → Verificar staged files

## Mensagens de Lembrança

Quando detectar padrões, incluir na resposta:

### Para Bugs
> 🔍 **Detectei um problema.** Vou aplicar debugging sistemático antes de propor solução.

### Para Implementações
> 🧪 **Nova funcionalidade.** Vou criar testes primeiro seguindo TDD.

### Para Conclusões
> ✅ **Antes de finalizar**, vou verificar que tudo está funcionando corretamente.

### Para Performance
> ⚡ **Identificado possível gargalo.** Vou analisar com o profiler.

## Integração com Subagents

### Invocação Automática
Quando as condições forem atendidas, informar o usuário e executar:

```
"Detectei [CONDIÇÃO]. Vou usar o subagent [NOME] para [AÇÃO]."
```

### Exemplo Real
```
Usuário: "A extração do artigo 42 ficou estranha"

Claude: "Detectei possível problema de qualidade na extração.
Vou usar o saec-cimo-validator para analisar a extração
e o saec-pdf-analyzer se houver problemas com o PDF de origem."

[Executa análise seguindo instruções dos subagents]
```

## Fluxo Completo de Uma Tarefa

```
1. RECEBER tarefa
   └─> Classificar (bug/feature/refactor/análise)

2. PLANEJAR (se necessário)
   └─> EnterPlanMode ou /superpowers:writing-plans

3. PREPARAR
   └─> Criar testes (TDD) se implementação

4. EXECUTAR
   └─> Implementar com verificações contínuas

5. VALIDAR
   └─> Subagents relevantes + testes + mypy

6. FINALIZAR
   └─> /superpowers:verification-before-completion

7. ENTREGAR
   └─> Resumo do que foi feito + próximos passos
```

## Checklist Mental (Revisar a Cada Tarefa)

- [ ] Entendi completamente o que foi pedido?
- [ ] Preciso de mais contexto? (usar Explore agent)
- [ ] É complexo o suficiente para planejar?
- [ ] Testes existem ou preciso criar?
- [ ] Quais subagents são relevantes?
- [ ] Verifiquei antes de declarar pronto?
