from __future__ import annotations

import hashlib
import os
import re
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import List, Optional

CHAVE_REGEX = re.compile(r"^\d{44}$")
INVALID_GTIN = {"", "SEM GTIN", "SEMGTIN", "0", "0000000000000"}

@dataclass(slots=True)
class ItemDocumentoFiscal:
    ean: str
    codigo_interno: str
    nome: str
    quantidade: Decimal
    preco_unitario: Decimal
    valor_total: Decimal

@dataclass(slots=True)
class DocumentoFiscalConsumidor:
    chave: str
    tipo_documento: str
    data_compra: str
    mercado: str
    itens: List[ItemDocumentoFiscal]

def validar_chave(chave: str) -> str:
    chave = (chave or "").strip()
    if not CHAVE_REGEX.fullmatch(chave):
        raise ValueError("A chave deve conter exatamente 44 dígitos numéricos.")
    return chave

def remover_namespaces(tree: ET.ElementTree) -> ET.ElementTree:
    for elem in tree.iter():
        if "}" in elem.tag:
            elem.tag = elem.tag.split("}", 1)[1]
    return tree

def to_decimal(valor: Optional[str], default: str = "0") -> Decimal:
    texto = (valor or default).strip().replace(",", ".")
    if not texto:
        texto = default
    try:
        return Decimal(texto)
    except InvalidOperation:
        return Decimal(default)

def gerar_ean_fallback(nome: str, codigo_interno: str) -> str:
    digest = hashlib.sha1(f"{codigo_interno}|{nome}".encode("utf-8")).hexdigest()[:12]
    return f"DFE_{digest.upper()}"

def extrair_chave_do_xml(root: ET.Element) -> Optional[str]:
    inf_nfe = root.find(".//infNFe")
    if inf_nfe is not None and inf_nfe.get("Id"):
        raw = inf_nfe.get("Id", "")
        if raw.startswith("NFe") and CHAVE_REGEX.fullmatch(raw[3:]):
            return raw[3:]

    inf_cfe = root.find(".//infCFe")
    if inf_cfe is not None and inf_cfe.get("Id"):
        raw = inf_cfe.get("Id", "")
        if raw.startswith("CFe") and CHAVE_REGEX.fullmatch(raw[3:]):
            return raw[3:]

    ch = (root.findtext(".//chNFe") or "").strip()
    if CHAVE_REGEX.fullmatch(ch):
        return ch
    return None

def detectar_tipo_documento(root: ET.Element) -> str:
    if root.find(".//infNFe") is not None:
        return "NFCe/NFe"
    if root.find(".//infCFe") is not None:
        return "CFe-SAT"
    return "DF-e Consumidor"

def detectar_data_compra(root: ET.Element) -> str:
    d_emi = (root.findtext(".//ide/dEmi") or "").strip()
    if d_emi:
        for fmt in ("%Y%m%d", "%Y-%m-%d"):
            try:
                return datetime.strptime(d_emi, fmt).date().isoformat()
            except ValueError:
                pass

    dh_emi = (root.findtext(".//ide/dhEmi") or "").strip()
    if dh_emi:
        prefixo = dh_emi[:19].replace("T", " ")
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(prefixo, fmt).date().isoformat()
            except ValueError:
                pass

    return datetime.now().date().isoformat()

def detectar_mercado(root: ET.Element) -> str:
    return (
        (root.findtext(".//emit/xFant") or "").strip()
        or (root.findtext(".//emit/xNome") or "").strip()
        or "ESTABELECIMENTO_NAO_IDENTIFICADO"
    )

