import type {
  DeleteImportacaoRequest,
  DeleteImportacaoResponse,
  ImportacaoLoteChavesRequest,
  ImportacaoLoteChavesResponse,
  ImportacaoNotaResponse,
} from '../types/api';

const API_BASE = '/api/v1';

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

const handleUnauthorized = () => {
  window.dispatchEvent(new Event('auth:expired'));
  throw new Error('Sessão expirada');
};

const extractErrorMessage = async (response: Response): Promise<{ message: string; detail?: unknown }> => {
  try {
    const body = await response.json();
    const detail = body?.detail;
    if (typeof detail === 'string') return { message: detail, detail };
    if (typeof body?.message === 'string') return { message: body.message, detail };
    if (typeof body?.mensagem === 'string') return { message: body.mensagem, detail };
    return { message: 'Falha na requisicao', detail };
  } catch {
    return { message: 'Falha na requisicao' };
  }
};

const throwApiError = async (response: Response): Promise<never> => {
  const { message, detail } = await extractErrorMessage(response);
  throw new ApiError(response.status, message, detail);
};

export const apiClient = {
  get: async <T>(endpoint: string): Promise<T> => {
    const response = await fetch(`${API_BASE}${endpoint}`, {
      credentials: 'include', // Envia cookies automaticamente
    });
    
    if (response.status === 401) {
      return handleUnauthorized();
    }
    
    if (!response.ok) return throwApiError(response);
    return response.json();
  },

  post: async <T>(endpoint: string, body: any, options: any = {}): Promise<T> => {
    const response = await fetch(`${API_BASE}${endpoint}`, {
      method: options.method || 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include',
      body: options.method === 'DELETE' ? undefined : JSON.stringify(body),
    });

    if (response.status === 401) {
      return handleUnauthorized();
    }

    if (!response.ok) return throwApiError(response);
    return response.json();
  },

  patch: async <T>(endpoint: string, body: any): Promise<T> => {
    const response = await fetch(`${API_BASE}${endpoint}`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include',
      body: JSON.stringify(body),
    });

    if (response.status === 401) {
      return handleUnauthorized();
    }

    if (!response.ok) return throwApiError(response);
    return response.json();
  },

  delete: async <T>(endpoint: string): Promise<T> => {
    const response = await fetch(`${API_BASE}${endpoint}`, {
      method: 'DELETE',
      credentials: 'include',
    });

    if (response.status === 401) {
      return handleUnauthorized();
    }

    if (!response.ok) return throwApiError(response);
    return response.json();
  },
};

export const importarLoteChaves = (
  payload: ImportacaoLoteChavesRequest,
): Promise<ImportacaoLoteChavesResponse> => apiClient.post<ImportacaoLoteChavesResponse>('/notas/importacao-lote-chaves', payload);

export const excluirImportacao = (
  notaId: string,
  payload: DeleteImportacaoRequest = {},
): Promise<DeleteImportacaoResponse> => apiClient.post<DeleteImportacaoResponse>(`/notas/importacoes/${notaId}/excluir`, payload);

export const importarPdfNfce = async (arquivo: File): Promise<ImportacaoNotaResponse> => {
  const formData = new FormData();
  formData.append('arquivo', arquivo);

  const response = await fetch(`${API_BASE}/notas/importacao-pdf-nfce`, {
    method: 'POST',
    credentials: 'include',
    body: formData,
  });

  if (response.status === 401) {
    return handleUnauthorized();
  }

  if (!response.ok) return throwApiError(response);
  return response.json();
};
