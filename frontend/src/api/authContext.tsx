import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { apiClient } from './client';

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
  const [token, setToken] = useState<string | null>(null);
  const [isInitialized, setIsInitialized] = useState(false);

  const checkSession = async () => {
    try {
      const userData = await apiClient.get<any>('/users/me');
      setUser({ username: userData.username, role: userData.role });
    } catch {
      setUser(null);
    } finally {
      setIsInitialized(true);
    }
  };

  // Verifica sessão ao carregar a página
  useEffect(() => {
    checkSession();
  }, []);

  const login = (newToken: string) => {
    setToken(newToken);
    checkSession();
  };

  const logout = async () => {
    try {
      await fetch('/api/v1/auth/logout', { method: 'POST' });
    } finally {
      setUser(null);
      setToken(null);
    }
  };

  useEffect(() => {
    const handleAuthExpired = () => {
      setUser(null);
      setToken(null);
    };

    window.addEventListener('auth:expired', handleAuthExpired);
    return () => {
      window.removeEventListener('auth:expired', handleAuthExpired);
    };
  }, []);

  const isAuthenticated = !!user || !!token;

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
