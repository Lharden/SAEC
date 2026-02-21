"""Validador das 12 regras de negócio do Guia v3.3."""

import re
import yaml
from dataclasses import dataclass, field
from typing import Any
from pathlib import Path

# Importar schema (com tratamento de erro para execução standalone)
import importlib


def _load_schemas():
    try:
        return importlib.import_module(".schemas", package=__package__)
    except (ImportError, ModuleNotFoundError, TypeError):  # pragma: no cover - standalone usage
        return importlib.import_module("schemas")


_schemas = _load_schemas()
ExtractionSchema = _schemas.ExtractionSchema
validate_extraction_dict = _schemas.validate_extraction_dict


def _load_profile_engine():
    try:
        return importlib.import_module(".profile_engine", package=__package__)
    except (ImportError, ModuleNotFoundError, TypeError):  # pragma: no cover - standalone usage
        try:
            return importlib.import_module("profile_engine")
        except (ImportError, ModuleNotFoundError):
            return None


_profile_engine = _load_profile_engine()


@dataclass
class ValidationResult:
    """Resultado de validação."""

    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    rules_passed: list[int] = field(default_factory=list)
    rules_failed: list[int] = field(default_factory=list)

    def __str__(self) -> str:
        if self.is_valid:
            status = "APROVADO"
        else:
            status = "REPROVADO"

        lines = [status]

        if self.errors:
            lines.append(f"\nErros ({len(self.errors)}):")
            for e in self.errors:
                lines.append(f"  - {e}")

        if self.warnings:
            lines.append(f"\nAvisos ({len(self.warnings)}):")
            for w in self.warnings:
                lines.append(f"  WARN: {w}")

        if self.rules_failed:
            lines.append(f"\nRegras violadas: {self.rules_failed}")

        return "\n".join(lines)

    def to_dict(self) -> dict:
        """Converte para dicionário (para salvar em JSON)."""
        return {
            "is_valid": self.is_valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "rules_passed": self.rules_passed,
            "rules_failed": self.rules_failed
        }


