export interface GastoCategoria {
  categoria: string;
  total: number;
}

export interface DashboardResumo {
  total_geral: number;
  por_categoria: GastoCategoria[];
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
  extraction_quality_status?: 'ok' | 'warning' | 'failed' | string | null;
  extraction_parser_source?: 'deterministic' | 'ai_fallback' | string | null;
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

export interface ImportacaoHistoricoItem {
  id: string;
  chave_acesso: string;
  numero_nota: string;
  fornecedor: string;
  data_emissao: string;
  valor_total: number | string;
  status: 'active' | 'archived' | string;
  created_at: string;
  imported_at: string;
  extraction_quality_status?: 'ok' | 'warning' | 'failed' | string | null;
  extraction_parser_source?: 'deterministic' | 'ai_fallback' | string | null;
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
