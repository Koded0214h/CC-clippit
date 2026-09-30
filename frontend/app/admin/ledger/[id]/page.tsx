import { AdminDetailScreen } from "@/components/admin/AdminScreens";
export default async function Page({ params }: { params: Promise<{ id: string }> }) { return <AdminDetailScreen kind="ledger" id={(await params).id} />; }
