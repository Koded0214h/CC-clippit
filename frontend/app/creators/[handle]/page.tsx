import { PublicCreatorProfileScreen } from "@/components/completion/CustomerCompletionScreens";

export default async function Page({ params }: { params: Promise<{ handle: string }> }) {
  return <PublicCreatorProfileScreen handle={(await params).handle} />;
}
