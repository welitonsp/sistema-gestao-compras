# Sistema de Gestão de Compras V2.0 🚀

Solução institucional para ingestão, auditoria e análise inteligente de documentos fiscais (NFC-e e NF-e), utilizando IA para extração e classificação de dados.

## 🏗️ Arquitetura

O sistema é dividido em:
- **Backend API (FastAPI):** Interface RESTful assíncrona.
- **Worker (ARQ/Redis):** Processamento em background para grandes volumes.
- **Engine de IA (Groq-first):** Extração estruturada e classificação de produtos via Groq. Gemini 1.5 Flash fica disponível apenas como recurso opcional de visão quando `ENABLE_GEMINI=true`.
- **Configuração de IA:** `AI_PROVIDER=groq` e `ENABLE_GEMINI=false` são os padrões; `GEMINI_API_KEY` é opcional.
- **Parser Determinístico:** Motor de alta performance para SEFAZ GO.

## ✅ Estado Operacional Atual (Junho/2026)

Checkpoint para evitar retrabalho em fases já encerradas:

- **Canonização de produtos (H9E):** concluída e em produção controlada. Inclui preview, confirmação, reversão, badges no catálogo, painel administrativo, dashboards canônicos e Dashboard Comparativo pós-canonização.
- **Reversão de canonização:** implementada como reversão lógica (`status = "reverted"`), preservando produtos, itens fiscais, histórico de preços, EAN fiscal e `descricao_original`.
- **CSV sanitization (H9F):** centralizada em `backend/core/csv_utils.py` e aplicada aos exports conhecidos, incluindo Dashboard, catálogo, auditoria e mapeamentos de canonização.
- **AuditLog hardening (H10B):** detalhes de auditoria passam por redação central em `backend/core/security.py`, com allow-list e proteção contra serialização bruta futura.
- **ClassificacaoCache e autocura tenant-aware (H10A-H10E):** cache, exemplos verificados, importação SEFAZ, importação manual, contexto de categorias de IA e sugestões de autocura respeitam `department_id` quando disponível, com fallback global explícito apenas quando não há tenant.
- **Chat de auditoria read-only (H10F):** o assistente IA bloqueia intenções de alteração de catálogo e valida de forma deterministica que SQL gerado seja uma única consulta somente leitura.
- **Chat de auditoria tenant-safe (H10G):** consultas geradas por IA são bloqueadas quando omitirem o `department_id` de usuários não-admin ou tentarem acessar identificadores fiscais/pessoais sensíveis.
- **Chat de auditoria com RBAC (H10H):** acesso restrito a `ADMIN`, `AUDITOR` e `MANAGER`; usuários não-admin sem departamento são bloqueados antes de chamar a IA.
- **Chat de auditoria no frontend (H10I):** botão do Auditor AI só aparece para perfis autorizados e com escopo de departamento quando necessário.
- **Chat de auditoria com SQL allow-list (H10J):** SQL gerado por IA só executa com tabelas/colunas permitidas, sem `SELECT *` e sem tabelas administrativas/fiscais sensíveis.
- **Chat de auditoria com saída sanitizada (H10K):** `data_summary`, erro técnico e resposta textual passam por redação defensiva antes de voltar ao frontend.
- **Chat de auditoria com limite de execução (H10L):** toda consulta validada é executada em subquery com `LIMIT 50` efetivo e timeout controlado.

Não refazer sem nova motivação técnica:

- não recriar endpoint de reversão de canonização;
- não recriar botão/modal de reversão no Catálogo;
- não recriar sanitização CSV local por endpoint;
- não voltar a gravar `AuditLog.detalhes` com payload bruto;
- não tratar `ClassificacaoCache` como global quando houver `department_id`;
- não mostrar sugestões de autocura de outro departamento para usuários `MANAGER`;
- não permitir mutações de catálogo pelo chat de auditoria;
- não executar SQL do chat para usuários não-admin sem filtro explícito de `department_id`;
- não expor o chat de auditoria para `OPERATOR` ou usuários não-admin sem departamento;
- não renderizar o botão do Auditor AI para perfis sem permissão;
- não permitir novas tabelas/colunas no chat de auditoria sem atualizar a allow-list e os testes;
- não retornar dados brutos do chat de auditoria sem passar pela sanitização defensiva;
- não executar SQL do chat sem wrapper de limite e timeout;
- não alterar fisicamente `Produto`, `ItemNotaFiscal`, `HistoricoPreco`, `descricao_original` ou EAN fiscal para canonização.

Referência arquitetural: [docs/PRODUCT_CANONIZATION_ARCHITECTURE.md](docs/PRODUCT_CANONIZATION_ARCHITECTURE.md).

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
- **AuditLog:** use `redact_audit_details` para qualquer novo detalhe estruturado de auditoria.
- **CSV:** use `sanitize_csv_cell` em qualquer novo export CSV.

## 📑 Documentação de Importação

Veja o guia detalhado em [docs/cfe_importacao.md](docs/cfe_importacao.md) para entender os métodos de importação (QR Code, Chave, HTML e OCR).

---
*Desenvolvido para fins institucionais e auditoria de compras.*
