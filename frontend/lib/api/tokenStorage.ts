export type TokenPersistence = "session" | "persistent";

const ACCESS_TOKEN_KEY = "clippit:access-token";
const REFRESH_TOKEN_KEY = "clippit:refresh-token";

type TokenPair = {
  access_token: string;
  refresh_token?: string | null;
};

function storage(kind: TokenPersistence): Storage | null {
  if (typeof window === "undefined") return null;
  try {
    return kind === "persistent" ? window.localStorage : window.sessionStorage;
  } catch {
    return null;
  }
}

function read(key: string): string | null {
  return storage("persistent")?.getItem(key) ?? storage("session")?.getItem(key) ?? null;
}

export function getAccessToken(): string | null {
  return read(ACCESS_TOKEN_KEY);
}

export function getRefreshToken(): string | null {
  return read(REFRESH_TOKEN_KEY);
}

export function getTokenPersistence(): TokenPersistence {
  return storage("persistent")?.getItem(ACCESS_TOKEN_KEY) || storage("persistent")?.getItem(REFRESH_TOKEN_KEY)
    ? "persistent"
    : "session";
}

export function clearStoredTokens() {
  for (const kind of ["persistent", "session"] as const) {
    const target = storage(kind);
    target?.removeItem(ACCESS_TOKEN_KEY);
    target?.removeItem(REFRESH_TOKEN_KEY);
  }
}

export function storeTokenPair(data: TokenPair, persistence: TokenPersistence = "persistent") {
  clearStoredTokens();
  const target = storage(persistence);
  target?.setItem(ACCESS_TOKEN_KEY, data.access_token);
  if (data.refresh_token) target?.setItem(REFRESH_TOKEN_KEY, data.refresh_token);
}

export function updateTokenPair(data: TokenPair) {
  const persistence = getTokenPersistence();
  const target = storage(persistence);
  target?.setItem(ACCESS_TOKEN_KEY, data.access_token);
  if (data.refresh_token) target?.setItem(REFRESH_TOKEN_KEY, data.refresh_token);
}

export function promoteSessionTokens(): boolean {
  const session = storage("session");
  const accessToken = session?.getItem(ACCESS_TOKEN_KEY);
  const refreshToken = session?.getItem(REFRESH_TOKEN_KEY);
  if (!accessToken) return false;

  const persistent = storage("persistent");
  persistent?.setItem(ACCESS_TOKEN_KEY, accessToken);
  if (refreshToken) persistent?.setItem(REFRESH_TOKEN_KEY, refreshToken);
  session?.removeItem(ACCESS_TOKEN_KEY);
  session?.removeItem(REFRESH_TOKEN_KEY);
  return true;
}
