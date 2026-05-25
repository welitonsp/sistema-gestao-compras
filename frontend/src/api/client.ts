const API_BASE = '/api/v1';

const handleUnauthorized = () => {
  window.dispatchEvent(new Event('auth:expired'));
  throw new Error('Sessão expirada');
};

export const apiClient = {
  get: async <T>(endpoint: string): Promise<T> => {
    const response = await fetch(`${API_BASE}${endpoint}`, {
      credentials: 'include', // Envia cookies automaticamente
    });
    
    if (response.status === 401) {
      return handleUnauthorized();
    }
    
    if (!response.ok) throw new Error('Falha na requisição');
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

    if (!response.ok) throw new Error('Falha na requisição');
    return response.json();
  },
};
