import type { Metadata } from "next";
import type { ReactNode } from "react";
import { AdminShell } from "@/components/admin/AdminShell";
import "../../styles/admin.css";

export const metadata: Metadata = { title: "Operations", description: "Clippit administration and operations workspace." };

export default function Layout({ children }: { children: ReactNode }) { return <AdminShell>{children}</AdminShell>; }
