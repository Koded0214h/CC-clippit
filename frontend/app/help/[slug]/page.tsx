import { ProductionHelpArticleScreen } from "@/components/completion/CustomerCompletionScreens";

export default async function Page({ params }: { params: Promise<{ slug: string }> }) {
  return <ProductionHelpArticleScreen slug={(await params).slug} />;
}
