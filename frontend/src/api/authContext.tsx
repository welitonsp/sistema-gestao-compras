import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { apiClient } from './client';

interface AuthUser {
  username: string;
  role: string;
  department_id: string | null;
}

interface AuthContextType {
  user: AuthUser | null;
  login: () => Promise<void>;
  logout: () => Promise<void>;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isInitialized, setIsInitialized] = useState(false);

  const checkSession = async (): Promise<AuthUser | null> => {
    try {
      const userData = await apiClient.get<AuthUser>('/users/me');
      const authenticatedUser = {
        username: userData.username,
        role: userData.role,
        department_id: userData.department_id,
      };
      setUser(authenticatedUser);
      return authenticatedUser;
    } catch {
      setUser(null);
      return null;
    } finally {
      setIsInitialized(true);
    }
  };

  // Verifica sessão ao carregar a página
  useEffect(() => {
    checkSession();
  }, []);

  const login = async () => {
    const authenticatedUser = await checkSession();
    if (!authenticatedUser) {
      throw new Error('Não foi possível carregar o perfil do usuário.');
    }
  };

  const logout = async () => {
    try {
      await fetch('/api/v1/auth/logout', {
        method: 'POST',
        credentials: 'include',
      });
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
    <AuthContext.Provider value={{ user, login, logout, isAuthenticated }}>
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
