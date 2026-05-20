import os

import httpx
import pytest


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_EXTERNAL_TESTS") != "1",
    reason="External SEFAZ smoke test disabled by default",
)


@pytest.mark.asyncio
async def test_resumo():
    chave = "52260517457404001183655110000409351275118105"
    url = f"https://nfeweb.sefaz.go.gov.br/nfeweb/sites/nfce/resumoNFCe?p={chave}"

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(url)

    assert response.status_code == 200
