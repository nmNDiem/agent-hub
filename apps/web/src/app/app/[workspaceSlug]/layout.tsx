import { WorkspaceSystemBoundary } from "@/components/workspace-system-boundary";

export default async function WorkspaceLayout({ children, params }: Readonly<{
  children: React.ReactNode;
  params: Promise<{ workspaceSlug: string }>;
}>) {
  const { workspaceSlug } = await params;
  return <WorkspaceSystemBoundary workspaceSlug={workspaceSlug}>{children}</WorkspaceSystemBoundary>;
}
