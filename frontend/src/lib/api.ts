import { AnalyzeRequest, AnalyzeResponse } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {}

export async function analyzeShipment(payload: AnalyzeRequest, signal?: AbortSignal): Promise<AnalyzeResponse> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}/api/v1/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal,
    });
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") throw e;
    throw new ApiError(`Server analisis tidak bisa dihubungi (${API_URL}). Pastikan backend berjalan.`);
  }

  if (res.status === 400 || res.status === 422) {
    let detail = "";
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") detail = ` ${body.detail}`;
    } catch {}
    throw new ApiError(`Data ditolak server (${res.status}).${detail}`);
  }
  if (!res.ok) throw new ApiError(`Server mengembalikan error (${res.status}).`);
  return res.json();
}
