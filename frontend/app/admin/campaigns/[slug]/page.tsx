import { AdminDetailScreen } from "@/components/admin/AdminScreens";
export default async function Page({ params }: { params: Promise<{ slug: string }> }) { return <AdminDetailScreen kind="campaign" id={(await params).slug} />; }
