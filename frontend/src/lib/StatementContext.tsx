import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import { api, StatementItem } from "./api";

interface StatementContextType {
  statements: StatementItem[];
  currentId: number | null;
  currentStatement: StatementItem | null;
  loading: boolean;
  setCurrentId: (id: number | null) => void;
  refreshStatements: () => Promise<StatementItem[]>;
  deleteStatement: (id: number) => Promise<void>;
  purgeAll: () => Promise<void>;
}

const StatementContext = createContext<StatementContextType | undefined>(undefined);

const STORAGE_KEY = "muleguard_active_statement_id";

export function StatementProvider({ children }: { children: React.ReactNode }) {
  const [statements, setStatements] = useState<StatementItem[]>([]);
  const [currentId, setCurrentIdState] = useState<number | null>(() => {
    const saved = localStorage.getItem(STORAGE_KEY);
    return saved ? Number(saved) : null;
  });
  const [loading, setLoading] = useState(true);

  const refreshStatements = useCallback(async () => {
    try {
      setLoading(true);
      const list = await api.listStatements();
      setStatements(list);
      
      // If currentId is not set or not in list, auto-select the latest statement
      setCurrentIdState((prevId) => {
        if (list.length === 0) {
          localStorage.removeItem(STORAGE_KEY);
          return null;
        }
        if (prevId && list.some((s) => s.id === prevId)) {
          return prevId;
        }
        const latestId = list[0]?.id;
        if (latestId != null) {
          localStorage.setItem(STORAGE_KEY, String(latestId));
          return latestId;
        }
        return null;
      });

      return list;
    } catch (e) {
      console.error("Failed to load statements", e);
      return [];
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshStatements();
  }, [refreshStatements]);

  const setCurrentId = useCallback((id: number | null) => {
    setCurrentIdState(id);
    if (id != null) {
      localStorage.setItem(STORAGE_KEY, String(id));
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  }, []);

  const deleteStatement = useCallback(async (id: number) => {
    await api.deleteStatement(id);
    await refreshStatements();
  }, [refreshStatements]);

  const purgeAll = useCallback(async () => {
    await api.purgeAll();
    setCurrentId(null);
    await refreshStatements();
  }, [refreshStatements, setCurrentId]);

  const currentStatement = statements.find((s) => s.id === currentId) || null;

  return (
    <StatementContext.Provider
      value={{
        statements,
        currentId,
        currentStatement,
        loading,
        setCurrentId,
        refreshStatements,
        deleteStatement,
        purgeAll,
      }}
    >
      {children}
    </StatementContext.Provider>
  );
}

export function useStatement() {
  const context = useContext(StatementContext);
  if (!context) {
    throw new Error("useStatement must be used within a StatementProvider");
  }
  return context;
}
