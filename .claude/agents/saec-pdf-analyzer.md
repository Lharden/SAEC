# SAEC PDF Analyzer Subagent

## Metadata
```yaml
name: saec-pdf-analyzer
version: 1.0.0
description: Analisa qualidade de extração de PDFs e sugere melhorias nas heurísticas
trigger: Quando extração de PDF falha, tem baixa qualidade, ou para otimização
priority: medium
estimated_savings: 40% do tempo de debug em problemas de extração
```

## Objetivo

Analisar a qualidade da extração de texto de PDFs científicos, identificar padrões de falha, e sugerir ajustes nas heurísticas de extração do projeto SAEC-O&G.

## Quando Usar

- Após falha de extração de PDF
- Quando texto extraído está corrompido ou incompleto
- Para auditar qualidade de batch de extrações
- Antes de processar novo tipo/fonte de PDFs
- Ao otimizar heurísticas de extração

## Contexto Técnico

O SAEC-O&G usa:
- **PyMuPDF (fitz)**: Extração primária de texto
- **pdf2image + Tesseract**: OCR para PDFs escaneados
- **Claude Vision**: Análise visual de páginas problemáticas
- Arquivos em: `Extraction/pdfs/` e `Extraction/outputs/`

## Padrões de Problemas Comuns

### 1. Layout Multi-Coluna
```python
MULTICOLUMN_INDICATORS = {
    "patterns": [
        r"(?m)^.{30,50}\s{10,}.{30,50}$",  # Grandes espaços no meio
        r"(?m)^\d+\s+\d+$",  # Números de página lado a lado
    ],
    "symptoms": [
        "Frases interrompidas no meio",
        "Parágrafos misturados",
        "Referências numéricas deslocadas"
    ],
    "solutions": [
        "Usar extração por blocos com fitz.get_text('blocks')",
        "Ordenar blocos por posição (x, y)",
        "Detectar colunas e processar separadamente"
    ]
}
```

### 2. Tabelas Mal Extraídas
```python
TABLE_INDICATORS = {
    "patterns": [
        r"\d+\s+\d+\s+\d+\s+\d+",  # Sequência de números
        r"[A-Z][a-z]+\s{5,}\d",    # Texto seguido de muito espaço
    ],
    "symptoms": [
        "Dados tabulares em linha única",
        "Cabeçalhos separados de valores",
        "Alinhamento perdido"
    ],
    "solutions": [
        "Usar fitz.find_tables() para detecção",
        "Extrair tabelas como estruturas separadas",
        "Aplicar heurística de grade"
    ]
}
```

### 3. PDFs Escaneados/Imagem
```python
SCANNED_INDICATORS = {
    "detection": [
        "Texto extraído muito curto vs páginas",
        "Caracteres especiais excessivos",
        "Ratio texto/página < 100 chars"
    ],
    "symptoms": [
        "Texto vazio ou quase vazio",
        "Caracteres ilegíveis (□, ■, etc.)",
        "Encoding incorreto"
    ],
    "solutions": [
        "Detectar via fitz.get_text() vazio",
        "Aplicar OCR com Tesseract",
        "Usar Claude Vision para páginas críticas"
    ]
}
```

### 4. Caracteres Especiais/Encoding
```python
ENCODING_INDICATORS = {
    "patterns": [
        r"[^\x00-\x7F]{3,}",  # Sequência de não-ASCII
        r"�{2,}",             # Replacement characters
        r"\\x[0-9a-f]{2}",    # Escape sequences
    ],
    "symptoms": [
        "Acentos convertidos em símbolos",
        "Ligaduras não resolvidas (fi, fl, ff)",
        "Símbolos matemáticos corrompidos"
    ],
    "solutions": [
        "Normalizar Unicode (NFKC)",
        "Mapear ligaduras comuns",
        "Detectar e corrigir encoding"
    ]
}
```

### 5. Cabeçalhos/Rodapés Repetidos
```python
HEADER_FOOTER_INDICATORS = {
    "detection": [
        "Texto idêntico em múltiplas páginas",
        "Números de página sequenciais",
        "Nome do journal repetido"
    ],
    "symptoms": [
        "Ruído no texto extraído",
        "Fragmentação de parágrafos",
        "Metadados misturados com conteúdo"
    ],
    "solutions": [
        "Detectar e remover por posição (top/bottom 10%)",
        "Usar regex para padrões comuns",
        "Comparar texto entre páginas"
    ]
}
```

## Instruções de Execução

### Passo 1: Coletar Informações do PDF
```python
def analyze_pdf_structure(pdf_path: Path) -> PDFAnalysis:
    """Analisa estrutura do PDF."""
    doc = fitz.open(pdf_path)

    analysis = PDFAnalysis(
        page_count=len(doc),
        has_text=False,
        has_images=False,
        is_scanned=False,
        has_tables=False,
        encoding_issues=False
    )

    for page in doc:
        text = page.get_text()
        blocks = page.get_text("blocks")
        images = page.get_images()

        analysis.has_text |= len(text) > 100
        analysis.has_images |= len(images) > 0
        analysis.pages.append(PageAnalysis(
            page_num=page.number,
            text_length=len(text),
            block_count=len(blocks),
            image_count=len(images),
            text_sample=text[:500]
        ))

    # Detectar se é escaneado
    avg_text = sum(p.text_length for p in analysis.pages) / len(analysis.pages)
    analysis.is_scanned = avg_text < 100 and analysis.has_images

    return analysis
```