class YAMLValidator:
    """Validador completo para YAML de extração."""

    # Keywords para Regra 11
    LIMITATION_KEYWORDS = ["limit", "restrict", "challeng", "only", "constrain", "caveat", "threat"]

    def _normalize_yaml_text(self, yaml_content: str) -> str:
        """Normaliza texto antes do parse.

        Objetivo: evitar reparos desnecessários por problemas mecânicos comuns, ex:
        - texto extra antes do YAML
        - múltiplos documentos por causa de '---' repetido
        - ausência de delimitadores

        Retorna uma string YAML mais "parseável".
        """
        text = (yaml_content or "").strip()
        if not text:
            return text

        # Se houver texto antes do YAML, cortar no primeiro marcador provável.
        # Preferir '---' e depois 'ArtigoID:' como âncora.
        if "---" in text:
            # pega do primeiro --- em diante
            text = text[text.find("---"):].strip()
        elif "ArtigoID" in text:
            text = text[text.find("ArtigoID"):].strip()

        # Garantir que começa com --- (padroniza) quando parece YAML.
        if text.startswith("ArtigoID"):
            text = "---\n" + text

        return text

    def validate(self, yaml_content: str) -> ValidationResult:
        """
        Valida YAML em 3 camadas: parse, schema, regras.

        Args:
            yaml_content: Conteúdo YAML como string

        Returns:
            ValidationResult com status e detalhes
        """
        errors: list[str] = []
        warnings: list[str] = []
        rules_passed: list[int] = []
        rules_failed: list[int] = []

        yaml_content = self._normalize_yaml_text(yaml_content)

        # CAMADA 1: Parse YAML
        try:
            docs = list(yaml.safe_load_all(yaml_content))
            data = docs[0] if docs else None
        except yaml.YAMLError as e:
            return ValidationResult(
                is_valid=False,
                errors=[f"[PARSE] YAML inválido: {str(e)[:200]}"],
                warnings=[],
                rules_passed=[],
                rules_failed=[],
            )

        if not isinstance(data, dict):
            return ValidationResult(
                is_valid=False,
                errors=["[PARSE] YAML deve ser um dicionário/mapeamento"],
                warnings=[],
                rules_passed=[],
                rules_failed=[],
            )

        # CAMADA 2: Schema Pydantic
        schema_valid, schema_errors = validate_extraction_dict(data)
        if not schema_valid:
            for err in schema_errors:
                errors.append(f"[SCHEMA] {err}")

        # CAMADA 3: Regras de negócio
        self._validate_rule_1(data, errors, rules_passed, rules_failed)
        self._validate_rule_2(data, errors, warnings, rules_passed, rules_failed)
        self._validate_rule_3(data, errors, rules_passed, rules_failed)
        self._validate_rule_4(data, errors, rules_passed, rules_failed)
        self._validate_rule_5(data, errors, rules_passed, rules_failed)
        self._validate_rule_6(data, errors, rules_passed, rules_failed)
        self._validate_rule_7(data, errors, rules_passed, rules_failed)
        self._validate_rule_8(data, errors, rules_passed, rules_failed)
        self._validate_rule_9(data, errors, rules_passed, rules_failed)
        self._validate_rule_10(data, warnings, rules_passed)
        self._validate_rule_11(data, warnings, rules_passed)
        self._validate_rule_12(rules_passed)

        self._validate_quotes(data, errors, warnings)
        self._validate_narratives(data, warnings)

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            rules_passed=sorted(set(rules_passed)),
            rules_failed=sorted(set(rules_failed)),
        )

    def _validate_rule_1(self, data: dict, errors: list[str], rules_passed: list[int], rules_failed: list[int]) -> None:
        tipo_risco = data.get("TipoRisco_SCRM", "")
        objeto_critico = data.get("ObjetoCrítico", "")

        if objeto_critico is None:
            objeto_critico = ""
        elif not isinstance(objeto_critico, str):
            objeto_critico = str(objeto_critico)

        if tipo_risco and tipo_risco != "NR":
            if not objeto_critico or objeto_critico.strip() == "":
                errors.append(f"[R1] TipoRisco_SCRM='{tipo_risco}' mas ObjetoCrítico está vazio")
                rules_failed.append(1)
            else:
                rules_passed.append(1)
        else:
            rules_passed.append(1)

    def _validate_rule_2(
        self,
        data: dict,
        errors: list[str],
        warnings: list[str],
        rules_passed: list[int],
        rules_failed: list[int],
    ) -> None:
        resultado_tipo = data.get("ResultadoTipo", "")
        resultados_quant = data.get("Resultados_Quant", "")

        if resultados_quant is None:
            resultados_quant = ""
        elif not isinstance(resultados_quant, str):
            resultados_quant = str(resultados_quant)

        if resultado_tipo in ["Quantitativo", "Misto"]:
            if not resultados_quant or resultados_quant.strip() in ["", "NR"]:
                errors.append(f"[R2] ResultadoTipo='{resultado_tipo}' mas Resultados_Quant está vazio/NR")
                rules_failed.append(2)
            elif ":" not in resultados_quant:
                warnings.append("[R2] Resultados_Quant deve seguir formato 'métrica: valor (vs. baseline: X)'")
                rules_passed.append(2)
            else:
                rules_passed.append(2)
        else:
            rules_passed.append(2)

    def _validate_rule_3(self, data: dict, errors: list[str], rules_passed: list[int], rules_failed: list[int]) -> None:
        maturidade = data.get("Maturidade", "")
        nivel_evidencia = data.get("NívelEvidência", "")

        MATURIDADE_VALIDOS = ["Conceito", "Protótipo", "Piloto", "Produção", "NR"]
        if maturidade and maturidade not in MATURIDADE_VALIDOS:
            errors.append(
                f"[R3b] Maturidade='{maturidade}' inválida. "
                f"Valores permitidos: {', '.join(MATURIDADE_VALIDOS)}. "
                f"(Confundiu com NívelEvidência?)"
            )
            rules_failed.append(3)
        elif maturidade == "Produção":
            valid_evidences = ["Estudo de caso real", "Experimento com dados reais"]
            if nivel_evidencia not in valid_evidences:
                errors.append(f"[R3] Maturidade='Produção' incompatível com NívelEvidência='{nivel_evidencia}'")
                rules_failed.append(3)
            else:
                rules_passed.append(3)
        else:
            rules_passed.append(3)

    def _validate_rule_4(self, data: dict, errors: list[str], rules_passed: list[int], rules_failed: list[int]) -> None:
        classe_ia = data.get("ClasseIA", "")
        familia_modelo = data.get("FamíliaModelo", "")
        if classe_ia == "Híbrido":
            if ";" not in familia_modelo and "+" not in familia_modelo and "," not in familia_modelo:
                errors.append("[R4] ClasseIA='Híbrido' mas FamíliaModelo não lista múltiplas técnicas")
                rules_failed.append(4)
            else:
                rules_passed.append(4)
        else:
            rules_passed.append(4)

    def _validate_rule_5(self, data: dict, errors: list[str], rules_passed: list[int], rules_failed: list[int]) -> None:
        mec_inferido = data.get("Mecanismo_Inferido", "")

        if isinstance(mec_inferido, list):
            mec_inferido = " ".join(str(x).strip() for x in mec_inferido if str(x).strip())
        elif mec_inferido is None:
            mec_inferido = ""
        elif not isinstance(mec_inferido, str):
            mec_inferido = str(mec_inferido)

        if mec_inferido and mec_inferido.strip() not in ["", "NR"]:
            sentences = [s.strip() for s in re.split(r"[.;]", mec_inferido) if s.strip()]
            missing_prefix = []
            for sent in sentences:
                if len(sent) > 15 and not sent.upper().startswith("INFERIDO:"):
                    missing_prefix.append(sent[:40])

            if missing_prefix:
                errors.append(f"[R5] Mecanismo_Inferido: sentenças sem 'INFERIDO:': {missing_prefix[:2]}")
                rules_failed.append(5)
            else:
                rules_passed.append(5)
        else:
            rules_passed.append(5)

    def _validate_rule_6(self, data: dict, errors: list[str], rules_passed: list[int], rules_failed: list[int]) -> None:
        mec_estruturado = data.get("Mecanismo_Estruturado", "")
        if mec_estruturado:
            if "\n" in mec_estruturado.strip():
                errors.append("[R6] Mecanismo_Estruturado deve ser STRING ÚNICA (sem quebras de linha)")
                rules_failed.append(6)
            elif "→" not in mec_estruturado:
                errors.append("[R6] Mecanismo_Estruturado deve conter '→' (seta)")
                rules_failed.append(6)
            else:
                rules_passed.append(6)
        else:
            errors.append("[R6] Mecanismo_Estruturado é obrigatório")
            rules_failed.append(6)

    def _validate_rule_7(self, data: dict, errors: list[str], rules_passed: list[int], rules_failed: list[int]) -> None:
        artigo_id = data.get("ArtigoID", "")
        if not re.match(r"^ART_\d{3}$", artigo_id):
            errors.append(f"[R7] ArtigoID='{artigo_id}' deve ser no formato ART_001")
            rules_failed.append(7)
        else:
            rules_passed.append(7)

    def _validate_rule_8(self, data: dict, errors: list[str], rules_passed: list[int], rules_failed: list[int]) -> None:
        nivel_evidencia = data.get("NívelEvidência", "")
        maturidade = data.get("Maturidade", "")
        if nivel_evidencia == "Simulação com dados sintéticos":
            if maturidade in ["Produção", "Piloto"]:
                errors.append(
                    f"[R8] NívelEvidência='Simulação com dados sintéticos' incompatível com Maturidade='{maturidade}'"
                )
                rules_failed.append(8)
            else:
                rules_passed.append(8)
        else:
            rules_passed.append(8)

    def _validate_rule_9(self, data: dict, errors: list[str], rules_passed: list[int], rules_failed: list[int]) -> None:
        complex_just = data.get("Complexidade_Justificativa", "")
        if complex_just:
            has_f1 = bool(re.search(r"F1\s*=", complex_just, re.IGNORECASE))
            has_f2 = bool(re.search(r"F2\s*=", complex_just, re.IGNORECASE))
            has_f3 = bool(re.search(r"F3\s*=", complex_just, re.IGNORECASE))
            if not (has_f1 and has_f2 and has_f3):
                missing = []
                if not has_f1:
                    missing.append("F1")
                if not has_f2:
                    missing.append("F2")
                if not has_f3:
                    missing.append("F3")
                errors.append(f"[R9] Complexidade_Justificativa faltando: {', '.join(missing)}")
                rules_failed.append(9)
            else:
                rules_passed.append(9)

                complexidade = data.get("Complexidade", "")
                f1_match = re.search(r"F1\s*=\s*(\d+)", complex_just, re.IGNORECASE)
                f2_match = re.search(r"F2\s*=\s*(\d+)", complex_just, re.IGNORECASE)
                f3_match = re.search(r"F3\s*=\s*(\d+)", complex_just, re.IGNORECASE)

                if f1_match and f2_match and f3_match:
                    f1 = int(f1_match.group(1))
                    f2 = int(f2_match.group(1))
                    f3 = int(f3_match.group(1))
                    total = f1 + f2 + f3

                    expected_map = {3: "Alta", 2: "Média", 1: "Baixa", 0: "Baixa"}
                    expected = expected_map.get(total, "NR")

                    if complexidade != expected:
                        errors.append(
                            f"[R9b] Complexidade incorreta: F1={f1}+F2={f2}+F3={f3}={total}pts "
                            f"→ esperado '{expected}', encontrado '{complexidade}'"
                        )
                        rules_failed.append(9)
        else:
            errors.append("[R9] Complexidade_Justificativa é obrigatório")
            rules_failed.append(9)

    def _validate_rule_10(self, data: dict, warnings: list[str], rules_passed: list[int]) -> None:
        ambiente = data.get("Ambiente", "")
        if ambiente:
            warnings.append("[R10] Verifique: Ambiente reflete onde a IA ATUA, não onde o ativo opera")
        rules_passed.append(10)

    def _validate_rule_11(self, data: dict, warnings: list[str], rules_passed: list[int]) -> None:
        limitacoes = data.get("Limitações_Artigo", "")
        if limitacoes is None:
            limitacoes = ""
        elif not isinstance(limitacoes, str):
            limitacoes = str(limitacoes)

        if limitacoes and limitacoes.strip() == "NR":
            warnings.append(
                "[R11] Limitações_Artigo='NR' - confirme que o artigo não menciona: "
                "limit*, restrict*, challeng*, only, constrain*, caveat"
            )
        rules_passed.append(11)

    def _validate_rule_12(self, rules_passed: list[int]) -> None:
        rules_passed.append(12)

    def _validate_quotes(self, data: dict, errors: list[str], warnings: list[str]) -> None:
        quotes = data.get("Quotes", [])
        if len(quotes) < 3:
            errors.append(f"[QUOTES] Mínimo 3 quotes obrigatórias, encontradas: {len(quotes)}")
        elif len(quotes) > 8:
            warnings.append(f"[QUOTES] Máximo 8 quotes recomendadas, encontradas: {len(quotes)}")

        has_mechanism_quote = any(q.get("TipoQuote") == "Mecanismo" for q in quotes if isinstance(q, dict))
        if not has_mechanism_quote and quotes:
            warnings.append("[QUOTES] Recomendado: incluir pelo menos 1 quote de tipo 'Mecanismo'")

    def _validate_narratives(self, data: dict, warnings: list[str]) -> None:
        problema = data.get("ProblemaNegócio_Contexto", "")
        if problema:
            lines = len([l for l in problema.split("\n") if l.strip()])
            if lines < 3:
                warnings.append(f"[NARRATIVA] ProblemaNegócio_Contexto curto: {lines} linhas (mín. 3)")

    def validate_file(self, yaml_path: Path) -> ValidationResult:
        """Valida um arquivo YAML."""
        with open(yaml_path, "r", encoding="utf-8") as f:
            content = f.read()
        return self.validate(content)


