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
from typing import Optional

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
    itens: list[ItemDocumentoFiscal]


def calcular_digito_verificador(chave_sem_dv: str) -> str:
    pesos = (4, 3, 2, 9, 8, 7, 6, 5)
    soma = 0
    for indice, digito in enumerate(reversed(chave_sem_dv)):
        soma += int(digito) * pesos[indice % len(pesos)]
    resto = soma % 11
    dv = 11 - resto
    if dv >= 10:
        dv = 0
    return str(dv)


def validar_chave(chave: str) -> str:
    chave_normalizada = re.sub(r"\D", "", (chave or "").strip())
    if not CHAVE_REGEX.fullmatch(chave_normalizada):
        raise ValueError("A chave deve conter exatamente 44 dígitos numéricos.")

    dv_esperado = calcular_digito_verificador(chave_normalizada[:-1])
    if chave_normalizada[-1] != dv_esperado:
        raise ValueError("A chave informada é inválida: dígito verificador inconsistente.")

    return chave_normalizada


def remover_namespaces(tree: ET.ElementTree) -> ET.ElementTree:
    for elem in tree.iter():
        if "}" in elem.tag:
            elem.tag = elem.tag.split("}", 1)[1]
    return tree


def to_decimal(valor: Optional[str], default: str = "0") -> Decimal:
    texto = (valor or "").strip().replace(",", ".")
    if not texto:
        texto = default
    try:
        return Decimal(texto)
    except InvalidOperation:
        return Decimal(default)


def gerar_ean_fallback(nome: str, codigo_interno: str) -> str:
    digest = hashlib.sha1(f"{codigo_interno}|{nome}".encode("utf-8")).hexdigest()[:12]
    return f"DFE_{digest.upper()}"


def decodificar_xml(raw_content: bytes, origem: str) -> str:
    ultimo_erro: Optional[UnicodeDecodeError] = None
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return raw_content.decode(encoding)
        except UnicodeDecodeError as exc:
            ultimo_erro = exc

    raise RuntimeError(f"Nao foi possivel decodificar o XML obtido de {origem}.") from ultimo_erro


def parse_xml(xml_content: str) -> ET.Element:
    try:
        tree = remover_namespaces(ET.ElementTree(ET.fromstring(xml_content.lstrip("\ufeff").strip())))
    except ET.ParseError as exc:
        raise ValueError(f"XML invalido ou corrompido: {exc}.") from exc
    return tree.getroot()


def extrair_chave_do_xml(root: ET.Element) -> Optional[str]:
    for tag, prefixo in (("infNFe", "NFe"), ("infCFe", "CFe")):
        info = root.find(f".//{tag}")
        if info is None:
            continue
        raw = (info.get("Id") or "").strip()
        if raw.startswith(prefixo) and CHAVE_REGEX.fullmatch(raw[len(prefixo) :]):
            return raw[len(prefixo) :]

    for caminho in (".//chNFe", ".//chave"):
        chave = (root.findtext(caminho) or "").strip()
        if CHAVE_REGEX.fullmatch(chave):
            return chave
    return None


def detectar_tipo_documento(root: ET.Element) -> str:
    modelo = (root.findtext(".//ide/mod") or "").strip()
    if root.find(".//infCFe") is not None:
        return "CFe-SAT"
    if modelo == "65":
        return "NFC-e"
    if modelo == "55":
        return "NF-e"
    if root.find(".//infNFe") is not None:
        return "NFC-e/NF-e"
    return "DF-e Consumidor"


def detectar_data_compra(root: ET.Element) -> str:
    candidatos = [
        (root.findtext(".//ide/dhEmi") or "").strip(),
        (root.findtext(".//ide/dEmi") or "").strip(),
        (root.findtext(".//emit/enderEmit/dhEmi") or "").strip(),
    ]
    for valor in candidatos:
        if not valor:
            continue
        if "T" in valor:
            try:
                return datetime.fromisoformat(valor.replace("Z", "+00:00")).date().isoformat()
            except ValueError:
                pass
        for fmt in ("%Y%m%d", "%Y-%m-%d"):
            try:
                return datetime.strptime(valor[:10], fmt).date().isoformat()
            except ValueError:
                continue

    raise ValueError("Nao foi possivel identificar a data de emissao no XML.")


