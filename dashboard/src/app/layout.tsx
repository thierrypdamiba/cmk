import type { Metadata } from "next";
import { Geist, Geist_Mono, Instrument_Serif } from "next/font/google";
import { AuthProvider } from "@/components/auth-provider";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const instrumentSerif = Instrument_Serif({
  variable: "--font-instrument",
  weight: "400",
  style: ["normal", "italic"],
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "CMK",
  description: "Claude Memory Kit. Persistent memory for Claude.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const hasAuth = process.env.NEXT_PUBLIC_AUTH_ENABLED === "true";

  const fontVars = `${geistSans.variable} ${geistMono.variable} ${instrumentSerif.variable} antialiased`;

  if (hasAuth) {
    return (
      <html lang="en">
        <body className={fontVars}>
          <AuthProvider>{children}</AuthProvider>
        </body>
      </html>
    );
  }

  return (
    <html lang="en">
      <body className={fontVars}>
        {children}
      </body>
    </html>
  );
}
