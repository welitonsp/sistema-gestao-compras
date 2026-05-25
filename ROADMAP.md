# 🚀 Strategic Roadmap - Gestão de Compras (Enterprise Edition)

Este documento define a visão estratégica e arquitetural do **Sistema de Gestão de Compras**. Ele serve como a "Estrela Guia" (North Star) para Engenheiros de Software, Arquitetos e Agentes de IA que atuarão no projeto.

A arquitetura foi projetada visando padrões de mercado **"Big Tech" (Alta Disponibilidade, Observabilidade, Segurança Zero-Trust e Escalabilidade Nuvem)** e rigor de auditoria nível **"Big Four"**.

---

## 📍 Estado Atual: Versão 2.x (Fundação Robusta)
O sistema atingiu a maturidade institucional. A infraestrutura base está consolidada:
- **Core:** FastAPI (Async), PostgreSQL (Neon), Redis (ARQ/Worker).
- **Frontend:** SPA React + Vite + Tailwind CSS (WCAG 2.1 AA Compliant).
- **Segurança:** Autenticação JWT, Proteção de Rotas, Sanitização DDL via Alembic.
- **Inteligência:** Classificação "Human-in-the-loop", OCR Multimodal (Gemini Vision) e Parsers Determinísticos (SEFAZ GO).
- **Auditoria:** Trilha de logs imutável, exportação corporativa (CSV/Excel), detecção de duplicidade de pagamentos e volatilidade de mercado.
- **DevOps:** Docker Multi-stage build para implantação em provedores serverless.

---

## 🔭 Horizontes Estratégicos (Visão V3.0+)

As próximas fases focam em expansão para múltiplos departamentos, inteligência preditiva e integração profunda de ecossistema.

### 🛡️ Horizonte 1: Governança Corporativa e Multi-Tenancy (RBAC)
Transformar o sistema de single-tenant para multi-tenant, permitindo o uso compartilhado por diferentes secretarias ou empresas de um mesmo conglomerado.
- **[ ] Controle de Acesso Baseado em Roles (RBAC):** Implementar perfis rígidos (`SuperAdmin`, `Auditor`, `GestorFinanceiro`, `OperadorIngestao`).
- **[ ] Data Isolation (Row-Level Security):** Garantir que usuários de um departamento vejam apenas notas e métricas do seu centro de custo.
- **[ ] Single Sign-On (SSO):** Integração com provedores de identidade corporativos (Azure AD, Okta, Google Workspace) via OAuth2/OIDC.
- **[ ] Advanced Audit Trail:** Integração dos logs de auditoria com ferramentas SIEM (Splunk, Datadog) para monitoramento de conformidade.

### 🧠 Horizonte 2: IA Preditiva e Agentes Autônomos
Evoluir a IA de uma ferramenta de "Extração" para uma ferramenta de "Recomendação e Ação".
- **[ ] Forecast de Gastos (Séries Temporais):** Utilizar modelos preditivos para estimar gastos do próximo trimestre baseados no histórico de consumo e sazonalidade.
- **[ ] Detecção de Anomalias Não-Supervisionada:** IA que detecta automaticamente compras fora do padrão institucional sem depender de limiares percentuais fixos (Machine Learning puro).
- **[ ] Autocura de Catálogo:** Agentes de IA que periodicamente varrem o `ClassificacaoCache` para unificar marcas (ex: "Coca Cola" e "Coca-cola") e sugerir fusões estruturais.
- **[ ] Chatbot de Auditoria (RAG):** Interface em linguagem natural no Dashboard para perguntas como: *"Quanto gastamos com material de limpeza no mês passado no fornecedor X?"*.

### ⚡ Horizonte 3: Escalabilidade Cloud-Native e Event-Driven
Preparar a infraestrutura para suportar volumes massivos de notas (milhões/mês) sem degradação.
- **[ ] Arquitetura Orientada a Eventos:** Migrar o fluxo de processamento de notas para um barramento de eventos pub/sub (Apache Kafka ou RabbitMQ Streams) para resiliência extrema.
- **[ ] Kubernetes Ready:** Criação de Helm Charts para deploy orquestrado, permitindo autoscaling do worker de OCR independentemente da API web.
- **[ ] Storage Object Distribuído:** Armazenamento de PDFs e imagens originais em S3 (AWS) ou Blob Storage (GCP/Azure) no lugar do sistema de arquivos local.

### 🔗 Horizonte 4: Integração de Ecossistema (Open API)
Tornar o sistema a fonte central de verdade para gestão de gastos.
- **[ ] Webhooks Dinâmicos:** Disparo em tempo real de eventos (ex: `invoice.fraud_detected`, `price.surge`) para o Slack, Microsoft Teams ou e-mail corporativo.
- **[ ] Integração com ERPs:** Camada de exportação via API (Swagger/OpenAPI estabilizada) ou integração nativa com sistemas contábeis (SAP, TOTVS, Oracle).
- **[ ] Portal do Fornecedor:** Interface simplificada para que fornecedores façam upload de suas próprias notas fiscais, invertendo o ônus da ingestão.

---

## 🛠️ Diretrizes Arquiteturais (Para Desenvolvedores e IAs)

Qualquer código submetido a este repositório **deve** obedecer aos seguintes pilares:

1. **API First & Contract Driven:**
   - O backend (FastAPI) e frontend (React) devem ser estritamente tipados.
   - Pydantic models (Backend) devem refletir as Interfaces TypeScript (Frontend). Mutações de API requerem atualização síncrona dos contratos.
2. **Design For Failure (Resiliência):**
   - Nenhuma chamada a serviço externo (SEFAZ, LLMs, Banco) deve bloquear o fluxo principal sem um `timeout` definido, política de `retry` (Exponential Backoff) ou `circuit breaker`.
3. **Observability First:**
   - Toda operação transacional de mutação (`INSERT`, `UPDATE`, `DELETE`) deve ser obrigatoriamente logada na tabela de auditoria (`AuditLog`).
4. **Performance by Default:**
   - Operações em lote no banco devem usar `Bulk Insert`. Evite o antipadrão N+1 em queries do SQLAlchemy usando estratégias explícitas de loading (`selectinload`, `joinedload`).
5. **Inclusão Inegociável (A11y):**
   - Novas telas React devem nascer com conformidade WCAG 2.1 AA. O uso de `aria-labels`, `focus rings`, `aria-live` regions e suporte a teclado não são opcionais.

---
*Documento vivo. Atualizado periodicamente para refletir as necessidades de governança tecnológica.*
