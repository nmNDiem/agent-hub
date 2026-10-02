import { redirect } from "next/navigation";

export default async function Page({
  params,
}: {
  params: Promise<{ workspaceSlug: string; publicAgentId: string }>;
}) {
  const { workspaceSlug, publicAgentId } = await params;
  redirect(`/app/${encodeURIComponent(workspaceSlug)}/chatbots?agent=${encodeURIComponent(publicAgentId)}`);
}
