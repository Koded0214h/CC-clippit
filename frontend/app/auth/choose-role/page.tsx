import { Suspense } from "react";
import { GoogleRoleChoice } from "@/components/auth/GoogleRoleChoice";

export default function Page() {
  return <Suspense><GoogleRoleChoice /></Suspense>;
}
