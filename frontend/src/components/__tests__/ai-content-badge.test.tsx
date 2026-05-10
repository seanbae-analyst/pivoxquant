import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

import {
  AiContentBadge,
  AI_CONTENT_LABEL_KO,
  AI_CONTENT_LABEL_EN,
} from "@/components/ui/ai-content-badge";

describe("<AiContentBadge /> — Regulatory ③ (2026-01)", () => {
  it("renders the mandatory KR + EN AI-content disclosure", () => {
    render(<AiContentBadge />);
    expect(screen.getByText(AI_CONTENT_LABEL_KO)).toBeInTheDocument();
    expect(screen.getByText(AI_CONTENT_LABEL_EN)).toBeInTheDocument();
  });

  it("exports the verbatim KR/EN label strings", () => {
    expect(AI_CONTENT_LABEL_KO).toBe("AI 생성 콘텐츠 (참고용)");
    expect(AI_CONTENT_LABEL_EN).toBe("AI-generated content (informational)");
  });

  it("exposes a data attribute regression tests can grep on", () => {
    const { container } = render(<AiContentBadge />);
    const node = container.querySelector('[data-ai-content-label="true"]');
    expect(node).not.toBeNull();
  });

  it("supports framed and inline variants without crashing", () => {
    const inline = render(<AiContentBadge variant="inline" />);
    expect(
      inline.getByLabelText("AI-generated content disclosure"),
    ).toBeInTheDocument();
    inline.unmount();

    const framed = render(<AiContentBadge variant="framed" />);
    expect(
      framed.getByLabelText("AI-generated content disclosure"),
    ).toBeInTheDocument();
  });
});
