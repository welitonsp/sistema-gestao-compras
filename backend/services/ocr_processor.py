"""Service for high-precision OCR and data extraction using Gemini Vision."""

from __future__ import annotations

import json
import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any

import google.generativeai as genai
from PIL import Image
from pdf2image import convert_from_path

from core.config import settings
from core.logger import get_logger
from backend.schemas.internal import NotaFiscalDTO

logger = get_logger("services.ocr")

class GeminiOCRService:
    """Uses Gemini 1.5 Flash to extract structured data from images/PDFs."""

    def __init__(self, api_key: str = settings.gemini_api_key, model_name: str = "gemini-1.5-flash"):
        if not api_key:
            raise ValueError("GEMINI_API_KEY não configurada.")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)
        self._log = logger

    async def extrair_de_imagem(self, caminho_imagem: Path) -> Optional[NotaFiscalDTO]:
        """Extracts data from a single image file."""
        self._log.info(f"Iniciando OCR via Gemini para imagem: {caminho_imagem.name}")
        
        prompt = (
            "Você é um especialista em extração de dados de cupons fiscais brasileiros (NFC-e/NF-e).\n"
            "Analise a imagem anexa e extraia as seguintes informações em formato JSON:\n"
            "1. chave_acesso (44 dígitos)\n"
            "2. data_emissao (ISO format YYYY-MM-DD)\n"
            "3. fornecedor (objeto com cnpj e razao_social)\n"
            "4. itens (lista com ean, descricao, quantidade, valor_unitario, valor_total)\n"
            "5. valor_total (valor total da nota)\n\n"
            "REGRAS:\n"
            "- Se não houver EAN, retorne null no campo ean.\n"
            "- Se não encontrar a chave de acesso, tente compor com os dados disponíveis.\n"
            "- Retorne APENAS o JSON válido."
        )

        try:
            img = Image.open(caminho_imagem)
            # Executa em thread pool pois a lib do google é síncrona para upload/generate
            response = await asyncio.to_thread(
                self.model.generate_content,
                [prompt, img]
            )
            
            texto_json = self._limpar_json(response.text)
            dados = json.loads(texto_json)
            return NotaFiscalDTO.model_validate(dados)

        except Exception as e:
            self._log.error(f"Erro no OCR Gemini (Imagem): {e}", exc_info=True)
            return None

    async def extrair_de_pdf(self, caminho_pdf: Path) -> Optional[NotaFiscalDTO]:
        """Converts PDF to images and extracts data from the first page."""
        self._log.info(f"Convertendo PDF para imagem para OCR: {caminho_pdf.name}")
        
        try:
            # Converte apenas a primeira página para economizar recursos (geralmente notas fiscais são 1 pág)
            paginas = await asyncio.to_thread(
                convert_from_path,
                caminho_pdf,
                first_page=1,
                last_page=1,
                fmt="jpeg"
            )
            
            if not paginas:
                return None
                
            # Salva temporariamente ou processa em memória
            temp_img_path = caminho_pdf.with_suffix(".temp.jpg")
            paginas[0].save(temp_img_path, "JPEG")
            
            resultado = await self.extrair_de_imagem(temp_img_path)
            
            # Limpeza
            if temp_img_path.exists():
                temp_img_path.unlink()
                
            return resultado

        except Exception as e:
            self._log.error(f"Erro no OCR Gemini (PDF): {e}", exc_info=True)
            return None

    def _limpar_json(self, texto: str) -> str:
        """Remove markdown blocks (```json ... ```) if present."""
        texto = texto.strip()
        if texto.startswith("```json"):
            texto = texto[7:]
        if texto.startswith("```"):
            texto = texto[3:]
        if texto.endswith("```"):
            texto = texto[:-3]
        return texto.strip()
