import type { Metadata } from "next";
import { Fraunces, Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const fraunces = Fraunces({
  variable: "--font-fraunces",
  subsets: ["latin"],
  axes: ["opsz"],
});

export const metadata: Metadata = {
  title: "The Antikythera Mechanism — A 2,000-Year-Old Computer",
  description:
    "An overview of the Antikythera Mechanism: its discovery, inner workings, and lasting significance.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} ${fraunces.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        {children}
        <script
          src="/widget.js"
          data-api-key="mrag_zsdCxsKkTNuqSn0-DdsNeH6rk28rjnDCZNlT2b1woDrxIJsa"
          data-bot-id="69f613da2ad73cc3eb1bb748"
          data-api-url="http://localhost:8100"
          defer
        />
      </body>
    </html>
  );
}
