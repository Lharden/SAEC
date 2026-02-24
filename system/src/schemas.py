"""Schemas Pydantic para validação de YAML extraído."""

from typing import Literal, Optional, Any
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict
import re


# ============================================================
# Tipos Literais (Enums do Codebook)
# ============================================================

SegmentoDominio = Literal[
    "Operacao Primaria", "Operacao de Movimentacao", "Operacao de Processamento", "Transversal", "NR"
]

Ambiente = Literal["Offshore", "Onshore", "Híbrido", "NR"]

Complexidade = Literal["Alta", "Média", "Baixa", "NR"]

Confianca = Literal["Alta", "Média", "Baixa"]

TipoPublicacao = Literal[
    "Journal", "Conference", "Relatório técnico", "Tese/Dissertação", "Outro", "NR"
]

ClasseIA = Literal[
    "ML supervisionado", "ML não supervisionado", "Deep Learning", "NLP",
    "Visão computacional", "Otimização/heurísticas", "Probabilístico/Bayesiano",
    "Sistemas especialistas/regras", "Digital Twin com IA", "Híbrido", "Outro", "NR"
]

TarefaAnalitica = Literal[
    "Previsão", "Classificação", "Regressão", "Detecção de anomalia",
    "Clustering", "Extração de informação (NLP)", "Recomendação",
    "Otimização", "Simulação/what-if", "Automação (RPA+IA)", "Outro", "NR"
]

Maturidade = Literal["Conceito", "Protótipo", "Piloto", "Produção", "NR"]

TipoDado = Literal["Tabular/ERP", "Séries temporais", "Texto", "Imagem/Vídeo", "Multimodal", "NR"]

MecanismoFonte = Literal["Declarado", "Inferido", "Misto"]

ResultadoTipo = Literal["Quantitativo", "Qualitativo", "Misto", "NR"]

NivelEvidencia = Literal[
    "Estudo de caso real", "Experimento com dados reais", "Simulação com dados reais",
    "Simulação com dados sintéticos", "Survey/entrevistas", "Proposta teórica/framework",
    "Revisão conceitual", "NR"
]

CategoriaMecanismo = Literal[
    "Antecipação de risco", "Detecção precoce/anomalias", "Redução de incerteza",
    "Priorização/alocação ótima", "Integração de dados dispersos", "Padronização/consistência",
    "Otimização de trade-offs", "Automação informacional (NLP)", "Outro", "NR"
]

TipoQuote = Literal["Contexto", "Intervenção", "Mecanismo", "Outcome", "Limitação", "Método", "Outro"]


# ============================================================
# Schema de Quote
# ============================================================

class Quote(BaseModel):
    """Schema para uma quote."""

    QuoteID: str = Field(..., description="ID da quote no formato Q001, Q002, etc.")
    TipoQuote: TipoQuote
    Trecho: str = Field(..., min_length=10, description="Texto literal da quote")
    Página: str = Field(..., alias="Página", description="Página/seção de origem")

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("QuoteID")
    @classmethod
    def validate_quote_id(cls, v: str) -> str:
        if not re.match(r"^Q\d{3}$", v):
            raise ValueError(f"QuoteID deve ser no formato Q001, Q002, etc. Recebido: {v}")
        return v

    @field_validator("Página")
    @classmethod
    def validate_pagina(cls, v: str) -> str:
        # Aceita formatos como: p.7, p.12-13, Section 4.2, p.7 Section 4.2
        if not v or len(v.strip()) < 2:
            raise ValueError("Página deve indicar localização (ex: p.7, Section 4.2)")
        return v


# ============================================================
# Schema Principal de Extração
# ============================================================

