import { AdminDetailScreen } from "@/components/admin/AdminScreens";
export default async function Page({ params }: { params: Promise<{ id: string }> }) { return <AdminDetailScreen kind="risk" id={(await params).id} />; }
