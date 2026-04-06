"use client";

import { Suspense, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";


function AnalysisRedirectContent() {
  // 分析頁不再是獨立主流程，第一版直接導回 /search 的指定 workflow run 視圖。
  const router = useRouter();
  const searchParams = useSearchParams();
  const runId = searchParams.get("runId");

  useEffect(() => {
    router.replace(runId ? `/search?runId=${runId}` : "/search");
  }, [router, runId]);

  return <div className="pixel-panel rounded-none p-6 text-sm text-slate-600">正在導向一體化工作流頁面...</div>;
}

export default function AnalysisPage() {
  return (
    <Suspense fallback={<div className="pixel-panel rounded-none p-6 text-sm text-slate-600">正在載入分析頁...</div>}>
      <AnalysisRedirectContent />
    </Suspense>
  );
}
