import type { User, Research, CreateResearchRequest } from "@/types";

const BASE = "/api";

async function request<T>(url: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(BASE + url, {
    credentials: "include",
    ...opts,
    headers: {
      "Content-Type": "application/json",
      ...(opts?.headers || {}),
    },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.error || `Request failed: ${res.status}`);
  }
  return res.json();
}

// Auth
export const authApi = {
  register: (username: string, email: string, password: string) =>
    request<User>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ username, email, password }),
    }),
  login: (email: string, password: string) =>
    request<User>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  logout: () => request<{ message: string }>("/auth/logout", { method: "POST" }),
  me: () => request<User>("/auth/me"),
};

// Research
export const researchApi = {
  create: (data: CreateResearchRequest) =>
    request<Research>("/research/", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  list: () => request<Research[]>("/research/"),
  get: (id: string) => request<Research>(`/research/${id}`),
  remove: (id: string) =>
    request<{ message: string }>(`/research/${id}`, { method: "DELETE" }),
  pdfUrl: (id: string) => `${BASE}/research/${id}/pdf`,
  texUrl: (id: string) => `${BASE}/research/${id}/tex`,
};