class ExtractionSchema(BaseModel):
    """Schema completo para extração CIMO."""

    # -------------------- METADATA --------------------
    ArtigoID: str = Field(..., description="ID do artigo no formato ART_001")
    Ano: int = Field(..., ge=1990, le=2030)
    TipoPublicação: TipoPublicacao
    Referência_Curta: str = Field(..., min_length=5)
    DOI: Optional[str] = None

    # -------------------- CONTEXTO (C) --------------------
    SegmentoDominio: Any = Field(..., alias="SegmentoSetorial")
    SegmentoDominio_Confiança: Confianca = Field(..., alias="SegmentoSetorial_Confiança")
    Ambiente: Ambiente
    Complexidade: Complexidade
    Complexidade_Justificativa: str
    ProcessoSCM_Alvo: str
    TipoRisco_SCRM: str
    ObjetoCrítico: Optional[str] = None

    # -------------------- NARRATIVAS --------------------
    ProblemaNegócio_Contexto: str = Field(..., min_length=50)

    # -------------------- INTERVENÇÃO (I) --------------------
    ClasseIA: ClasseIA
    ClasseIA_Confiança: Confianca
    TarefaAnalítica: TarefaAnalitica
    FamíliaModelo: str
    TipoDado: TipoDado
    Maturidade: Maturidade
    Maturidade_Confiança: Confianca
    Intervenção_Descrição: str = Field(..., min_length=30)
    Dados_Descrição: str = Field(..., min_length=30)

    # -------------------- MECANISMO (M) --------------------
    CategoriaMecanismo: CategoriaMecanismo
    Mecanismo_Fonte: MecanismoFonte
    Mecanismo_Declarado: str
    Mecanismo_Inferido: Optional[str] = None
    Mecanismo_Estruturado: str

    # -------------------- OUTCOME (O) --------------------
    ResultadoTipo: ResultadoTipo
    Resultados_Quant: Optional[str] = None
    Resultados_Qual: Optional[str] = None
    NívelEvidência: NivelEvidencia
    Limitações_Artigo: str

    # -------------------- OPCIONAL --------------------
    Observação: Optional[str] = None

    # -------------------- QUOTES --------------------
    Quotes: list[Quote] = Field(..., min_length=3, max_length=8)

    model_config = ConfigDict(populate_by_name=True)

    # -------------------- VALIDADORES DE CAMPO --------------------

    @field_validator("ArtigoID")
    @classmethod
    def validate_artigo_id(cls, v: str) -> str:
        """Regra 7: ArtigoID deve ser no formato ART_001."""
        if not re.match(r"^ART_\d{3}$", v):
            raise ValueError(f"ArtigoID deve ser no formato ART_001. Recebido: {v}")
        return v

    @field_validator("Complexidade_Justificativa")
    @classmethod
    def validate_complexidade_justificativa(cls, v: str) -> str:
        """Regra 9: Deve ter F1/F2/F3."""
        if not v or v == "NR":
            raise ValueError("Complexidade_Justificativa é obrigatório e deve conter F1, F2, F3")

        has_f1 = bool(re.search(r"F1\s*=", v, re.IGNORECASE))
        has_f2 = bool(re.search(r"F2\s*=", v, re.IGNORECASE))
        has_f3 = bool(re.search(r"F3\s*=", v, re.IGNORECASE))

        if not (has_f1 and has_f2 and has_f3):
            missing = []
            if not has_f1:
                missing.append("F1")
            if not has_f2:
                missing.append("F2")
            if not has_f3:
                missing.append("F3")
            raise ValueError(
                f"Complexidade_Justificativa deve conter {', '.join(missing)}"
            )

        return v

    @field_validator("Mecanismo_Estruturado")
    @classmethod
    def validate_mecanismo_estruturado(cls, v: str) -> str:
        """Regra 6: Deve ser string única com →."""
        if not v or v == "NR":
            raise ValueError("Mecanismo_Estruturado é obrigatório")

        # Verificar se é multilinha
        if "\n" in v.strip():
            raise ValueError("Mecanismo_Estruturado deve ser string ÚNICA (sem quebras de linha)")

        # Verificar se tem o formato de seta
        if "→" not in v:
            raise ValueError("Mecanismo_Estruturado deve conter '→' (Entrada → Transformação → Mediação → Resultado)")

        return v

    @field_validator("Mecanismo_Inferido")
    @classmethod
    def validate_mecanismo_inferido(cls, v: Optional[str]) -> Optional[str]:
        """Regra 5: Cada sentença deve iniciar com INFERIDO:"""
        if not v or v.strip() == "NR" or v.strip() == "":
            return v

        # Separar sentenças (por ponto ou ponto-e-vírgula)
        # Ignorar pontos em abreviações comuns
        text = v.strip()
        sentences = re.split(r'(?<=[.;])\s+(?=INFERIDO:|[A-Z])', text)

        for sentence in sentences:
            sentence = sentence.strip()
            if sentence and not sentence.upper().startswith("INFERIDO:"):
                # Verificar se é continuação de sentença anterior
                if len(sentence) > 20:  # Provavelmente é uma sentença nova
                    raise ValueError(
                        f"Cada sentença de Mecanismo_Inferido deve iniciar com 'INFERIDO:'. "
                        f"Encontrado: '{sentence[:60]}...'"
                    )

        return v

    # -------------------- VALIDADOR DE MODELO (CROSS-FIELD) --------------------

    @model_validator(mode="after")
    def validate_cross_field_rules(self):
        """Validações que envolvem múltiplos campos."""

        # Regra 1: TipoRisco ≠ NR → ObjetoCrítico preenchido
        if self.TipoRisco_SCRM and self.TipoRisco_SCRM != "NR":
            if not self.ObjetoCrítico or self.ObjetoCrítico.strip() == "":
                raise ValueError(
                    f"Regra 1: Se TipoRisco_SCRM='{self.TipoRisco_SCRM}' (≠ NR), "
                    f"ObjetoCrítico DEVE estar preenchido"
                )

        # Regra 2: ResultadoTipo = Quantitativo → Resultados_Quant com formato correto
        if self.ResultadoTipo in ["Quantitativo", "Misto"]:
            if not self.Resultados_Quant or self.Resultados_Quant.strip() in ["", "NR"]:
                raise ValueError(
                    f"Regra 2: Se ResultadoTipo='{self.ResultadoTipo}', "
                    f"Resultados_Quant deve estar preenchido com métricas"
                )

        # Regra 3: Maturidade = Produção → NívelEvidência compatível
        if self.Maturidade == "Produção":
            valid_evidences = ["Estudo de caso real", "Experimento com dados reais"]
            if self.NívelEvidência not in valid_evidences:
                raise ValueError(
                    f"Regra 3: Se Maturidade='Produção', NívelEvidência deve ser "
                    f"'Estudo de caso real' ou 'Experimento com dados reais'. "
                    f"Atual: '{self.NívelEvidência}'"
                )

        # Regra 4: ClasseIA = Híbrido → técnicas especificadas
        if self.ClasseIA == "Híbrido":
            has_multiple_in_familia = ";" in self.FamíliaModelo or "+" in self.FamíliaModelo
            if not has_multiple_in_familia:
                raise ValueError(
                    f"Regra 4: Se ClasseIA='Híbrido', FamíliaModelo deve listar "
                    f"múltiplas técnicas separadas por ';' ou '+'"
                )

        # Regra 8: Simulação sintética → Maturidade não pode ser Produção/Piloto
        if self.NívelEvidência == "Simulação com dados sintéticos":
            if self.Maturidade in ["Produção", "Piloto"]:
                raise ValueError(
                    f"Regra 8: Se NívelEvidência='Simulação com dados sintéticos', "
                    f"Maturidade não pode ser '{self.Maturidade}' (deve ser Conceito ou Protótipo)"
                )

        return self


