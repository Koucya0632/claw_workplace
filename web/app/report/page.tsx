"use client";

import { Suspense, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";


function ReportRedirectContent() {
  // 報告頁改成 workflow run 的入口代理，避免和新版 /search 的主流程頁分裂。
  const router = useRouter();
  const searchParams = useSearchParams();
  const runId = searchParams.get("runId");

  useEffect(() => {
    router.replace(runId ? `/search?runId=${runId}` : "/search");
  }, [router, runId]);

  return <div className="status-strip rounded-[1.25rem] p-6 text-sm text-slate-600">正在導向工作流報告視圖...</div>;
}

export default function ReportPage() {
  return (
    <Suspense fallback={<div className="status-strip rounded-[1.25rem] p-6 text-sm text-slate-600">正在載入報告頁...</div>}>
      <ReportRedirectContent />
    </Suspense>
  );
}
