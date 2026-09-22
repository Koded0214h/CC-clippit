import { AdminDetailScreen } from "@/components/admin/AdminScreens";
export default async function Page({ params }: { params: Promise<{ id: string }> }) { return <AdminDetailScreen kind="dispute" id={(await params).id} />; }
