import React from "react";

import { render, screen } from "@testing-library/react";

import { RoleSquad } from "@/components/role-squad";


describe("RoleSquad", () => {
  it("renders role names and quotes", () => {
    // 角色小隊是首頁與多個頁面的共用視覺核心，先驗證基本內容渲染。
    render(
      <RoleSquad
        roles={[
          {
            name: "Chief Lobster",
            tagline: "任務調度",
            status: "ready",
            quote: "我會安排任務流程。"
          }
        ]}
      />
    );

    expect(screen.getByText("Chief Lobster")).toBeInTheDocument();
    expect(screen.getByText("我會安排任務流程。")).toBeInTheDocument();
  });
});
