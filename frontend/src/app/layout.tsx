import type { Metadata } from "next";
import NavBar from "@/components/NavBar";
import "./globals.css";

export const metadata: Metadata = {
  title: "COSMIN Checker",
  description: "AI-assisted COSMIN Risk of Bias assessment platform",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-surface-0 text-text-primary">
        <NavBar />
        <main className="relative">{children}</main>
      </body>
    </html>
  );
}
