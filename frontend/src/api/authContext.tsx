import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';

interface AuthUser {
  username: string;
  role: string;
}

interface AuthContextType {
  token: string | null;
  user: AuthUser | null;
  login: (token: string) => void;
  logout: () => void;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isInitialized, setIsInitialized] = useState(false);

  // Verifica sessão ao carregar a página
  useEffect(() => {
    const checkSession = async () => {
      try {
        // Tenta buscar o perfil do usuário logado (endpoint a ser criado ou usar health check estendido)
        const userData = await apiClient.get<User>('/users/me');
        setUser({ username: userData.username, role: userData.role });
      } catch {
        setUser(null);
      } finally {
        setIsInitialized(true);
      }
    };
    checkSession();
  }, []);

  const login = (userData: AuthUser) => {
    setUser(userData);
  };

  const logout = async () => {
    try {
      await fetch('/api/v1/auth/logout', { method: 'POST' });
    } finally {
      setUser(null);
    }
  };

  useEffect(() => {
    const handleAuthExpired = () => {
      setUser(null);
    };

    window.addEventListener('auth:expired', handleAuthExpired);
    return () => {
      window.removeEventListener('auth:expired', handleAuthExpired);
    };
  }, []);

  const isAuthenticated = !!user;

  if (!isInitialized) return null; // Aguarda inicialização segura

  return (
    <AuthContext.Provider value={{ token, user, login, logout, isAuthenticated }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