def parse_documento_por_chave(xml_content: str, chave_esperada: str) -> DocumentoFiscalConsumidor:
    tree = remover_namespaces(ET.ElementTree(ET.fromstring(xml_content)))
    root = tree.getroot()

    chave_xml = extrair_chave_do_xml(root)
    if chave_xml and chave_xml != chave_esperada:
        raise ValueError(f"Chave divergente: informada {chave_esperada}, XML contém {chave_xml}.")

    itens: List[ItemDocumentoFiscal] = []
    for det in root.findall(".//det"):
        prod = det.find("prod")
        if prod is None:
            continue

        nome = (prod.findtext("xProd") or "").strip()
        codigo = (prod.findtext("cProd") or "").strip()
        ean = (prod.findtext("cEAN") or "").strip()

        if ean.upper() in INVALID_GTIN:
            ean = (prod.findtext("cEANTrib") or "").strip()
        if ean.upper() in INVALID_GTIN:
            ean = codigo or gerar_ean_fallback(nome, codigo)

        qtd = to_decimal(prod.findtext("qCom"), "1")
        vuni = to_decimal(prod.findtext("vUnCom"), "0")
        vtot = to_decimal(prod.findtext("vProd"), "0")
        if not nome:
            nome = f"PRODUTO_{codigo or ean}"

        itens.append(ItemDocumentoFiscal(ean, codigo, nome, qtd, vuni, vtot))

    if not itens:
        raise ValueError("Nenhum item <det>/<prod> encontrado no XML informado.")

    return DocumentoFiscalConsumidor(
        chave=chave_esperada,
        tipo_documento=detectar_tipo_documento(root),
        data_compra=detectar_data_compra(root),
        mercado=detectar_mercado(root),
        itens=itens,
    )

def resolver_xml_por_chave_goias(chave: str) -> str:
    cache_dir = Path(os.getenv("GOIAS_XML_DOWNLOAD_DIR", "XML_DFE_GO"))
    local_path = cache_dir / f"{chave}.xml"
    if local_path.exists():
        return local_path.read_text(encoding="utf-8")

    url_template = os.getenv("SEFAZ_GO_XML_PROVIDER_URL_TEMPLATE", "").strip()
    if url_template:
        url = url_template.format(chave=chave)
        token = os.getenv("SEFAZ_GO_XML_PROVIDER_TOKEN", "").strip()
        req = urllib.request.Request(url)
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"Falha HTTP ao buscar XML: {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Falha de conexão ao buscar XML: {exc.reason}") from exc

    raise FileNotFoundError(
        f"XML não encontrado para a chave. Salve em {local_path} ou configure SEFAZ_GO_XML_PROVIDER_URL_TEMPLATE."
    )

def importar_documento_por_chave_goias(chave: str) -> dict:
    from ia_groq_utils import classificar_produto, produto_ja_existe, salvar_compra, salvar_produto

    chave = validar_chave(chave)
    xml_content = resolver_xml_por_chave_goias(chave)
    nota = parse_documento_por_chave(xml_content, chave)

    processados = 0
    novos = 0
    for item in nota.itens:
        if not produto_ja_existe(item.ean):
            dados = classificar_produto(item.nome)
            salvar_produto(
                item.ean,
                item.nome,
                dados.get("produto", item.nome),
                dados.get("marca", ""),
                dados.get("categoria", "Outros"),
                dados.get("unidade", "un"),
            )
            novos += 1

        salvar_compra(item.ean, nota.data_compra, nota.mercado, float(item.preco_unitario), float(item.quantidade))
        processados += 1

    return {
        "chave": nota.chave,
        "tipo_documento": nota.tipo_documento,
        "mercado": nota.mercado,
        "data_compra": nota.data_compra,
        "itens_encontrados": len(nota.itens),
        "itens_processados": processados,
        "novos_produtos": novos,
    }

def main() -> None:
    from ia_groq_utils import criar_tabelas_se_nao_existirem

    print("\n📥 IMPORTADOR DE NFC-e/CF-e (SEFAZ GOIÁS) POR CHAVE\n")
    criar_tabelas_se_nao_existirem()
    chave = input("Informe a chave (44 dígitos): ").strip()

    try:
        r = importar_documento_por_chave_goias(chave)
    except Exception as e:
        print(f"❌ Erro na importação: {e}")
        return

    print("\n✅ Importação concluída!")
    print(f"   Tipo: {r['tipo_documento']}")
    print(f"   Chave: {r['chave']}")
    print(f"   Mercado: {r['mercado']}")
    print(f"   Data compra: {r['data_compra']}")
    print(f"   Itens encontrados: {r['itens_encontrados']}")
    print(f"   Itens processados: {r['itens_processados']}")
    print(f"   Novos produtos: {r['novos_produtos']}")

if __name__ == "__main__":
    main()
