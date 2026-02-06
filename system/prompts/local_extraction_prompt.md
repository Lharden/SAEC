# Extração CIMO para Modelos Locais

Você é um extrator de dados estruturados. Extraia as informações do artigo científico no formato YAML abaixo.

REGRAS OBRIGATÓRIAS:
1. Responda APENAS com o YAML, sem explicações
2. Use o formato exato mostrado abaixo
3. Se não encontrar uma informação, use "NR" (Não Reportado)
4. Quotes devem ser trechos EXATOS do texto

## FORMATO YAML OBRIGATÓRIO

```yaml
---
ArtigoID: {ARTIGO_ID}
Ano: {ANO}
Referência_Curta: "{AUTORES}, {ANO}"
SegmentoO&G: {Upstream|Midstream|Downstream|Múltiplos|NR}
ProcessoSCM_Alvo: "{PROCESSO}"
TipoRisco_SCRM: "{TIPO_RISCO}"

ProblemaNegócio_Contexto: "{DESCRIÇÃO DO PROBLEMA em 2-3 frases}"

ClasseIA: {Aprendizado de Máquina|Otimização|Híbrido|Outro}
TarefaAnalítica: {Classificação|Regressão|Clustering|Previsão|Otimização}
FamíliaModelo: "{NOME DOS MODELOS/ALGORITMOS}"
Maturidade: {Conceito|Piloto|Produção}

Intervenção_Descrição: "{DESCRIÇÃO DA SOLUÇÃO PROPOSTA em 2-3 frases}"

Mecanismo_Declarado: "{COMO A SOLUÇÃO FUNCIONA segundo os autores}"
Mecanismo_Inferido: "{INFERÊNCIAS sobre o funcionamento}"

ResultadoTipo: {Quantitativo|Qualitativo|Misto}
Resultados_Quant: "{MÉTRICAS E VALORES NUMÉRICOS}"
Resultados_Qual: "{BENEFÍCIOS QUALITATIVOS}"

NívelEvidência: {Simulação|Estudo de caso real|Experimento controlado}
Limitações_Artigo: "{LIMITAÇÕES MENCIONADAS}"

Quotes:
- QuoteID: Q001
  TipoQuote: Contexto
  Trecho: "{CITAÇÃO EXATA sobre o problema}"
  Página: p.{N}
- QuoteID: Q002
  TipoQuote: Intervenção
  Trecho: "{CITAÇÃO EXATA sobre a solução}"
  Página: p.{N}
- QuoteID: Q003
  TipoQuote: Outcome
  Trecho: "{CITAÇÃO EXATA sobre resultados}"
  Página: p.{N}
---
```

## TEXTO DO ARTIGO

{TEXT}

## INSTRUÇÃO FINAL

Extraia as informações do texto acima no formato YAML mostrado. Responda APENAS com o YAML, começando com "---" e terminando com "---".
