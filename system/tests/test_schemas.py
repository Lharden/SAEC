"""Tests for SAEC Pydantic data models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

from schemas import (
    Quote,
    ExtractionSchema,
    validate_extraction_dict,
    TipoQuote,
    Confianca,
    Ambiente,
)


class TestQuoteModel:
    """Tests for the Quote Pydantic model."""

    def test_valid_quote_construction(self):
        """Test that a valid Quote can be constructed."""
        quote = Quote(
            QuoteID="Q001",
            TipoQuote="Mecanismo",
            Trecho="The model enables early detection of failures in offshore equipment.",
            Página="p.7",
        )
        assert quote.QuoteID == "Q001"
        assert quote.TipoQuote == "Mecanismo"
        assert (
            quote.Trecho == "The model enables early detection of failures in offshore equipment."
        )
        assert quote.Página == "p.7"

    def test_quote_id_format_validation(self):
        """Test that QuoteID must be in Q001, Q002 format."""
        with pytest.raises(PydanticValidationError) as exc_info:
            Quote(
                QuoteID="001",
                TipoQuote="Mecanismo",
                Trecho="Some text here",
                Página="p.1",
            )
        assert "Q001" in str(exc_info.value)

    def test_quote_id_invalid_format(self):
        """Test rejection of non-Q### formats."""
        with pytest.raises(PydanticValidationError):
            Quote(
                QuoteID="Q1",
                TipoQuote="Mecanismo",
                Trecho="Some text here",
                Página="p.1",
            )

    def test_trecho_min_length_validation(self):
        """Test that Trecho must be at least 10 characters."""
        with pytest.raises(PydanticValidationError) as exc_info:
            Quote(
                QuoteID="Q001",
                TipoQuote="Mecanismo",
                Trecho="short",
                Página="p.1",
            )
        # Pydantic v2 returns "string_too_short" error type
        assert "string_too_short" in str(exc_info.value).lower()

    def test_pagina_min_length_validation(self):
        """Test that Página must be at least 2 characters."""
        with pytest.raises(PydanticValidationError) as exc_info:
            Quote(
                QuoteID="Q001",
                TipoQuote="Mecanismo",
                Trecho="Some valid length text here",
                Página="p",
            )
        assert "localização" in str(exc_info.value).lower()

    def test_tipoquote_literal_validation(self):
        """Test that TipoQuote accepts valid literals."""
        valid_types = [
            "Contexto",
            "Intervenção",
            "Mecanismo",
            "Outcome",
            "Limitação",
            "Método",
            "Outro",
        ]
        for tipo in valid_types:
            quote = Quote(
                QuoteID="Q001",
                TipoQuote=tipo,
                Trecho="Some text that is long enough to pass validation",
                Página="p.1",
            )
            assert quote.TipoQuote == tipo


