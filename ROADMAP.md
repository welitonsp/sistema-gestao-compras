# 🚀 Roadmap de Melhorias - Sistema Gestão Compras V2.0

Este documento centraliza as melhorias planejadas, novas funcionalidades e estratégias de qualidade para elevar o sistema ao nível de excelência.

---

## 🏗️ Fase 6: Inteligência e Performance (Concluída ✅)

- [x] **6.1. Cache de Classificação de IA**
  - **Objetivo:** Evitar chamadas repetidas à API da Groq para produtos já classificados.
  - **Ação:** Criada tabela `classificacao_cache` e lógica de busca/salvamento no `ia_groq_utils.py`.
  - **Impacto:** Redução drástica de custos e latência.

- [x] **6.2. Engine de Alertas e Insights de Preço**
  - **Objetivo:** Transformar dados em economia real.
  - **Ação:** Criado `PriceInsightsService` e script `ver_alertas_preco.py` integrado ao menu principal.
  - **Impacto:** Identificação proativa de variações de preço acima de 10%.

- [x] **6.3. Padronização de Marcas (Canonização)**
  - **Objetivo:** Unificar variações de nomes de marcas.
  - **Ação:** Refinado o prompt do LLMA no `ia_groq_utils.py` com instruções explícitas de canonização.
  - **Impacto:** Melhor agrupamento e comparação de preços entre marcas.

---

## 🌐 Fase 7: Expansão de Interface e Integração (Em Andamento 🚧)

- [x] **7.1. API REST Completa (FastAPI)**
  - **Objetivo:** Desacoplar o backend do CLI.
  - **Ação:** Criada estrutura FastAPI, schemas de dashboard, e rotas para `/health`, `/notas` e `/dashboard`.
  - **Impacto:** Sistema pronto para integração com frontends modernos.

- [x] **7.2. Sistema de Mensageria (Background Tasks)**
  - **Objetivo:** Processamento assíncrono real de grandes lotes.
  - **Ação:** Integrado `arq` com Redis. Criado `backend/core/worker.py` e endpoint `/processar-lote`.
  - **Impacto:** O sistema pode processar centenas de notas em paralelo sem bloquear a API.

- [x] **7.3. OCR de Alta Precisão**
  - **Objetivo:** Suportar fotos de cupons e PDFs não-digitais.
  - **Ação:** Criado `GeminiOCRService` utilizando Gemini 1.5 Flash (Vision). Integrado ao `PDFProcessorService` para suporte a PDF, JPG e PNG.
  - **Impacto:** O sistema agora extrai dados reais de imagens e PDFs físicos com alta precisão, sem depender de simulações.

---

## 🧪 Fase 8: Resiliência, Qualidade e Importação Profissional (Concluída ✅)

- [x] **8.1. Suite de Testes de Regressão de IA**
    - **Objetivo:** Garantir que novos prompts não piorem a classificação.
    - **Ação:** Criado `golden_dataset.json` e script `test_ai_regression.py`.
    - **Impacto:** Segurança total em ajustes finos da IA.

- [x] **8.2. Health Check e Monitoramento**
    - **Objetivo:** Visibilidade total do estado do sistema.
    - **Ação:** Endpoint `/health` expandido para monitorar DB, Redis e conectividade da API Groq.
    - **Impacto:** Monitoramento proativo de infraestrutura.

- [x] **8.3. Parser Determinístico "Estilo Dinheiro na Nota"**
    - **Objetivo:** Importação instantânea, gratuita e ultra-detalhada.
    - **Ação:** Implementado `SefazGoParser` para extração de EAN/GTIN, Descontos, Impostos e Formas de Pagamento.
    - **Impacto:** Precisão de 100% e custo zero de tokens para SEFAZ GO.

- [x] **8.4. Navegação Semi-Automática (Anti-CAPTCHA)**
    - **Objetivo:** Facilitar a consulta por chave de acesso sem custos de APIs pagas.
    - **Ação:** Criado script `importar_sefaz_navegador.py` usando Selenium para preenchimento automático e captura pós-captcha.
    - **Impacto:** Experiência de usuário idêntica a apps de cashback profissionais.

- [x] **8.5. Suporte Universal (NF-e + NFC-e)**
    - **Objetivo:** Importar tanto cupons de mercado quanto notas de atacado/online.
    - **Ação:** Detecção automática de layout (Modelo 55 e 65) e suporte a "Pasted HTML".
    - **Impacto:** Flexibilidade total para qualquer tipo de documento fiscal.

---

## 📈 Histórico de Conclusões

- **V1.0:** Importação PDF/XML básica e banco de dados.
- **V1.5:** Integração com IA (Groq/Llama 3) e Classificação Automática.
- **V2.0:** Dashboard, Alertas de Preço, Canonização, OCR Vision, Redis e Importação Profissional Determinística.

---
*   **Fases 1-5:** Concluídas (Segurança, Pipeline IA, SQLAlchemy, Unificação de Ingestão e Observabilidade).
