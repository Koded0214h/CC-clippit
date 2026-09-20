import type { Metadata } from "next";
import type { ReactNode } from "react";
import { BrandShell } from "@/components/brand/BrandShell";
import "../../styles/brand.css";

export const metadata: Metadata = {
  title: "Brand workspace",
  description: "Fund creator campaigns and follow every verified view.",
};

export default function BrandLayout({ children }: { children: ReactNode }) {
  return <BrandShell>{children}</BrandShell>;
}