class TestExtractionSchemaModel:
    """Tests for the main ExtractionSchema Pydantic model."""

    def get_valid_extraction_data(self) -> dict:
        """Return a valid minimal extraction data dict."""
        return {
            "ArtigoID": "ART_001",
            "Ano": 2024,
            "TipoPublicação": "Journal",
            "Referência_Curta": "Silva et al., 2024",
            "SegmentoSetorial": "Operacao Primaria",
            "SegmentoSetorial_Confiança": "Alta",
            "Ambiente": "Offshore",
            "Complexidade": "Alta",
            "Complexidade_Justificativa": "F1=1 (offshore), F2=1 (>5 fornecedores), F3=1 (risco crítico)",
            "ProcessoSCM_Alvo": "Manutenção/MRO",
            "TipoRisco_SCRM": "Risco de ativos",
            "ObjetoCrítico": "ESP (bomba submersível)",
            "ProblemaNegócio_Contexto": "Descrição do problema de negócio com pelo menos 50 caracteres para validar.",
            "ClasseIA": "ML supervisionado",
            "ClasseIA_Confiança": "Alta",
            "TarefaAnalítica": "Previsão",
            "FamíliaModelo": "Ensemble tree-based",
            "TipoDado": "Séries temporais",
            "Maturidade": "Piloto",
            "Maturidade_Confiança": "Média",
            "Intervenção_Descrição": "Descrição da intervenção com detalhes suficientes.",
            "Dados_Descrição": "Descrição dos dados utilizados no estudo.",
            "CategoriaMecanismo": "Antecipação de risco",
            "Mecanismo_Fonte": "Misto",
            "Mecanismo_Declarado": "O modelo permite antecipar falhas.",
            "Mecanismo_Inferido": "INFERIDO: O modelo aprende padrões históricos.",
            "Mecanismo_Estruturado": "Dados de sensores → Random Forest → Probabilidade de falha → Manutenção preventiva",
            "ResultadoTipo": "Quantitativo",
            "Resultados_Quant": "Acurácia: 92% (vs. baseline: 78%)",
            "Resultados_Qual": "Redução de paradas não programadas",
            "NívelEvidência": "Experimento com dados reais",
            "Limitações_Artigo": "Estudo limitado a um campo específico.",
            "Quotes": [
                {
                    "QuoteID": "Q001",
                    "TipoQuote": "Mecanismo",
                    "Trecho": "The model enables early detection of failures...",
                    "Página": "p.7",
                },
                {
                    "QuoteID": "Q002",
                    "TipoQuote": "Contexto",
                    "Trecho": "ESP failures are a major concern in offshore...",
                    "Página": "p.2",
                },
                {
                    "QuoteID": "Q003",
                    "TipoQuote": "Outcome",
                    "Trecho": "Results show 92% accuracy in predicting...",
                    "Página": "p.12",
                },
            ],
        }

    def test_valid_extraction_schema(self):
        """Test that valid extraction data creates a valid schema."""
        data = self.get_valid_extraction_data()
        schema = ExtractionSchema(**data)
        assert schema.ArtigoID == "ART_001"
        assert schema.Ano == 2024
        assert len(schema.Quotes) == 3

    def test_artigo_id_format_validation(self):
        """Test ArtigoID must be in ART_001 format."""
        data = self.get_valid_extraction_data()
        data["ArtigoID"] = "001"
        with pytest.raises(PydanticValidationError) as exc_info:
            ExtractionSchema(**data)
        assert "ART_001" in str(exc_info.value)

    def test_ano_range_validation(self):
        """Test that Ano must be between 1990 and 2030."""
        data = self.get_valid_extraction_data()
        data["Ano"] = 1985
        with pytest.raises(PydanticValidationError):
            ExtractionSchema(**data)

    def test_ano_future_validation(self):
        """Test that Ano cannot be too far in the future."""
        data = self.get_valid_extraction_data()
        data["Ano"] = 2050
        with pytest.raises(PydanticValidationError):
            ExtractionSchema(**data)

    def test_quotes_min_length_validation(self):
        """Test that at least 3 quotes are required."""
        data = self.get_valid_extraction_data()
        data["Quotes"] = [
            {
                "QuoteID": "Q001",
                "TipoQuote": "Mecanismo",
                "Trecho": "Short text here",
                "Página": "p.1",
            },
        ]
        with pytest.raises(PydanticValidationError) as exc_info:
            ExtractionSchema(**data)
        assert "min_length" in str(exc_info.value).lower() or "3" in str(exc_info.value)

    def test_referencia_curta_min_length(self):
        """Test that Referência_Curta must be at least 5 characters."""
        data = self.get_valid_extraction_data()
        data["Referência_Curta"] = "AB"
        with pytest.raises(PydanticValidationError):
            ExtractionSchema(**data)

    def test_complexidade_justificativa_requires_f1_f2_f3(self):
        """Test Complexidade_Justificativa must contain F1, F2, F3."""
        data = self.get_valid_extraction_data()
        data["Complexidade_Justificativa"] = "Some justification without formulas"
        with pytest.raises(PydanticValidationError) as exc_info:
            ExtractionSchema(**data)
        error_msg = str(exc_info.value).lower()
        assert "f1" in error_msg and "f2" in error_msg

    def test_mecanismo_estruturado_requires_arrow(self):
        """Test Mecanismo_Estruturado must contain →."""
        data = self.get_valid_extraction_data()
        data["Mecanismo_Estruturado"] = "Input Output Result"
        with pytest.raises(PydanticValidationError) as exc_info:
            ExtractionSchema(**data)
        assert "→" in str(exc_info.value)

    def test_mecanismo_estruturado_no_newlines(self):
        """Test Mecanismo_Estruturado must be a single line."""
        data = self.get_valid_extraction_data()
        data["Mecanismo_Estruturado"] = "Input →\nOutput → Result"
        with pytest.raises(PydanticValidationError) as exc_info:
            ExtractionSchema(**data)
        assert "ÚNICA" in str(exc_info.value) or "line" in str(exc_info.value).lower()

    def test_model_validator_regra1_tipo_risco_requires_objeto_critico(self):
        """Test Regra 1: TipoRisco != NR requires ObjetoCrítico."""
        data = self.get_valid_extraction_data()
        data["TipoRisco_SCRM"] = "Risco de ativos"
        data["ObjetoCrítico"] = ""
        with pytest.raises(PydanticValidationError) as exc_info:
            ExtractionSchema(**data)
        assert "ObjetoCrítico" in str(exc_info.value)

    def test_model_validator_regra2_quant_requires_resultados_quant(self):
        """Test Regra 2: ResultadoTipo=Quantitativo requires Resultados_Quant."""
        data = self.get_valid_extraction_data()
        data["ResultadoTipo"] = "Quantitativo"
        data["Resultados_Quant"] = "NR"
        with pytest.raises(PydanticValidationError) as exc_info:
            ExtractionSchema(**data)
        assert "Resultados_Quant" in str(exc_info.value)

    def test_model_validator_regra3_producao_requires_evidencia(self):
        """Test Regra 3: Maturidade=Produção requires compatible NívelEvidência."""
        data = self.get_valid_extraction_data()
        data["Maturidade"] = "Produção"
        data["NívelEvidência"] = "Proposta teórica/framework"
        with pytest.raises(PydanticValidationError) as exc_info:
            ExtractionSchema(**data)
        assert "NívelEvidência" in str(exc_info.value)

    def test_model_validator_regra4_hibrido_requires_multiple_techniques(self):
        """Test Regra 4: ClasseIA=Híbrido requires multiple techniques in FamíliaModelo."""
        data = self.get_valid_extraction_data()
        data["ClasseIA"] = "Híbrido"
        data["FamíliaModelo"] = "Single technique"
        with pytest.raises(PydanticValidationError) as exc_info:
            ExtractionSchema(**data)
        assert (
            "múltiplas" in str(exc_info.value).lower() or "multiple" in str(exc_info.value).lower()
        )

    def test_model_validator_regra8_sintetica_no_producao(self):
        """Test Regra 8: Simulação sintética cannot have Maturidade=Produção."""
        data = self.get_valid_extraction_data()
        data["NívelEvidência"] = "Simulação com dados sintéticos"
        data["Maturidade"] = "Produção"
        with pytest.raises(PydanticValidationError) as exc_info:
            ExtractionSchema(**data)
        assert "Maturidade" in str(exc_info.value)

    def test_mecanismo_inferido_valid_format(self):
        """Test Mecanismo_Inferido accepts valid INFERIDO: format."""
        data = self.get_valid_extraction_data()
        data["Mecanismo_Inferido"] = "INFERIDO: First sentence. INFERIDO: Second sentence."
        schema = ExtractionSchema(**data)
        assert "INFERIDO" in schema.Mecanismo_Inferido


