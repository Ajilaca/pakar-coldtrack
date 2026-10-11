"use client";

// Data armada live: satu EventSource (GET /api/v1/stream) untuk seluruh dasbor. Setiap event truk/insiden/
// notifikasi menaikkan `tick` (didebounce) sehingga hook useFleet() memuat ulang datanya. Bila SSE putus,
// jatuh ke polling 30 detik. Notifikasi waspada/kritis juga muncul sebagai toast.

import { createContext, ReactNode, useCallback, useContext, useEffect, useRef, useState } from "react";
import { API_URL, fleetGet } from "./fleet-api";
import { Notifikasi } from "./fleet-types";

const DEBOUNCE_MS = 1500;
const POLL_MS = 30_000;
const TOAST_MS = 7000;

export interface Toast {
  id: number;
  level: Notifikasi["level"];
  title: string;
  body: string | null;
  truck_id: string | null;
}

interface FleetCtx {
  tick: number;
  live: boolean;            // SSE tersambung
  now: string | null;       // jam server (simulasi di dev)
  toasts: Toast[];
  dismiss: (id: number) => void;
  refresh: () => void;
}

const Ctx = createContext<FleetCtx>({
  tick: 0, live: false, now: null, toasts: [], dismiss: () => {}, refresh: () => {},
});

export function FleetProvider({ children }: { children: ReactNode }) {
  const [tick, setTick] = useState(0);
  const [live, setLive] = useState(false);
  const [now, setNow] = useState<string | null>(null);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const bump = useCallback(() => {
    if (timer.current) return;
    timer.current = setTimeout(() => {
      timer.current = null;
      setTick((t) => t + 1);
    }, DEBOUNCE_MS);
  }, []);

  const dismiss = useCallback((id: number) => setToasts((ts) => ts.filter((t) => t.id !== id)), []);

  useEffect(() => {
    let es: EventSource | null = null;
    let poll: ReturnType<typeof setInterval> | null = null;
    const startPoll = () => {
      if (!poll) poll = setInterval(() => setTick((t) => t + 1), POLL_MS);
    };
    try {
      es = new EventSource(`${API_URL}/api/v1/stream`);
      es.addEventListener("hello", (e) => {
        setLive(true);
        if (poll) clearInterval(poll);
        poll = null;
        try {
          setNow(JSON.parse((e as MessageEvent).data).now);
        } catch {}
      });
      es.addEventListener("truck", (e) => {
        try {
          const d = JSON.parse((e as MessageEvent).data);
          if (d.ts) setNow((n) => (!n || d.ts > n ? d.ts : n));
        } catch {}
        bump();
      });
      es.addEventListener("incident", bump);
      es.addEventListener("notification", (e) => {
        bump();
        try {
          const d = JSON.parse((e as MessageEvent).data);
          if (d.level === "waspada" || d.level === "kritis") {
            setToasts((ts) => [...ts.slice(-3), { id: d.id, level: d.level, title: d.title, body: d.body ?? null, truck_id: d.truck_id }]);
            setTimeout(() => setToasts((ts) => ts.filter((t) => t.id !== d.id)), TOAST_MS);
          }
        } catch {}
      });
      es.onerror = () => {
        setLive(false);
        startPoll();             // EventSource mencoba sambung ulang sendiri; sementara itu polling
      };
    } catch {
      startPoll();
    }
    return () => {
      es?.close();
      if (poll) clearInterval(poll);
      if (timer.current) clearTimeout(timer.current);
    };
  }, [bump]);

  return (
    <Ctx.Provider value={{ tick, live, now, toasts, dismiss, refresh: () => setTick((t) => t + 1) }}>
      {children}
    </Ctx.Provider>
  );
}

export const useFleetCtx = () => useContext(Ctx);

/** GET path armada; dimuat ulang setiap ada event (tick). Data lama dipertahankan saat memuat ulang. */
export function useFleet<T>(path: string | null) {
  const { tick } = useFleetCtx();
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [own, setOwn] = useState(0);

  useEffect(() => {
    if (!path) return;
    const ctrl = new AbortController();
    setLoading(true);
    fleetGet<T>(path, ctrl.signal)
      .then((d) => {
        setData(d);
        setError(null);
      })
      .catch((e) => {
        if (e instanceof DOMException && e.name === "AbortError") return;
        setError(e instanceof Error ? e.message : "Gagal memuat data.");
      })
      .finally(() => {
        if (!ctrl.signal.aborted) setLoading(false);
      });
    return () => ctrl.abort();
  }, [path, tick, own]);

  // ganti path (mis. truk lain): jangan tampilkan data path sebelumnya
  useEffect(() => setData(null), [path]);

  return { data, error, loading, reload: () => setOwn((n) => n + 1) };
}
