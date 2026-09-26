import Image from "next/image";

export function AppHeader({ model }: { model?: string }) {
  return (
    <header className="flex items-center justify-between gap-3 px-4 pt-4 lg:px-6">
      <div className="flex items-center gap-3">
        <Image src="/logo.webp" alt="" width={64} height={33} priority className="h-9 w-auto" />
        <div>
          <h1 className="text-[24px] font-extrabold leading-none tracking-[-0.03em] text-brand-strong">
            Cold<span className="italic text-accent">Track</span>
          </h1>
          <p className="mt-1 hidden text-[12px] text-muted sm:block">
            Berapa menit lagi muatan aman, dan apa yang harus dilakukan sekarang.
          </p>
        </div>
      </div>
      {model && (
        <span className="hidden items-center gap-2 rounded-full border bg-surface px-3 py-1.5 text-[12px] font-medium text-muted md:flex">
          <span className="size-2 rounded-full bg-ok" aria-hidden />
          Model aktif · <span className="num">{model}</span>
        </span>
      )}
    </header>
  );
}
