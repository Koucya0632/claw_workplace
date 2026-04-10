import { inspectWorkflowPayload, summarizeWorkflowRuntimeIssue } from "@/lib/workflow-payloads";


describe("workflow payload parsing", () => {
  it("parses development structured payloads into readable summaries", () => {
    const payload = {
      summary: "已完成 sources page 的主骨架與管理操作。",
      completed_items: ["新增 KPI 摘要卡", "補齊來源管理表格"],
      changed_modules: ["web/app/settings/sources/page.tsx", "api/app/routers/sources.py"],
      notable_decisions: ["維持單頁管理，不另拆 detail page"],
    };

    const parsed = inspectWorkflowPayload(payload);

    expect(parsed?.kind).toBe("development_structured");
    expect(parsed?.summary).toBe("已完成 sources page 的主骨架與管理操作。");
    expect(parsed?.highlights).toContain("新增 KPI 摘要卡");
    expect(parsed?.artifacts).toContain("web/app/settings/sources/page.tsx");
    expect(summarizeWorkflowRuntimeIssue(payload)).toContain("已完成 sources page 的主骨架與管理操作。");
  });

  it("recovers readable summary and highlights from missing-text detail strings", () => {
    const detail =
      "summary=已完成 sources page 的主骨架與管理操作。 / completed=新增 KPI 摘要卡；補齊來源管理表格 / modules=web/app/settings/sources/page.tsx；api/app/routers/sources.py / provider=minimax / model=MiniMax-M2.7 / text_fields=none";

    const parsed = inspectWorkflowPayload({ error: detail });

    expect(parsed?.summary).toBe("已完成 sources page 的主骨架與管理操作。");
    expect(parsed?.highlights).toContain("新增 KPI 摘要卡");
    expect(parsed?.artifacts).toContain("web/app/settings/sources/page.tsx");
    expect(summarizeWorkflowRuntimeIssue({ error: detail }, "Fullstack Engineer Agent")).toContain(
      "已完成 sources page 的主骨架與管理操作。"
    );
  });
});