class TestValidateExtractionDict:
    """Tests for the validate_extraction_dict helper function."""

    def test_valid_dict_returns_true_empty_errors(self):
        """Test that valid dict returns (True, [])."""
        data = {
            "ArtigoID": "ART_001",
            "Ano": 2024,
            "TipoPublicação": "Journal",
            "Referência_Curta": "Silva et al., 2024",
            "SegmentoSetorial": "Operacao Primaria",
            "SegmentoSetorial_Confiança": "Alta",
            "Ambiente": "Offshore",
            "Complexidade": "Alta",
            "Complexidade_Justificativa": "F1=1, F2=1, F3=1",
            "ProcessoSCM_Alvo": "Test",
            "TipoRisco_SCRM": "NR",
            "ProblemaNegócio_Contexto": "A" * 50,
            "ClasseIA": "ML supervisionado",
            "ClasseIA_Confiança": "Alta",
            "TarefaAnalítica": "Previsão",
            "FamíliaModelo": "Test",
            "TipoDado": "Tabular/ERP",
            "Maturidade": "Conceito",
            "Maturidade_Confiança": "Alta",
            "Intervenção_Descrição": "A" * 30,
            "Dados_Descrição": "A" * 30,
            "CategoriaMecanismo": "Antecipação de risco",
            "Mecanismo_Fonte": "Declarado",
            "Mecanismo_Declarado": "Test",
            "Mecanismo_Estruturado": "A → B → C",
            "ResultadoTipo": "Qualitativo",
            "NívelEvidência": "Proposta teórica/framework",
            "Limitações_Artigo": "Test",
            "Quotes": [
                {"QuoteID": "Q001", "TipoQuote": "Mecanismo", "Trecho": "A" * 10, "Página": "p.1"},
                {"QuoteID": "Q002", "TipoQuote": "Contexto", "Trecho": "B" * 10, "Página": "p.2"},
                {"QuoteID": "Q003", "TipoQuote": "Outcome", "Trecho": "C" * 10, "Página": "p.3"},
            ],
        }
        is_valid, errors = validate_extraction_dict(data)
        assert is_valid is True
        assert errors == []

    def test_invalid_dict_returns_false_and_errors(self):
        """Test that invalid dict returns (False, [error_list])."""
        data = {
            "ArtigoID": "INVALID",  # Invalid format
            "Ano": 2024,
            # ... other required fields missing
        }
        is_valid, errors = validate_extraction_dict(data)
        assert is_valid is False
        assert len(errors) > 0
        assert any("ArtigoID" in err for err in errors)

    def test_empty_dict_returns_errors_for_required_fields(self):
        """Test that empty dict returns errors for required fields."""
        is_valid, errors = validate_extraction_dict({})
        assert is_valid is False
        assert len(errors) > 0
