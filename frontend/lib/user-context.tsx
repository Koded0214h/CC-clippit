"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { useRouter } from "next/navigation";
import { authApi, clearTokens, getAccessToken, type UserOut } from "@/lib/api/auth";
import { ApiError } from "@/lib/api/client";

interface UserContextValue {
  user: UserOut | null;
  isLoading: boolean;
  logout: () => Promise<void>;
}

const UserContext = createContext<UserContextValue>({
  user: null,
  isLoading: true,
  logout: async () => {},
});

export function UserProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<UserOut | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const token = getAccessToken();
    if (!token) {
      setIsLoading(false);
      return;
    }
    authApi
      .me()
      .then(setUser)
      .catch((err) => {
        // Token is expired or invalid — clear it so AuthGuard redirects.
        if (err instanceof ApiError && err.status === 401) {
          clearTokens();
        }
      })
      .finally(() => setIsLoading(false));
  }, []);

  const logout = async () => {
    try {
      await authApi.logout();
    } catch {
      // best-effort — we clear locally regardless
    }
    clearTokens();
    setUser(null);
    router.push("/auth/sign-in");
  };

  return (
    <UserContext.Provider value={{ user, isLoading, logout }}>
      {children}
    </UserContext.Provider>
  );
}

export function useUser() {
  return useContext(UserContext);
}
