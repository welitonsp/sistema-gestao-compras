export interface GastoCategoria {
  categoria: string;
  total: number;
}

export interface EvolucaoMensal {
  mes: string;
  total: number;
}

export interface TopProduto {
  ean: string;
  produto: string;
  total: number;
}

export interface TopFornecedor {
  fornecedor_id: string;
  fornecedor: string;
  total: number;
}

export interface AlertaRisco {
  tipo: string;
  severidade: string;
  titulo: string;
  mensagem: string;
  valor?: number;
}

export interface HistoricoPrecoProduto {
  data_compra: string;
  fornecedor: string;
  preco_unitario: number;
  quantidade: number;
  valor_total: number;
  numero_nota?: string;
}

export interface ProductPriceHistoryResponse {
  ean: string;
  nome_produto: string;
  historico: HistoricoPrecoProduto[];
}

export interface ResumoFornecedor {
  total_gasto: number;
  quantidade_notas: number;
  ticket_medio: number;
  primeira_compra?: string | null;
  ultima_compra?: string | null;
}

export interface ConcentracaoFornecedor {
  percentual: number;
  nivel: string; // info, warning, danger
  mensagem: string;
}

export interface NotaFornecedor {
  data_emissao: string;
  numero_nota: string;
  valor_total: number;
}

export interface TopProdutoFornecedor {
  ean: string;
  nome_produto: string;
  quantidade_total: number;
  total_gasto: number;
  preco_medio: number;
  quantidade_notas: number;
}

export interface SupplierDrilldownResponse {
  fornecedor_id: string;
  nome_exibicao: string;
  resumo: ResumoFornecedor;
  concentracao?: ConcentracaoFornecedor;
  notas: NotaFornecedor[];
  top_produtos: TopProdutoFornecedor[];
}

export interface DataHealthMetrics {
  total_notas: number;
  notas_ok: number;
  notas_warning: number;
  notas_failed: number;
  percentual_saude: number;
  nivel: "ok" | "warning" | "danger" | string;
  total_itens: number;
  itens_sem_ean: number;
  total_mismatches: number;
  descricoes_vazias: number;
  quantidades_invalidas: number;
  valores_invalidos: number;
}

export interface DashboardResumo {
  total_geral: number;
  por_categoria: GastoCategoria[];
  evolucao_mensal: EvolucaoMensal[];
  top_produtos: TopProduto[];
  top_fornecedores: TopFornecedor[];
  alertas_risco: AlertaRisco[];
  saude_dados?: DataHealthMetrics | null;
}

export interface AlertaPreco {
  ean: string;
  produto: string;
  preco_medio: number;
  preco_atual: number;
  variacao_percentual: number;
  data_ultima_compra: string;
  local: string;
}

export interface AlertasPrecoResponse {
  alertas: AlertaPreco[];
}

export interface OpportunityScoreBreakdown {
  financial_impact_score: number;
  confidence_score: number;
  recurrence_score: number;
  total_score: number;
}

export interface SavingOpportunity {
  id: string;
  type: "price_gap" | "supplier_switch" | "recurrence_buy" | "data_quality" | string;
  title: string;
  description: string;
  product_name: string | null;
  ean: string | null;
  category: string | null;
  current_supplier: string | null;
  suggested_supplier: string | null;
  reference_date: string;
  current_unit_price: number | null;
  benchmark_unit_price: number | null;
  estimated_savings: number;
  estimated_savings_percent: number | null;
  confidence: "high" | "medium" | "low" | "insufficient_data";
  score: OpportunityScoreBreakdown;
  reasons: string[];
  warnings: string[];
}

export interface SavingOpportunitiesSummary {
  period_start: string;
  period_end: string;
  total_estimated_savings: number;
  opportunity_count: number;
  high_confidence_count: number;
  medium_confidence_count: number;
  low_confidence_count: number;
  insufficient_data_count: number;
  opportunities: SavingOpportunity[];
}

export interface CategorySuggestionCandidate {
  ean: string;
  product_name: string;
  current_category: string | null;
  suggested_category: string | null;
  confidence: number;
  confidence_level: "high" | "medium" | "low" | "insufficient_data";
  source: "item_suggestion" | "classification_cache" | "rules" | "none";
  reason: string;
  occurrence_count: number;
  last_seen: string | null;
  can_confirm: boolean;
}

export interface CategorySuggestionCandidatesResponse {
  total_candidates: number;
  returned_count: number;
  candidates: CategorySuggestionCandidate[];
}

export interface CanonizationProduct {
  ean: string;
  name: string;
  category?: string | null;
}

export interface CanonizationMatch extends CanonizationProduct {
  similarity: number;
  reason: string | null;
}

export interface CanonizationCandidateGroup {
  primary: CanonizationProduct;
  matches: CanonizationMatch[];
}

export interface CanonizationCandidatesResponse {
  groups: CanonizationCandidateGroup[];
  total_groups: number;
  threshold: number;
  limit: number;
}

export type CanonizationMappingStatus = "all" | "active" | "inactive" | "reverted";

export interface CanonizationMappingItem {
  department_id: string;
  department_name: string | null;
  ean_original: string;
  original_name: string | null;
  ean_canonico: string;
  canonical_name: string | null;
  status: string;
  reason: string | null;
  confidence_score: number | null;
  confirmado_por: string | null;
  confirmado_em: string | null;
  revertido_por: string | null;
  revertido_em: string | null;
  revert_reason: string | null;
}