def _should_use_dynamic_profile_validator() -> tuple[bool, Any, Any]:
    """Return whether a non-default project profile is active in runtime env."""
    if _profile_engine is None:
        return False, None, None

    try:
        project_root = _profile_engine.resolve_runtime_project_root()
    except (ImportError, ModuleNotFoundError, AttributeError, OSError):
        return False, None, None
    if project_root is None:
        return False, None, None

    try:
        ref = _profile_engine.get_active_profile_ref(project_root)
    except (ImportError, ModuleNotFoundError, AttributeError, OSError):
        return False, None, None
    if ref is None:
        return False, None, None

    profile_id = str(getattr(ref, "profile_id", "")).strip().lower()
    if profile_id in {"", "cimo_v3_3"}:
        return False, None, None
    return True, project_root, ref


def _validate_dict_with_dynamic_profile(data: dict, project_root: Path) -> ValidationResult:
    if _profile_engine is None:
        return ValidationResult(
            is_valid=False,
            errors=["[PROFILE] Dynamic profile engine unavailable."],
            warnings=[],
            rules_passed=[],
            rules_failed=[],
        )

    try:
        spec, _ref = _profile_engine.load_active_profile_spec(project_root)
        errors, warnings, rules_passed, rules_failed = _profile_engine.validate_dict_with_profile(
            data,
            spec,
        )
    except (ImportError, ModuleNotFoundError, AttributeError, OSError, ValueError) as exc:
        return ValidationResult(
            is_valid=False,
            errors=[f"[PROFILE] Dynamic profile validation failed: {exc}"],
            warnings=[],
            rules_passed=[],
            rules_failed=[],
        )

    return ValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        rules_passed=rules_passed,
        rules_failed=rules_failed,
    )


