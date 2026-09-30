import { Suspense } from "react";
import { AdminInvitationScreen } from "@/components/admin/AdminScreens";
import { ClippitLoader } from "@/components/ui/ClippitLoader";

export default function Page() {
  return <Suspense fallback={<ClippitLoader tone="ink" label="Checking invitation" note="Verifying this operator invitation." />}><AdminInvitationScreen /></Suspense>;
}
