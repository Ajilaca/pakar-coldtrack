import type { Metadata } from "next";
import "@fontsource-variable/inter";
import "./globals.css";

export const metadata: Metadata = {
  title: "ColdTrack AI",
  description: "Peringatan dini kegagalan rantai dingin berbasis AI",
  icons: { icon: "/logo.webp" },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="id">
      <body className="min-h-dvh antialiased">{children}</body>
    </html>
  );
}