def _validate_yaml_with_project_profile(yaml_content: str) -> ValidationResult | None:
    enabled, project_root, _ref = _should_use_dynamic_profile_validator()
    if not enabled:
        return None

    validator = YAMLValidator()
    normalized = validator._normalize_yaml_text(yaml_content)

    try:
        docs = list(yaml.safe_load_all(normalized))
        data = docs[0] if docs else None
    except yaml.YAMLError as exc:
        return ValidationResult(
            is_valid=False,
            errors=[f"[PARSE] YAML inválido: {str(exc)[:200]}"],
            warnings=[],
            rules_passed=[],
            rules_failed=[],
        )
    if not isinstance(data, dict):
        return ValidationResult(
            is_valid=False,
            errors=["[PARSE] YAML deve ser um dicionário/mapeamento"],
            warnings=[],
            rules_passed=[],
            rules_failed=[],
        )
    return _validate_dict_with_dynamic_profile(data, Path(project_root))


def _validate_yaml_file_with_project_profile(yaml_path: Path) -> ValidationResult | None:
    enabled, _project_root, _ref = _should_use_dynamic_profile_validator()
    if not enabled:
        return None
    content = yaml_path.read_text(encoding="utf-8", errors="replace")
    return _validate_yaml_with_project_profile(content)


