import type { Metadata } from "next";
import { Geist, Kalam } from "next/font/google";
import type { ReactNode } from "react";
import { UserProvider } from "@/lib/user-context";
import "./globals.css";
import "../styles/product.css";
import "../styles/creator.css";
import "../styles/customer.css";
import "../styles/completion.css";

const geist = Geist({
  subsets: ["latin"],
  variable: "--font-geist",
  display: "swap",
});

const kalam = Kalam({
  subsets: ["latin"],
  weight: "700",
  variable: "--font-kalam",
  display: "swap",
});

export const metadata: Metadata = {
  metadataBase: new URL(
    process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:5174",
  ),
  title: {
    default: "Clippit — Good creators. Better paydays.",
    template: "%s | Clippit",
  },
  description:
    "Discover funded campaigns, publish on your socials, and earn naira from verified views.",
  openGraph: {
    title: "Clippit — Your next post. Your next payday.",
    description:
      "Make something worth watching. Get paid for verified views. Built for Nigerian creators.",
    type: "website",
  },
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={`${geist.variable} ${kalam.variable}`}>
      <body><UserProvider>{children}</UserProvider></body>
    </html>
  );
}
