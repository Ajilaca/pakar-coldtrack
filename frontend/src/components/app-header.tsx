import { Icon } from "@/components/icon";

/**
 * Header — elemen 1 dari "Anatomi satu halaman":
 * nama produk, satu kalimat positioning, badge mode demo.
 */
export function AppHeader({ usingMock }: { usingMock: boolean }) {
  return (
    <header className="glass-strong flex flex-wrap items-center justify-between gap-3 rounded-2xl px-4 py-3">
      <div className="flex items-center gap-3">
        <div className="grad-brand flex size-10 shrink-0 items-center justify-center rounded-xl">
          <Icon name="logo" size={22} tone="white" />
        </div>
        <div>
          <h1 className="t-panel-title">ColdTrack AI</h1>
          <p className="t-meta">
            Mengubah telemetri rantai dingin jadi keputusan: berapa menit lagi muatan aman, dan apa yang harus dilakukan.
          </p>
        </div>
      </div>

      <div className="flex items-center gap-2">
        {/* Pengungkapan jujur — parameter model statis selama demo. */}
        <span className="inline-flex items-center gap-1.5 rounded-full bg-amberwarn-soft px-2.5 py-1 t-pill text-amberwarn">
          <span className="size-1.5 rounded-full bg-amberwarn" />
          Mode Demo — parameter statis
        </span>
        {usingMock && (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-secondary px-2.5 py-1 t-pill text-muted-foreground">
            Data tiruan
          </span>
        )}
      </div>
    </header>
  );
}
