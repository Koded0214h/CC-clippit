"use client";

import {
  createContext,
  useEffect,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { AccountRole, CompletionKind } from "@/lib/auth";

interface AuthFlowState {
  email: string;
  role: AccountRole;
  completion: CompletionKind;
  setEmail: (email: string) => void;
  setRole: (role: AccountRole) => void;
  setCompletion: (completion: CompletionKind) => void;
}

const AuthFlowContext = createContext<AuthFlowState | null>(null);

export function AuthFlowProvider({ children }: { children: ReactNode }) {
  const [email, setEmail] = useState("");
  const [role, setRoleState] = useState<AccountRole>("creator");
  const [completion, setCompletion] = useState<CompletionKind>("signup");

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      const stored = window.localStorage.getItem("clippit:account-role");
      if (stored === "creator" || stored === "organisation") setRoleState(stored);
    });
    return () => window.cancelAnimationFrame(frame);
  }, []);

  const setRole = (nextRole: AccountRole) => {
    setRoleState(nextRole);
    window.localStorage.setItem("clippit:account-role", nextRole);
  };
  const value = useMemo(
    () => ({ email, role, completion, setEmail, setRole, setCompletion }),
    [email, role, completion],
  );
  return (
    <AuthFlowContext.Provider value={value}>
      {children}
    </AuthFlowContext.Provider>
  );
}

export function useAuthFlow() {
  const context = useContext(AuthFlowContext);
  if (!context)
    throw new Error("useAuthFlow must be used inside AuthFlowProvider");
  return context;
}
