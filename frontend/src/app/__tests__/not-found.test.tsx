import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

import NotFound from "@/app/not-found";

describe("NotFound page (404)", () => {
  it("renders the 404 eyebrow and headline", () => {
    render(<NotFound />);

    expect(screen.getByText(/Error 404/i)).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
  });

  it("renders a 'Back to desk' link pointing at /", () => {
    render(<NotFound />);

    // Match the Link by its accessible name (icon + text).
    const back = screen.getByRole("link", { name: /Back to desk/i });
    expect(back).toBeInTheDocument();
    expect(back).toHaveAttribute("href", "/");
  });
});
