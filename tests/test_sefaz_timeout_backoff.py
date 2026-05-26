from __future__ import annotations

import httpx
import pytest

from backend.core.config import settings
from backend.services.importador_sefaz import ImportadorSefazService, SefazComunicacaoError


class FakeLogger:
    def __init__(self):
        self.messages: list[str] = []

    def warning(self, message: str) -> None:
        self.messages.append(message)

    def error(self, message: str) -> None:
        self.messages.append(message)


class FakeSefazClient:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    async def get(self, url: str, **kwargs):
        self.calls.append({"url": url, **kwargs})
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _service_with_client(client: FakeSefazClient) -> tuple[ImportadorSefazService, FakeLogger]:
    service = ImportadorSefazService.__new__(ImportadorSefazService)
    service._client = client
    service._log = FakeLogger()
    return service, service._log


def _response(status_code: int, url: str = "https://sefaz.test?p=1234") -> httpx.Response:
    request = httpx.Request("GET", url)
    return httpx.Response(status_code=status_code, request=request, text="erro")


@pytest.fixture(autouse=True)
def deterministic_sefaz_settings(monkeypatch):
    monkeypatch.setattr(settings, "sefaz_request_timeout_seconds", 7.0)
    monkeypatch.setattr(settings, "sefaz_max_retries", 3)
    monkeypatch.setattr(settings, "sefaz_backoff_base_seconds", 0.5)


@pytest.mark.anyio
async def test_fetch_url_sucesso_usa_timeout_e_user_agent():
    client = FakeSefazClient([_response(200)])
    service, _logger = _service_with_client(client)

    html = await service._fetch_url("https://sefaz.test?p=99999999999999999999999999999999999999999999")

    assert html == "erro"
    assert len(client.calls) == 1
    assert client.calls[0]["timeout"] == 7.0
    assert client.calls[0]["headers"]["User-Agent"] == ImportadorSefazService.USER_AGENT


@pytest.mark.anyio
async def test_fetch_url_timeout_retorna_erro_controlado_sem_chave_completa(monkeypatch):
    chave = "99999999999999999999999999999999999999999999"
    sleeps = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr("backend.services.importador_sefaz.asyncio.sleep", fake_sleep)
    request = httpx.Request("GET", f"https://sefaz.test?p={chave}")
    client = FakeSefazClient(
        [
            httpx.TimeoutException(f"timeout em https://sefaz.test?p={chave}", request=request),
            httpx.TimeoutException(f"timeout em https://sefaz.test?p={chave}", request=request),
            httpx.TimeoutException(f"timeout em https://sefaz.test?p={chave}", request=request),
        ]
    )
    service, logger = _service_with_client(client)

    with pytest.raises(SefazComunicacaoError) as exc:
        await service._fetch_url(f"https://sefaz.test?p={chave}")

    assert str(exc.value) == "Falha ao consultar SEFAZ (timeout)."
    assert chave not in str(exc.value)
    assert len(client.calls) == 3
    assert sleeps == [0.5, 1.0]
    assert all(chave not in message for message in logger.messages)
    assert any("<chave-redigida>" in message for message in logger.messages)


@pytest.mark.anyio
async def test_fetch_url_503_retorna_ate_limite_e_sucesso(monkeypatch):
    sleeps = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr("backend.services.importador_sefaz.asyncio.sleep", fake_sleep)
    client = FakeSefazClient([_response(503), _response(503), _response(200)])
    service, _logger = _service_with_client(client)

    html = await service._fetch_url("https://sefaz.test?p=99999999999999999999999999999999999999999999")

    assert html == "erro"
    assert len(client.calls) == 3
    assert sleeps == [0.5, 1.0]


@pytest.mark.anyio
@pytest.mark.parametrize("status_code", [502, 503, 504, 429])
async def test_fetch_url_status_retryable_esgota_limite(status_code: int, monkeypatch):
    sleeps = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr("backend.services.importador_sefaz.asyncio.sleep", fake_sleep)
    client = FakeSefazClient([_response(status_code), _response(status_code), _response(status_code)])
    service, _logger = _service_with_client(client)

    with pytest.raises(SefazComunicacaoError) as exc:
        await service._fetch_url("https://sefaz.test?p=99999999999999999999999999999999999999999999")

    assert str(exc.value) == "Falha ao consultar SEFAZ (tentativas esgotadas)."
    assert len(client.calls) == 3
    assert sleeps == [0.5, 1.0]


@pytest.mark.anyio
async def test_fetch_url_404_nao_faz_retry(monkeypatch):
    sleeps = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr("backend.services.importador_sefaz.asyncio.sleep", fake_sleep)
    client = FakeSefazClient([_response(404)])
    service, _logger = _service_with_client(client)

    with pytest.raises(SefazComunicacaoError) as exc:
        await service._fetch_url("https://sefaz.test?p=99999999999999999999999999999999999999999999")

    assert str(exc.value) == "Falha ao consultar SEFAZ."
    assert len(client.calls) == 1
    assert sleeps == []
