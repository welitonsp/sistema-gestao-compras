# Sistema de Gestão de Compras V2.0 🚀

Solução institucional para ingestão, auditoria e análise inteligente de documentos fiscais (NFC-e e NF-e), utilizando IA para extração e classificação de dados.

## 🏗️ Arquitetura

O sistema é dividido em:
- **Backend API (FastAPI):** Interface RESTful assíncrona.
- **Worker (ARQ/Redis):** Processamento em background para grandes volumes.
- **Engine de IA (Groq-first):** Extração estruturada e classificação de produtos via Groq. Gemini 1.5 Flash fica disponível apenas como recurso opcional de visão quando `ENABLE_GEMINI=true`.
- **Configuração de IA:** `AI_PROVIDER=groq` e `ENABLE_GEMINI=false` são os padrões; `GEMINI_API_KEY` é opcional.
- **Parser Determinístico:** Motor de alta performance para SEFAZ GO.

## 🛠️ Configuração Rápida

1. **Requisitos:** Python 3.11+, Docker, Redis.
2. **Ambiente:**
   ```bash
   cp .env.example .env
   # Edite o .env com suas chaves reais
   ```
3. **Execução via Docker:**
   ```bash
   docker-compose up --build
   ```

## 🔐 Segurança

- **Secrets:** Nunca faça commit de arquivos `.env` ou chaves privadas. Use o `.env.example` como base.
- **CORS:** Em produção, a variável `CORS_ORIGINS` deve ser configurada obrigatoriamente.
- **Logs:** O sistema possui filtros automáticos de sanitização para ocultar chaves fiscais e CNPJs nos arquivos de log.

## 📑 Documentação de Importação

Veja o guia detalhado em [docs/cfe_importacao.md](docs/cfe_importacao.md) para entender os métodos de importação (QR Code, Chave, HTML e OCR).

---
*Desenvolvido para fins institucionais e auditoria de compras.*
