import { ApiError } from "./api";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { cache: "no-store", ...init });
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") throw e;
    throw new ApiError(`Server armada tidak bisa dihubungi (${API_URL}). Pastikan backend dan database berjalan.`);
  }
  if (!res.ok) {
    let detail = "";
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") detail = `: ${body.detail}`;
    } catch {}
    throw new ApiError(`Server mengembalikan ${res.status}${detail}`);
  }
  return res.json();
}

export const fleetGet = <T>(path: string, signal?: AbortSignal) => req<T>(path, { signal });

export function patchInsiden(id: number, body: { phase?: string; assignee?: string; note?: string; actor: string }) {
  return req(`/api/v1/incidents/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export const tandaiDibaca = (id: number) => req(`/api/v1/notifications/${id}/read`, { method: "POST" });
export const tandaiSemuaDibaca = () => req(`/api/v1/notifications/read-all`, { method: "POST" });

export function trukPath(truckId: string): string {
  return `/truk/${encodeURIComponent(truckId.replace(/\s+/g, ""))}`;
}
