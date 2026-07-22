import type { Metadata } from "next";
import { Sidebar } from "@/components/Sidebar";
import { Topbar } from "@/components/Topbar";
import "./globals.css";

export const metadata: Metadata = {
  title: "ARAP Console",
  description: "AI Recruitment Assessment Platform — HR/Admin Console",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="flex min-h-screen bg-slate-50 text-slate-900 antialiased">
        <Sidebar />
        <div className="flex flex-col flex-1 min-w-0">
          <Topbar />
          <main className="flex-1 p-6 overflow-auto">{children}</main>
        </div>
      </body>
    </html>
  );
}
