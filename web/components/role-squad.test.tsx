import React from "react";

import { render, screen } from "@testing-library/react";

import { RoleSquad } from "@/components/role-squad";


describe("RoleSquad", () => {
  it("renders role names without long quote copy", () => {
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
    expect(screen.getByText("任務調度")).toBeInTheDocument();
    expect(screen.queryByText("我會安排任務流程。")).not.toBeInTheDocument();
  });
});
