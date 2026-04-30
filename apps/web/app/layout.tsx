import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { Toaster } from "sonner";

import { Providers } from "@/components/providers";

import "./globals.css";

// Nonce-based CSP requires dynamic rendering — Next.js applies nonces during
// SSR based on the per-request CSP header set in middleware.ts. Static
// pre-rendering would emit `<script>` tags without nonces and the browser
// would block hydration.
export const dynamic = "force-dynamic";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "MongoRAG",
  description: "AI chatbot platform powered by RAG",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <Providers>
          {children}
        </Providers>
        <Toaster />
      </body>
    </html>
  );
}
