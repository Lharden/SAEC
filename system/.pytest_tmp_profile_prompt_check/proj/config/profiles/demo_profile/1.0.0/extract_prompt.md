# Universal Extraction Prompt (CUSTOM)

Objetivo:
Extrair dados do artigo e retornar SOMENTE YAML valido conforme o perfil ativo.

Regras gerais obrigatorias:
- Retorne apenas YAML, sem texto antes/depois.
- Use apenas campos declarados no perfil ativo.
- Nao invente valores sem evidencia no texto/imagens do artigo.
- Mantenha nomes de campos exatamente como definidos no perfil.
- Preserve consistencia semantica entre campos relacionados.
- Quando faltar evidencia explicita, use NR ou vazio conforme o contrato do campo.
- Quando houver quotes, use trechos literais e com pagina/secao quando aplicavel.

Campos do perfil ativo:
- ArtigoID (string, obrigatorio)

Politica de quotes:
- Quantidade: 0 a 0
- Campos por quote: QuoteID, TipoQuote, Trecho, Página
- Padrao de QuoteID: ^Q\d{3}$

Checklist final antes de responder:
- YAML valido e completo.
- Sem campos fora do perfil.
- Regras do perfil respeitadas.
- Sem alucinacoes.
