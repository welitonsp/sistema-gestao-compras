import pytest
from pydantic import ValidationError
from backend.schemas.agent import (
    AgentQueryRequest,
    AgentQueryResponse,
    AgentAuditMetadata,
    AgentIntent,
    AgentStatus,
    AgentRecommendationType,
    AgentResponseMetadata,
    AgentRecommendation
)

def test_request_accepts_valid_message():
    req = AgentQueryRequest(message="Qual o gasto total?")
    assert req.message == "Qual o gasto total?"

def test_request_rejects_empty_message():
    with pytest.raises(ValidationError):
        AgentQueryRequest(message="")
    with pytest.raises(ValidationError):
        AgentQueryRequest(message="   ")

def test_request_rejects_long_message():
    with pytest.raises(ValidationError):
        AgentQueryRequest(message="a" * 501)

def test_request_forbids_extra_fields():
    with pytest.raises(ValidationError):
        AgentQueryRequest(message="Ok", extra_field="not allowed")

def test_response_forbids_extra_fields():
    with pytest.raises(ValidationError):
        AgentQueryResponse(
            answer="Sim",
            intent=AgentIntent.PRICE_ANALYSIS,
            status=AgentStatus.SUCCESS,
            metadata=AgentResponseMetadata(),
            unknown_field="not allowed"
        )

def test_response_metadata_no_query_hash():
    # Garantir que o schema de metadata público não tem query_hash e proíbe extras
    metadata = AgentResponseMetadata(row_count=10, execution_time_ms=100.0)
    assert not hasattr(metadata, "query_hash")

    with pytest.raises(ValidationError):
         AgentResponseMetadata(row_count=10, query_hash="abc")

def test_audit_metadata_query_hash_validation():
    valid_hash = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    audit = AgentAuditMetadata(
        intent=AgentIntent.PRICE_ANALYSIS,
        status=AgentStatus.SUCCESS,
        query_hash=valid_hash
    )
    assert audit.query_hash == valid_hash

    # Rejeita tamanho inválido
    with pytest.raises(ValidationError):
        AgentAuditMetadata(
            intent=AgentIntent.PRICE_ANALYSIS,
            status=AgentStatus.SUCCESS,
            query_hash="abc123"
        )

    # Rejeita caracteres não hexadecimais
    with pytest.raises(ValidationError):
        AgentAuditMetadata(
            intent=AgentIntent.PRICE_ANALYSIS,
            status=AgentStatus.SUCCESS,
            query_hash="z" * 64
        )

def test_recommendations_default_factory():
    res = AgentQueryResponse(
        answer="Ok",
        intent=AgentIntent.PRICE_ANALYSIS,
        status=AgentStatus.SUCCESS,
        metadata=AgentResponseMetadata()
    )
    assert res.recommendations == []
    # Testar se é uma lista nova (factory)
    res2 = AgentQueryResponse(
        answer="Ok2",
        intent=AgentIntent.PRICE_ANALYSIS,
        status=AgentStatus.SUCCESS,
        metadata=AgentResponseMetadata()
    )
    assert res.recommendations is not res2.recommendations

def test_impact_value_cents_validation():
    # Aceita inteiro positivo ou zero
    rec = AgentRecommendation(
        type=AgentRecommendationType.SAVINGS_OPPORTUNITY,
        title="Economia",
        description="Desc",
        impact_value_cents=100
    )
    assert rec.impact_value_cents == 100

    rec2 = AgentRecommendation(
        type=AgentRecommendationType.SAVINGS_OPPORTUNITY,
        title="Economia",
        description="Desc",
        impact_value_cents=0
    )
    assert rec2.impact_value_cents == 0

    # Rejeita negativo
    with pytest.raises(ValidationError):
        AgentRecommendation(
            type=AgentRecommendationType.SAVINGS_OPPORTUNITY,
            title="Economia",
            description="Desc",
            impact_value_cents=-1
        )

def test_unsupported_intent():
    req_data = {
        "answer": "Não entendi",
        "intent": "UNSUPPORTED",
        "status": "blocked",
        "metadata": {}
    }
    res = AgentQueryResponse(**req_data)
    assert res.intent == AgentIntent.UNSUPPORTED

def test_schema_no_sensitive_fields():
    schemas_to_check = [AgentQueryRequest, AgentQueryResponse, AgentAuditMetadata, AgentResponseMetadata]
    forbidden_fields = {
        "cpf", "cnpj", "chave_acesso", "qr_code", "url_sefaz", "xml",
        "json_bruto", "payload_fiscal", "raw_payload"
    }

    for schema in schemas_to_check:
        fields = schema.model_fields.keys()
        for forbidden in forbidden_fields:
            assert forbidden not in fields, f"Campo proibido '{forbidden}' encontrado em {schema.__name__}"