### Passo 2: Identificar Problemas
```python
def identify_issues(analysis: PDFAnalysis, extracted_text: str) -> list[Issue]:
    """Identifica problemas na extração."""
    issues = []

    # Verificar texto escaneado
    if analysis.is_scanned:
        issues.append(Issue(
            type="scanned_pdf",
            severity="high",
            description="PDF parece ser escaneado, OCR necessário",
            affected_pages=list(range(analysis.page_count))
        ))

    # Verificar encoding
    encoding_errors = re.findall(r'[�□■]', extracted_text)
    if len(encoding_errors) > 10:
        issues.append(Issue(
            type="encoding_issues",
            severity="medium",
            description=f"{len(encoding_errors)} caracteres com problema de encoding",
            sample=encoding_errors[:10]
        ))

    # Verificar multi-coluna
    if has_multicolumn_pattern(extracted_text):
        issues.append(Issue(
            type="multicolumn_layout",
            severity="medium",
            description="Layout multi-coluna detectado, possível mistura de texto"
        ))

    # Verificar tabelas
    if has_table_patterns(extracted_text):
        issues.append(Issue(
            type="table_extraction",
            severity="low",
            description="Possíveis tabelas mal extraídas"
        ))

    return issues
```

### Passo 3: Gerar Recomendações
```python
def generate_recommendations(issues: list[Issue]) -> list[Recommendation]:
    """Gera recomendações baseadas nos problemas encontrados."""
    recommendations = []

    for issue in issues:
        if issue.type == "scanned_pdf":
            recommendations.append(Recommendation(
                action="apply_ocr",
                description="Aplicar OCR com Tesseract ou Claude Vision",
                code_hint="""
# Em pdf_reader.py
if is_scanned_page(page):
    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
    text = pytesseract.image_to_string(pix.tobytes())
"""
            ))

        elif issue.type == "multicolumn_layout":
            recommendations.append(Recommendation(
                action="block_extraction",
                description="Usar extração por blocos ordenados",
                code_hint="""
# Em pdf_reader.py
blocks = page.get_text("blocks")
blocks.sort(key=lambda b: (b[1], b[0]))  # Ordenar por y, depois x
text = "\\n".join(b[4] for b in blocks if b[6] == 0)
"""
            ))

        elif issue.type == "encoding_issues":
            recommendations.append(Recommendation(
                action="normalize_encoding",
                description="Normalizar Unicode e mapear ligaduras",
                code_hint="""
import unicodedata

def normalize_text(text: str) -> str:
    text = unicodedata.normalize('NFKC', text)
    ligatures = {'ﬁ': 'fi', 'ﬂ': 'fl', 'ﬀ': 'ff', 'ﬃ': 'ffi'}
    for lig, rep in ligatures.items():
        text = text.replace(lig, rep)
    return text
"""
            ))

    return recommendations
```

### Passo 4: Comparar Extração com Original
```python
def compare_extraction_quality(
    pdf_path: Path,
    extracted_text: str,
    sample_pages: list[int] = [0, 1, -1]
) -> QualityReport:
    """Compara qualidade da extração com análise visual."""
    doc = fitz.open(pdf_path)

    comparisons = []
    for page_num in sample_pages:
        page = doc[page_num]

        # Extração direta
        direct_text = page.get_text()

        # Extração por blocos
        blocks_text = extract_by_blocks(page)

        # Métricas
        comparisons.append(PageComparison(
            page_num=page_num,
            direct_length=len(direct_text),
            blocks_length=len(blocks_text),
            similarity=calculate_similarity(direct_text, blocks_text),
            recommended_method="blocks" if len(blocks_text) > len(direct_text) else "direct"
        ))

    return QualityReport(
        pdf_path=pdf_path,
        overall_quality=calculate_overall_quality(comparisons),
        comparisons=comparisons,
        best_method=determine_best_method(comparisons)
    )
```

## Template de Relatório

```markdown
## Relatório de Análise de PDF

**Arquivo**: {pdf_path}
**Data**: {timestamp}
**Qualidade Geral**: {quality_score}/100

### Estrutura do PDF
- **Páginas**: {page_count}
- **Tipo**: {pdf_type} (nativo/escaneado/misto)
- **Tem tabelas**: {has_tables}
- **Tem imagens**: {has_images}

### Problemas Identificados

{for issue in issues}
#### {issue.type}
- **Severidade**: {issue.severity}
- **Descrição**: {issue.description}
- **Páginas afetadas**: {issue.affected_pages}
{endfor}

### Recomendações

{for rec in recommendations}
#### {rec.action}
{rec.description}

```python
{rec.code_hint}
```
{endfor}

### Comparação de Métodos de Extração

| Página | Direto | Blocos | Recomendado |
|--------|--------|--------|-------------|
{comparison_table}

### Ações Sugeridas
1. {action_1}
2. {action_2}
3. {action_3}
```

## Métricas de Sucesso

- Taxa de extração bem-sucedida >= 90%
- Tempo de análise < 30s por PDF
- Precisão de diagnóstico >= 85%
- Recomendações acionáveis em 100% dos casos
