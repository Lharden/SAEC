"""Pós-processamento determinístico para correção automática de campos.

Este módulo contém funções que CORRIGEM automaticamente campos que podem
ser calculados deterministicamente a partir de outros campos, sem depender
de interpretação do LLM.

Uso típico no pipeline:
    yaml_content = llm.extract(...)
    yaml_content = postprocess_yaml(yaml_content)  # Correção automática
    validation = validator.validate(yaml_content)   # Validação
"""

import re

import yaml


def _wrap_to_multiline(text: str, min_lines: int = 3, max_lines: int = 6) -> str:
    """Força um texto a ter múltiplas linhas (para padronização no YAML).

    Estratégia: divide em sentenças e distribui em linhas (sem mudar palavras).

    - Se já tem quebras de linha suficientes, mantém.
    - Se não, cria quebras após sentenças.

    Observação: isso não "melhora" o conteúdo, só o formato para ficar consistente.
    """
    if not isinstance(text, str):
        return text

    raw = text.strip()
    if not raw:
        return text

    # Se já tem pelo menos min_lines linhas não vazias, deixa.
    existing_lines = [l.strip() for l in raw.split("\n") if l.strip()]
    if len(existing_lines) >= min_lines:
        return "\n".join(existing_lines)

    # Split simples por sentença (mantém texto; pode não ser perfeito, mas é determinístico)
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", raw) if p.strip()]

    if len(parts) <= 1:
        # fallback: quebra por tamanho
        words = raw.split()
        if len(words) < 20:
            return raw
        chunk = max(10, len(words) // max_lines)
        lines = [" ".join(words[i:i+chunk]) for i in range(0, len(words), chunk)]
        lines = [l.strip() for l in lines if l.strip()]
        return "\n".join(lines[:max_lines])

    # Montar linhas até max_lines
    lines_out: list[str] = []
    for p in parts:
        if len(lines_out) < max_lines:
            lines_out.append(p)
        else:
            # se estourou, agrega no último
            lines_out[-1] = (lines_out[-1] + " " + p).strip()

    # Garantir mínimo de linhas: se ainda ficou curto, força quebra por tamanho
    if len(lines_out) < min_lines and len(lines_out) >= 1:
        words = " ".join(lines_out).split()
        chunk = max(10, len(words) // min_lines)
        lines_out = [" ".join(words[i:i+chunk]) for i in range(0, len(words), chunk)]
        lines_out = [l.strip() for l in lines_out if l.strip()]

    return "\n".join(lines_out[:max_lines])


def recalculate_complexidade(data: dict) -> dict:
    """
    Recalcula Complexidade a partir de F1, F2, F3 na justificativa.

    Regra do Guia:
        3 pontos → Alta
        2 pontos → Média
        0-1 pontos → Baixa

    Args:
        data: Dicionário com dados YAML parseados

    Returns:
        Dicionário com Complexidade corrigida (se aplicável)
    """
    justif = data.get("Complexidade_Justificativa", "")
    if not justif:
        return data

    # Extrair F1, F2, F3
    f1_match = re.search(r"F1\s*=\s*(\d+)", justif, re.IGNORECASE)
    f2_match = re.search(r"F2\s*=\s*(\d+)", justif, re.IGNORECASE)
    f3_match = re.search(r"F3\s*=\s*(\d+)", justif, re.IGNORECASE)

    if f1_match and f2_match and f3_match:
        f1 = int(f1_match.group(1))
        f2 = int(f2_match.group(1))
        f3 = int(f3_match.group(1))
        total = f1 + f2 + f3

        # Mapeamento determinístico
        mapping = {3: "Alta", 2: "Média", 1: "Baixa", 0: "Baixa"}
        correct_value = mapping.get(total, "NR")

        current = data.get("Complexidade", "")
        if current != correct_value:
            print(f"  [FIX] Complexidade '{current}' -> '{correct_value}' (F1={f1}+F2={f2}+F3={f3}={total}pts)")
            data["Complexidade"] = correct_value

    return data


def normalize_maturidade(data: dict) -> dict:
    """
    Corrige Maturidade se valor inválido (ex: confundido com NívelEvidência).

    Valores válidos: Conceito, Protótipo, Piloto, Produção, NR

    Heurística de correção:
        - "Estudo de caso real" → Piloto (dados reais, 1 empresa)
        - "Experimento com dados reais" → Piloto
        - "Simulação com dados sintéticos" → Protótipo
    """
    VALIDOS = ["Conceito", "Protótipo", "Piloto", "Produção", "NR"]
    maturidade = data.get("Maturidade", "")

    if maturidade in VALIDOS:
        return data

    # Heurísticas de correção para valores comuns errados
    correcoes = {
        "Estudo de caso real": "Piloto",
        "Experimento com dados reais": "Piloto",
        "Simulação com dados reais": "Piloto",
        "Simulação com dados sintéticos": "Protótipo",
        "Proposta teórica/framework": "Conceito",
    }

    if maturidade in correcoes:
        novo = correcoes[maturidade]
        print(f"  [FIX] Maturidade '{maturidade}' -> '{novo}' (valor original era NivelEvidencia)")
        data["Maturidade"] = novo

    return data


def normalize_familia_modelo(data: dict) -> dict:
    """
    Adiciona warning se FamíliaModelo contém termos mal classificados.

    NÃO altera automaticamente, apenas registra para revisão.
    """
    familia = data.get("FamíliaModelo", "").lower()
    intervencao = data.get("Intervenção_Descrição", "").lower()

    # Detectar uso errado de "Ensemble tree-based" quando o artigo usa CHAID/CART
    if "ensemble" in familia:
        # Verificar se há algoritmos de árvore única mencionados
        arvores_simples = ["chaid", "cart", "c4.5", "id3"]
        ensemble_reais = ["random forest", "xgboost", "gbm", "gradient boosting", "adaboost"]

        tem_arvore_simples = any(a in intervencao for a in arvores_simples)
        tem_ensemble_real = any(e in intervencao for e in ensemble_reais)

        if tem_arvore_simples and not tem_ensemble_real:
            print(f"  [WARN] FamíliaModelo='Ensemble' mas Intervenção menciona árvore simples (CHAID/CART)")
            # Poderia corrigir, mas é mais seguro alertar

    return data


def postprocess_yaml(yaml_content: str) -> str:
    """
    Pipeline completo de pós-processamento determinístico.

    Esta função aplica todas as correções automáticas que não dependem
    de interpretação do LLM.

    Args:
        yaml_content: String YAML bruta da extração

    Returns:
        String YAML com correções aplicadas
    """
    # Parse YAML
    try:
        docs = list(yaml.safe_load_all(yaml_content))
        data = docs[0] if docs else None
    except yaml.YAMLError:
        return yaml_content  # Retorna original se não conseguir parsear

    if not isinstance(data, dict):
        return yaml_content

    print("\n[POSTPROCESS] Pos-processamento deterministico:")

    # Aplicar correcoes
    data = recalculate_complexidade(data)
    data = normalize_maturidade(data)
    data = normalize_familia_modelo(data)

    # Padronização de narrativa (formato): garantir múltiplas linhas
    if isinstance(data.get("ProblemaNegócio_Contexto"), str):
        data["ProblemaNegócio_Contexto"] = _wrap_to_multiline(data["ProblemaNegócio_Contexto"], min_lines=3, max_lines=6)

    # Reconstruir YAML
    output = yaml.dump(
        data,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
        width=1000  # Evitar quebras de linha indesejadas
    )

    return f"---\n{output}---\n"


# ============================================================
# Funções Helper para uso standalone
# ============================================================

def postprocess_file(yaml_path: str, output_path: str | None = None) -> str:
    """Pós-processa um arquivo YAML e salva o resultado."""
    from pathlib import Path

    path = Path(yaml_path)
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    corrected = postprocess_yaml(content)

    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(corrected)
    else:
        # Sobrescreve o original
        with open(path, "w", encoding="utf-8") as f:
            f.write(corrected)

    return corrected
