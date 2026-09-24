const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "https://clippit-5b5j.onrender.com";

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(detail);
    this.name = "ApiError";
  }
}




async function request<T>(path: string, init: RequestInit = {}, isRetry = false): Promise<T> {
  const token =
    typeof window !== "undefined"
      ? localStorage.getItem("clippit:access-token")
      : null;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init.headers as Record<string, string> | undefined),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_URL}${path}`, { ...init, headers });

  if (!res.ok) {
    if (
      res.status === 401 &&
      !isRetry &&
      path !== "/auth/refresh" &&
      path !== "/auth/login"
    ) {
      const refreshToken =
        typeof window !== "undefined"
          ? localStorage.getItem("clippit:refresh-token")
          : null;
      if (refreshToken) {
        try {
          const refreshRes = await fetch(`${API_URL}/auth/refresh`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ refresh_token: refreshToken }),
          });
          if (refreshRes.ok) {
            const data = await refreshRes.json();
            localStorage.setItem("clippit:access-token", data.access_token);
            if (data.refresh_token)
              localStorage.setItem("clippit:refresh-token", data.refresh_token);
            return request<T>(path, init, true);
          }
        } catch {
          // refresh failed, fall through
        }
      }
      if (typeof window !== "undefined") {
        localStorage.removeItem("clippit:access-token");
        localStorage.removeItem("clippit:refresh-token");
        window.location.href = "/auth/sign-in";
      }
      throw new ApiError(401, "Session expired");
    }

    let detail = res.statusText;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      // keep statusText
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "POST", body: JSON.stringify(body) }),
  put: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "PUT", body: JSON.stringify(body) }),
  patch: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "PATCH", body: JSON.stringify(body) }),
  delete: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: "DELETE",
      ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
    }),
};
