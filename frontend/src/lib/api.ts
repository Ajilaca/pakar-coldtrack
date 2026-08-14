import { AnalyzeRequest, AnalyzeResponse } from "./types";
import { mockAnalyze } from "./mock";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// Default true supaya frontend tidak pernah "menunggu tanpa kerjaan" (lihat role-context R4).
// Set NEXT_PUBLIC_USE_MOCK=false di .env.local begitu endpoint asli R3 siap.
const USE_MOCK = process.env.NEXT_PUBLIC_USE_MOCK !== "false";

export class AnalyzeError extends Error {}

export async function analyzeShipment(
  payload: AnalyzeRequest,
  scenarioId?: string
): Promise<AnalyzeResponse> {
  if (USE_MOCK) {
    return mockAnalyze(payload, scenarioId);
  }

  let res: Response;
  try {
    res = await fetch(`${API_URL}/api/v1/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch {
    throw new AnalyzeError("Tidak bisa menghubungi server analisis. Periksa koneksi atau status backend.");
  }

  if (!res.ok) {
    throw new AnalyzeError(`Server mengembalikan error (${res.status}). Coba lagi sebentar.`);
  }

  return res.json();
}