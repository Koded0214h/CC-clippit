import { redirect } from "next/navigation";

export default async function Page({
  searchParams,
}: {
  searchParams: Promise<{ role?: string }>;
}) {
  const { role } = await searchParams;
  redirect(
    role === "organisation"
      ? "/auth/sign-up/organisation"
      : "/auth/sign-up/creator",
  );
}