def detectar_mercado(root: ET.Element) -> str:
    nome = (
        (root.findtext(".//emit/xFant") or "").strip()
        or (root.findtext(".//emit/xNome") or "").strip()
    )
    if not nome:
        raise ValueError("Nao foi possivel identificar o emitente no XML.")
    return nome


def parse_documento_por_chave(xml_content: str, chave_esperada: str) -> DocumentoFiscalConsumidor:
    root = parse_xml(xml_content)

    chave_xml = extrair_chave_do_xml(root)
    if chave_xml and chave_xml != chave_esperada:
        raise ValueError(f"Chave divergente: informada {chave_esperada}, XML contem {chave_xml}.")

    itens: list[ItemDocumentoFiscal] = []
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
        if vtot == 0 and qtd > 0 and vuni > 0:
            vtot = qtd * vuni
        if not nome:
            nome = f"PRODUTO_{codigo or ean}"

        itens.append(
            ItemDocumentoFiscal(
                ean=ean,
                codigo_interno=codigo,
                nome=nome,
                quantidade=qtd,
                preco_unitario=vuni,
                valor_total=vtot,
            )
        )

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
        return decodificar_xml(local_path.read_bytes(), str(local_path))

    url_template = os.getenv("SEFAZ_GO_XML_PROVIDER_URL_TEMPLATE", "").strip()
    if url_template:
        url = url_template.format(chave=chave)
        token = os.getenv("SEFAZ_GO_XML_PROVIDER_TOKEN", "").strip()
        req = urllib.request.Request(url)
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return decodificar_xml(resp.read(), url)
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"Falha HTTP ao buscar XML: status {exc.code}.") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Falha de conexao ao buscar XML: {exc.reason}.") from exc

    raise FileNotFoundError(
        f"XML nao encontrado para a chave {chave}. Salve o arquivo em {local_path} "
        "ou configure SEFAZ_GO_XML_PROVIDER_URL_TEMPLATE."
    )


def importar_documento_por_chave_goias(chave: str) -> dict:
    from ia_groq_utils import classificar_produto, produto_ja_existe, salvar_compra, salvar_produto

    chave = validar_chave(chave)
    xml_content = resolver_xml_por_chave_goias(chave)
    nota = parse_documento_por_chave(xml_content, chave)

    processados = 0
    novos = 0
    for item in nota.itens:
        try:
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

            salvar_compra(
                item.ean,
                nota.data_compra,
                nota.mercado,
                float(item.preco_unitario),
                float(item.quantidade),
            )
        except Exception as exc:
            raise RuntimeError(
                f"Falha ao persistir item '{item.nome}' (EAN {item.ean}): {exc}"
            ) from exc
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

    print("\nIMPORTADOR DE NFC-e/CF-e (SEFAZ GOIAS) POR CHAVE\n")
    criar_tabelas_se_nao_existirem()
    chave = input("Informe a chave (44 digitos): ").strip()

    try:
        resultado = importar_documento_por_chave_goias(chave)
    except Exception as exc:
        print(f"Erro na importacao: {exc}")
        return

    print("\nImportacao concluida com sucesso.")
    print(f"Tipo: {resultado['tipo_documento']}")
    print(f"Chave: {resultado['chave']}")
    print(f"Mercado: {resultado['mercado']}")
    print(f"Data da compra: {resultado['data_compra']}")
    print(f"Itens encontrados: {resultado['itens_encontrados']}")
    print(f"Itens processados: {resultado['itens_processados']}")
    print(f"Novos produtos: {resultado['novos_produtos']}")


if __name__ == "__main__":
    main()
