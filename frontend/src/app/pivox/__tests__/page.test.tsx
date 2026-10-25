import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import PivoxPage from "../page";

describe("/pivox — the Instagram bio page", () => {
  it("links to all three products", () => {
    render(<PivoxPage />);
    expect(screen.getByTestId("pivox-quant").getAttribute("href")).toBe("/");
    expect(screen.getByTestId("pivox-map").getAttribute("href")).toBe("https://map.pivoxquant.com");
    expect(screen.getByTestId("pivox-data").getAttribute("href")).toBe("https://data.pivoxquant.com");
  });

  it("keeps the 투자 권유 아님 line under the Quant link", () => {
    render(<PivoxPage />);
    expect(screen.getByText("관측 자료이며 투자 권유가 아닙니다.")).toBeTruthy();
  });
});
