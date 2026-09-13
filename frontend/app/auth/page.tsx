import { redirect } from "next/navigation";
export default function AuthIndex() {
  redirect("/auth/sign-up");
}
