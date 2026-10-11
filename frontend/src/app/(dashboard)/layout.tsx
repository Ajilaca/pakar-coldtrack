import { ReactNode } from "react";
import { Sidebar } from "@/components/fleet/sidebar";
import { Toaster } from "@/components/fleet/notifications";
import { FleetProvider } from "@/lib/use-fleet";

export default function DashboardLayout({ children }: { children: ReactNode }) {
  return (
    <FleetProvider>
      <div className="flex min-h-dvh flex-col bg-page lg:flex-row">
        <Sidebar />
        <main className="mx-auto flex w-full min-w-0 max-w-[1280px] flex-1 flex-col gap-5 px-4 py-5 lg:px-8 lg:py-7">
          {children}
          <footer className="mt-auto pt-4 text-[12px] text-muted">
            Alat bantu keputusan, bukan pengganti penilaian operator. Nilai rupiah adalah estimasi dari harga per kg [ASUMSI].
          </footer>
        </main>
      </div>
      <Toaster />
    </FleetProvider>
  );
}