# ============================================================
# Funções Helper
# ============================================================

def validate_extraction_dict(data: dict) -> tuple[bool, list[str]]:
    """
    Valida um dicionário de extração contra o schema.

    Returns:
        (is_valid, list of error messages)
    """
    try:
        ExtractionSchema(**data)
        return True, []
    except Exception as e:
        errors: list[str] = []
        err_fn = getattr(e, "errors", None)
        if callable(err_fn):
            err_list = err_fn()
            if isinstance(err_list, list):
                for error in err_list:
                    if not isinstance(error, dict):
                        continue
                    field = ".".join(str(loc) for loc in error.get("loc", []))
                    errors.append(f"{field}: {error.get('msg', '')}")
        else:
            errors.append(str(e))
        return False, errors


# ============================================================
# Teste
# ============================================================

if __name__ == "__main__":
    # Teste básico
    test_data = {
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
        "Mecanismo_Inferido": "INFERIDO: O modelo aprende padrões históricos. INFERIDO: Isso permite antecipar falhas.",
        "Mecanismo_Estruturado": "Dados de sensores → Random Forest → Probabilidade de falha → Manutenção preventiva",
        "ResultadoTipo": "Quantitativo",
        "Resultados_Quant": "Acurácia: 92% (vs. baseline: 78%)",
        "Resultados_Qual": "Redução de paradas não programadas",
        "NívelEvidência": "Experimento com dados reais",
        "Limitações_Artigo": "Estudo limitado a um campo específico.",
        "Quotes": [
            {"QuoteID": "Q001", "TipoQuote": "Mecanismo", "Trecho": "The model enables early detection of failures...", "Página": "p.7"},
            {"QuoteID": "Q002", "TipoQuote": "Contexto", "Trecho": "ESP failures are a major concern in offshore...", "Página": "p.2"},
            {"QuoteID": "Q003", "TipoQuote": "Outcome", "Trecho": "Results show 92% accuracy in predicting...", "Página": "p.12"},
        ]
    }

    is_valid, errors = validate_extraction_dict(test_data)
    print(f"Válido: {is_valid}")
    if errors:
        print("Erros:")
        for e in errors:
            print(f"  - {e}")
    else:
        print("Todos os campos validados com sucesso!")


