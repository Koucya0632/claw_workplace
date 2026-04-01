import React from "react";

import { fireEvent, render, screen } from "@testing-library/react";
import { vi } from "vitest";

import { SourceStatusBoard } from "@/components/source-status-board";


describe("SourceStatusBoard", () => {
  it("shows empty state when there are no sources", () => {
    // 空狀態是初次使用的重要畫面，這裡先確認提示文字存在。
    render(<SourceStatusBoard sources={[]} />);

    expect(screen.getByText("尚未建立本地資料源，請先在設定頁新增資料夾。")).toBeInTheDocument();
  });

  it("fires scan callback when scan button is clicked", () => {
    // 掃描按鈕需要把正確的 source id 回傳給頁面層處理。
    const onScan = vi.fn();

    render(
      <SourceStatusBoard
        sources={[
          {
            id: "src_1",
            name: "本地來源",
            type: "local",
            status: "ready",
            config: { path: "/tmp/source" },
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString()
          }
        ]}
        onScan={onScan}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "重新掃描" }));
    expect(onScan).toHaveBeenCalledWith("src_1");
  });
});