export interface CanonizationMappingsResponse {
  items: CanonizationMappingItem[];
  total: number;
  status: CanonizationMappingStatus;
  limit: number;
  offset: number;
}

export interface FornecedorImportado {
  id: string;
  cnpj: string;
  razao_social: string;
  nome_fantasia: string | null;
}

export interface NotaFiscalImportada {
  id: string;
  chave_acesso: string;
  numero_nota: string;
  data_emissao: string;
  valor_total: number;
  extraction_quality_status?: "ok" | "warning" | "failed" | string | null;
  extraction_parser_source?: "deterministic" | "ai_fallback" | string | null;
  extraction_item_count?: number | null;
  extraction_missing_ean_count?: number | null;
  extraction_empty_description_count?: number | null;
  extraction_invalid_quantity_count?: number | null;
  extraction_invalid_value_count?: number | null;
  extraction_total_itens?: number | string | null;
  extraction_total_nota?: number | string | null;
  extraction_total_mismatch?: boolean | null;
  extraction_quality_details?: string | Record<string, unknown> | null;
}

export interface ItemNotaFiscalImportado {
  id: string;
  codigo_produto: string;
  descricao: string;
  quantidade: number;
  valor_unitario: number;
  valor_total: number;
}

export interface ImportacaoChaveRequest {
  chave_acesso: string;
}

export interface ImportacaoNotaResponse {
  mensagem: string;
  fornecedor: FornecedorImportado;
  nota_fiscal: NotaFiscalImportada;
  itens: ItemNotaFiscalImportado[];
  total_itens: number;
}

export interface ImportacaoLoteChavesRequest {
  chaves_acesso: string[];
}

export type ImportacaoLoteChaveStatus = "success" | "duplicate" | "failed";

export interface ImportacaoLoteChaveResultado {
  chave_acesso: string;
  status: ImportacaoLoteChaveStatus;
  mensagem: string;
  nota_fiscal?: NotaFiscalImportada | null;
  error_code?: string | null;
}

export interface ImportacaoLoteChavesResponse {
  total: number;
  success_count: number;
  duplicate_count: number;
  failed_count: number;
  results: ImportacaoLoteChaveResultado[];
}

export interface ArchiveImportacaoRequest {
  motivo: string;
}

export interface ArchiveImportacaoResponse {
  mensagem: string;
  status: string;
  chave_acesso: string;
  archived_at: string;
  archived_by: string;
  archive_reason: string;
}

export interface DeleteImportacaoRequest {
  motivo?: string | null;
}

export interface DeleteImportacaoResponse {
  id: string;
  numero_nota: string;
  status: "deleted";
  itens_deletados: number;
  historico_precos_deletados: number;
  produtos_orfaos_deletados: number;
  fornecedores_orfaos_deletados: number;
  mensagem: string;
}

export interface ImportacaoHistoricoItem {
  id: string;
  chave_acesso: string;
  numero_nota: string;
  fornecedor: string;
  data_emissao: string;
  valor_total: number | string;
  status: "active" | "archived" | string;
  created_at: string;
  imported_at: string;
  extraction_quality_status?: "ok" | "warning" | "failed" | string | null;
  extraction_parser_source?: "deterministic" | "ai_fallback" | string | null;
  extraction_item_count?: number | null;
  extraction_missing_ean_count?: number | null;
  extraction_total_mismatch?: boolean | null;
  extraction_quality_details?: string | Record<string, unknown> | null;
  archived_at?: string | null;
  archived_by?: string | null;
  archive_reason?: string | null;
}

export interface ImportacoesHistoricoResponse {
  items: ImportacaoHistoricoItem[];
  total: number;
  limit: number;
  offset: number;
  status: string;
  quality_status: string;
}

export interface AuditLog {
  id: string;
  usuario: string;
  operacao: string;
  entidade: string;
  entidade_id: string;
  detalhes: string | null;
  ip_origem: string | null;
  criado_em: string;
}

export interface Produto {
  ean: string;
  nome_limpo: string;
  marca: string | null;
  categoria: string;
  unidade: string;
  canonizacao?: {
    status: string;
    ean_original: string;
    ean_canonico: string;
    reason?: string | null;
    confidence_score?: number | null;
  } | null;
}

export interface CanonizationRevertRequest {
  ean_original: string;
  reason?: string | null;
  confirmed: true;
}

export interface CanonizationRevertResponse {
  ean_original: string;
  ean_canonico: string;
  department_id: string;
  status: string;
  revertido_por: string;
  revertido_em: string;
  revert_reason: string | null;
  message: string;
}

export interface ProdutoUpdate {
  nome_limpo?: string;
  marca?: string;
  categoria?: string;
  unidade?: string;
}

export interface ForecastInfo {
  categoria: string;
  media_atual: number;
  projeção_proximo_mes: number;
  tendencia: string;
}

export interface AnomaliaEstatistica {
  ean: string;
  produto: string;
  preco_atual: number;
  media_historica: number;
  z_score: number;
  confianca: string;
}

export interface User {
  id: string;
  username: string;
  email: string | null;
  full_name: string | null;
  role: string;
  is_active: boolean;
  department_id: string | null;
}

export interface Department {
  id: string;
  name: string;
  description: string | null;
  is_active: boolean;
}
