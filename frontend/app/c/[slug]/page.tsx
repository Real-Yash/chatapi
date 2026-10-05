import { Suspense } from "react";
import PublicChat from "./chat";

export default function PublicChatPage({
  params,
}: {
  params: { slug: string };
}) {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-white">
          <p className="text-sm text-gray-400">Loading…</p>
        </div>
      }
    >
      <PublicChat slug={params.slug} />
    </Suspense>
  );
}
