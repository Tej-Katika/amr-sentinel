import axios from "axios";
import type { AgentResponse, Alert, Antibiogram, AuthResponse } from "../types";

const baseURL = import.meta.env.VITE_API_URL ?? "http://localhost:8080/api";

const api = axios.create({ baseURL });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("amr_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (resp) => resp,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("amr_token");
      localStorage.removeItem("amr_user");
      window.location.href = "/login";
    }
    return Promise.reject(error);
  },
);

export const auth = {
  login: (email: string, password: string) =>
    api.post<AuthResponse>("/auth/login", { email, password }).then((r) => r.data),
};

export const antibiograms = {
  current: (params: { period_months?: number; stratification?: string; organism?: string } = {}) =>
    api.get<Antibiogram>("/antibiogram", { params }).then((r) => r.data),
};

export const alerts = {
  list: (severity = "ALL", daysBack = 30) =>
    api
      .get<{ alerts: Alert[]; count: number }>("/alerts", {
        params: { severity, days_back: daysBack },
      })
      .then((r) => r.data),
};

export const agent = {
  query: (q: string) =>
    api.post<AgentResponse>("/agent/query", { query: q }).then((r) => r.data),
};

export default api;
