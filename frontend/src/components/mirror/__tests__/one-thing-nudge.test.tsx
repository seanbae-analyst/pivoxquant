import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { OneThingNudge } from "@/components/mirror/one-thing-nudge";
import type { MirrorHomeResponse } from "@/lib/types";

const data = (over: Partial<MirrorHomeResponse>) =>
  ({ stage: "new", gap: [], ...over }) as MirrorHomeResponse;

describe("OneThingNudge", () => {
  it("sends a user with no fills to the import", () => {
    render(<OneThingNudge data={data({ total_fills: 0 })} />);
    expect(screen.getByRole("link").getAttribute("href")).toBe("/journal/import");
  });

  it("does not ask for fills it already has when they are outside the window", () => {
    render(<OneThingNudge data={data({ total_fills: 12 })} />);
    expect(screen.getByRole("link").getAttribute("href")).toBe("/journal#habits");
    expect(screen.getByText(/체결 12건이 기록돼 있어요/)).toBeTruthy();
  });

  it("keeps the pause as the next step once behaviour is observed", () => {
    render(<OneThingNudge data={data({ stage: "observed", total_fills: 12 })} />);
    expect(screen.getByRole("link").getAttribute("href")).toBe("/pre-trade");
  });
});
