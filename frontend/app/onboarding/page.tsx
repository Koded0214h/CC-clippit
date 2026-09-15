import { redirect } from "next/navigation";

export default async function Page({ searchParams }: { searchParams: Promise<{ role?: string }> }) {
  const query = await searchParams;
  redirect(query.role === "organisation" ? "/onboarding/brand" : "/onboarding/creator");
}