# ============================================================
# Funções Helper
# ============================================================

def validate_yaml(yaml_content: str) -> ValidationResult:
    """Função helper para validação rápida."""
    dynamic = _validate_yaml_with_project_profile(yaml_content)
    if dynamic is not None:
        return dynamic
    validator = YAMLValidator()
    return validator.validate(yaml_content)


def validate_yaml_file(yaml_path: Path) -> ValidationResult:
    """Função helper para validar arquivo."""
    dynamic = _validate_yaml_file_with_project_profile(yaml_path)
    if dynamic is not None:
        return dynamic
    validator = YAMLValidator()
    return validator.validate_file(yaml_path)


# ============================================================
# Teste
# ============================================================

if __name__ == "__main__":
    # Teste com YAML de exemplo
    test_yaml = """
ArtigoID: "ART_001"
Ano: 2024
TipoPublicação: "Journal"
Referência_Curta: "Silva et al., 2024"
DOI: "https://doi.org/10.1000/example"

SegmentoSetorial: "Operacao Primaria"
SegmentoSetorial_Confiança: "Alta"
Ambiente: "Offshore"
Complexidade: "Alta"
Complexidade_Justificativa: "F1=1 (offshore), F2=1 (>5 fornecedores), F3=1 (risco crítico)"
ProcessoSCM_Alvo: "Manutenção/MRO"
TipoRisco_SCRM: "Risco de ativos"
ObjetoCrítico: "ESP (bomba submersível)"

ProblemaNegócio_Contexto: |
  Falhas em ESPs representam alto custo operacional em campos offshore.
  A manutenção preventiva tradicional não consegue prever falhas com precisão.
  O contexto de operação remota dificulta intervenções de emergência.

ClasseIA: "ML supervisionado"
ClasseIA_Confiança: "Alta"
TarefaAnalítica: "Previsão"
FamíliaModelo: "Ensemble tree-based"
TipoDado: "Séries temporais"
Maturidade: "Piloto"
Maturidade_Confiança: "Média"

Intervenção_Descrição: |
  Sistema de ML que analisa dados de sensores de ESP para prever falhas.
  Utiliza Random Forest treinado com histórico de 2 anos de operação.

Dados_Descrição: |
  Dados de sensores IoT de 50 ESPs em operação.
  Período: 2022-2024. 1.2 milhões de registros.
  Features: temperatura, vibração, corrente, pressão.

CategoriaMecanismo: "Antecipação de risco"
Mecanismo_Fonte: "Misto"
Mecanismo_Declarado: "O modelo identifica padrões que precedem falhas."
Mecanismo_Inferido: "INFERIDO: O algoritmo aprende correlações entre variáveis de sensor e eventos de falha. INFERIDO: Isso permite alertar operadores antes da falha ocorrer."
Mecanismo_Estruturado: "Dados de sensores → Random Forest → Score de risco → Alerta de manutenção"

ResultadoTipo: "Quantitativo"
Resultados_Quant: "Acurácia: 92% (vs. baseline: 78%); Recall: 89% (baseline: NR)"
Resultados_Qual: "Redução significativa de paradas não programadas"
NívelEvidência: "Experimento com dados reais"
Limitações_Artigo: |
  Estudo limitado a um único campo de produção.
  Dados de apenas um fabricante de ESP.

Quotes:
  - QuoteID: Q001
    TipoQuote: "Mecanismo"
    Trecho: "The Random Forest model captures complex interactions between sensor variables that precede equipment failure"
    Página: "p.7"
  - QuoteID: Q002
    TipoQuote: "Contexto"
    Trecho: "ESP failures in offshore fields result in production losses exceeding $500k per event"
    Página: "p.2"
  - QuoteID: Q003
    TipoQuote: "Outcome"
    Trecho: "The proposed model achieved 92% accuracy in predicting failures within a 7-day window"
    Página: "p.12"
"""

    print("=== Teste do Validador ===\n")
    result = validate_yaml(test_yaml)
    print(result)


