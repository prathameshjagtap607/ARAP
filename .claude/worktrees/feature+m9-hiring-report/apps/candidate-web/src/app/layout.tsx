import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ARAP — Candidate Assessment",
  description: "AI Recruitment Assessment Platform — Candidate Portal",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-white text-slate-900 antialiased">
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4
                     focus:z-50 focus:rounded focus:bg-white focus:px-4 focus:py-2
                     focus:text-slate-900 focus:shadow-lg focus:outline focus:outline-2
                     focus:outline-slate-900"
        >
          Skip to main content
        </a>
        {children}
      </body>
    </html>
  );
}
