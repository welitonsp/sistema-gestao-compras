"""Deterministic parser for SEFAZ GO NFC-e HTML."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import datetime
from decimal import Decimal
from typing import Optional

from bs4 import BeautifulSoup

from backend.schemas.internal import NotaFiscalDTO, ItemNotaDTO, FornecedorDTO
from core.logger import get_logger

logger = get_logger("services.parsers.sefaz_go")

class SefazGoParser:
    """Parses SEFAZ GO NFC-e HTML using CSS selectors."""

    def parse(self, html_content: str) -> Optional[NotaFiscalDTO]:
        """Extracts data from the SEFAZ GO HTML (NFC-e or NF-e)."""
        try:
            soup = BeautifulSoup(html_content, "html.parser")
            
            # Detecta o tipo de página: Consulta de Cupom (NFC-e) ou Consulta Completa (NF-e/Geral)
            is_full_consultation = "consulta-completa" in html_content or soup.find("div", id="aba_produto_1")
            
            # 1. Chave de Acesso
            chave = self._extract_chave(soup)
            if not chave:
                # Tenta extrair de campos de formulário se for post-search
                chave_input = soup.find("input", id="chaveAcesso")
                chave = re.sub(r"\D", "", chave_input.get("value", "")) if chave_input else ""
                
            if not chave:
                logger.warning("Não foi possível extrair a chave de acesso via seletor.")
                return None

            # 2. Dados do Fornecedor
            fornecedor = self._extract_fornecedor(soup)
            
            # 3. Itens
            itens = self._extract_itens(soup) if not is_full_consultation else self._extract_itens_full(soup)
            
            if not itens:
                logger.warning("Nenhum item encontrado via seletores determinísticos.")
                return None

            # 4. Totais e Data
            data_emissao = self._extract_data_emissao(soup)
            valor_total = self._extract_valor_total(soup)

            return NotaFiscalDTO(
                chave_acesso=chave,
                numero_nota=self._extract_numero_nota(soup),
                data_emissao=data_emissao.date(),
                valor_total=valor_total,
                fornecedor=fornecedor,
                itens=itens
            )

        except Exception as e:
            logger.error(f"Erro ao parsear HTML da SEFAZ GO: {e}", exc_info=True)
            return None

    def _extract_itens_full(self, soup: BeautifulSoup) -> list[ItemNotaDTO]:
        """Extração para o layout de Consulta Completa (NF-e)."""
        itens = []
        # No layout completo, os itens costumam estar em tabelas dentro de abas ou divs específicos
        # Procuramos pela tabela de produtos (comumente id='tabResult' ou dentro de div#aba_produto_1)
        table = soup.find("table", id="tabResult") or soup.select_one("div#aba_produto_1 table")
        
        if not table:
            # Tenta encontrar qualquer tabela que tenha cabeçalho de 'Código' ou 'Descrição'
            for t in soup.find_all("table"):
                header_text = t.get_text().lower()
                if "descrição" in header_text and "valor" in header_text:
                    table = t
                    break
        
        if not table: return []

        rows = table.find_all("tr")[1:] # Pula cabeçalho
        for row in rows:
            cols = row.find_all(["td", "span"])
            if len(cols) < 3: continue
            
            try:
                # Extração genérica para layout de tabela clássica
                # Geralmente: Código | Descrição | Qtd | Un | Valor...
                nome = row.find("span", class_="txtTit") or cols[1]
                codigo_elem = row.find("span", class_="RCod") or cols[0]
                
                # Procura por valores numéricos que pareçam Qtd e Valor
                texto_linha = row.get_text()
                qtd = Decimal("1")
                vuni = Decimal("0")
                vtot = Decimal("0")
                
                # Tenta seletores específicos conhecidos
                qtd_elem = row.find("span", class_="Rqtd")
                if qtd_elem:
                    qtd = self._to_decimal(qtd_elem.text.split(":")[-1])
                
                vuni_elem = row.find("span", class_="RvalUnit")
                if vuni_elem:
                    vuni = self._to_decimal(vuni_elem.text.split(":")[-1])
                
                vtot_elem = row.find("span", class_="valor")
                if vtot_elem:
                    vtot = self._to_decimal(vtot_elem.text)
                
                descricao = nome.get_text().strip()
                codigo = re.sub(r"\D", "", codigo_elem.get_text()) if codigo_elem else ""

                itens.append(ItemNotaDTO(
                    ean=self._identificador_produto(codigo, row.get_text(), descricao),
                    descricao=descricao,
                    quantidade=qtd,
                    valor_unitario=vuni,
                    valor_total=vtot if vtot > 0 else (qtd * vuni)
                ))
            except:
                continue
        return itens

    def _extract_chave(self, soup: BeautifulSoup) -> str:
        chave_elem = soup.find("span", class_="chave")
        if chave_elem:
            return re.sub(r"\D", "", chave_elem.text)
        return ""

    def _extract_fornecedor(self, soup: BeautifulSoup) -> FornecedorDTO:
        # Geralmente no div.txtCenter superior
        centers = soup.find_all("div", class_="txtCenter")
        razao_social = "MERCADO DESCONHECIDO"
        cnpj = "00000000000000"
        
        for div in centers:
            text = div.get_text(strip=True)
            if "CNPJ:" in text:
                cnpj_match = re.search(r"CNPJ:\s*([\d\.\-\/]+)", text)
                if cnpj_match:
                    cnpj = re.sub(r"\D", "", cnpj_match.group(1))
                # A razão social geralmente está no div anterior ou é o topo deste
                if div.previous_sibling:
                    razao_social = div.previous_sibling.get_text(strip=True) or razao_social
                break
            elif not div.find("span") and len(text) > 5:
                # Provável razão social se estiver no topo
                razao_social = text
                
        return FornecedorDTO(razao_social=razao_social, cnpj=cnpj)

    def _extract_itens(self, soup: BeautifulSoup) -> list[ItemNotaDTO]:
        itens = []
        table = soup.find("table", id="tabResult")
        if not table:
            return []

        rows = table.find_all("tr")
        for row in rows:
            try:
                # Seletores baseados na estrutura de NFC-e de Goiás
                nome_elem = row.find("span", class_="txtTit")
                if not nome_elem: continue
                
                codigo_elem = row.find("span", class_="RCod")
                codigo = re.sub(r"\D", "", codigo_elem.text) if codigo_elem else ""
                
                qtd_elem = row.find("span", class_="Rqtd")
                qtd = self._to_decimal(qtd_elem.text.split(":")[-1]) if qtd_elem else Decimal("1")
                
                vuni_elem = row.find("span", class_="RvalUnit")
                vuni = self._to_decimal(vuni_elem.text.split(":")[-1]) if vuni_elem else Decimal("0")
                
                vtot_elem = row.find("span", class_="valor")
                vtot = self._to_decimal(vtot_elem.text) if vtot_elem else (qtd * vuni)

                ean = self._identificador_produto(codigo, row.get_text(), nome_elem.text)

                itens.append(ItemNotaDTO(
                    ean=ean,
                    descricao=nome_elem.text.strip(),
                    quantidade=qtd,
                    valor_unitario=vuni,
                    valor_total=vtot
                ))
            except Exception as e:
                logger.debug(f"Falha ao parsear linha de item: {e}")
                continue
        
        return itens

    def _extract_info_adicional(self, soup: BeautifulSoup) -> dict:
        """Extrai descontos totais e formas de pagamento."""
        info = {"desconto": Decimal("0"), "pagamento": "NÃO IDENTIFICADO"}
        
        # Procura por "Desconto" na página
        desconto_elem = soup.find("span", string=re.compile(r"Desconto", re.I))
        if desconto_elem and desconto_elem.find_next("span", class_="valor"):
            info["desconto"] = self._to_decimal(desconto_elem.find_next("span", class_="valor").text)
            
        # Forma de pagamento
        pag_elem = soup.find("label", string=re.compile(r"Forma de Pagamento", re.I))
        if pag_elem:
            val_pag = pag_elem.find_next("td")
            if val_pag:
                info["pagamento"] = val_pag.get_text(strip=True)
                
        return info

    def _extract_data_emissao(self, soup: BeautifulSoup) -> datetime:
        text = soup.get_text()
        match = re.search(
            r"(?:Emissão|Emissao):\s*(\d{2}/\d{2}/\d{4}\s*\d{2}:\d{2}:\d{2})",
            text,
            re.I,
        )
        if match:
            try:
                return datetime.strptime(match.group(1), "%d/%m/%Y %H:%M:%S")
            except:
                pass
        return datetime.now()

    def _extract_valor_total(self, soup: BeautifulSoup) -> Decimal:
        total_elem = soup.find("span", class_="totalNfe")
        if total_elem:
            return self._to_decimal(total_elem.text)
        return Decimal("0")

    def _extract_numero_nota(self, soup: BeautifulSoup) -> str:
        text = soup.get_text()
        match = re.search(r"(?:Número|Numero):\s*(\d+)", text, re.I)
        return match.group(1) if match else "0"

    def _to_decimal(self, text: str) -> Decimal:
        try:
            return Decimal(text.strip().replace(".", "").replace(",", "."))
        except:
            return Decimal("0")

    def _identificador_produto(self, codigo: str, texto_linha: str, descricao: str) -> str:
        """Retorna GTIN, codigo interno ou identificador sintetico estavel para itens sem EAN."""
        if len(codigo) >= 8:
            return codigo

        ean_match = re.search(r"GTIN:\s*(\d+)", texto_linha, re.I)
        if ean_match and ean_match.group(1) != "0":
            return ean_match.group(1)

        if codigo and codigo != "0":
            return codigo

        base = self._normalizar_descricao_sem_ean(descricao)
        digest = hashlib.sha1(base.encode("utf-8")).hexdigest()[:12].upper()
        return f"SEM_EAN_{digest}"

    def _normalizar_descricao_sem_ean(self, descricao: str) -> str:
        """Normaliza descricoes sem EAN antes do hash, sem heuristicas de merge."""
        texto = (descricao or "PRODUTO_SEM_EAN").strip().upper()
        texto = unicodedata.normalize("NFKD", texto)
        texto = "".join(char for char in texto if not unicodedata.combining(char))
        texto = re.sub(r"[^A-Z0-9\s]", " ", texto)
        texto = re.sub(r"\s+", " ", texto).strip()
        texto = re.sub(r"\b(\d+)\s+(KG|G|ML|L|LT|UN|UND)\b", r"\1\2", texto)
        return re.sub(r"\s+", " ", texto).strip() or "PRODUTO_SEM_EAN"
