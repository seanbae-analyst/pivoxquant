/**
 * Endpoint contract gate — `API.observationNotes.*`.
 *
 * `endpoints.ts` is the frontend's 1:1 map of the backend URL space
 * (CLAUDE.md §중요 원칙: "API endpoint URL 변경 금지"). These four paths are
 * quoted verbatim from docs/design/observation-notes_2026-09-22.md §3, so a
 * silent rename on either side fails here instead of in production.
 */
import { describe, expect, it } from "vitest";
import { API } from "@/lib/endpoints";

describe("API.observationNotes paths", () => {
  it("list / create are the exact contract paths", () => {
    expect(API.observationNotes.list).toBe("/api/observation-notes/list");
    // Trailing slash is load-bearing: the blueprint registers POST on "/".
    expect(API.observationNotes.create).toBe("/api/observation-notes");
  });

  it("detail(id) addresses one note by id", () => {
    expect(API.observationNotes.detail(42)).toBe("/api/observation-notes/42");
    expect(API.observationNotes.detail("42")).toBe("/api/observation-notes/42");
  });

  it("byTicker(ticker) hits the by-ticker read used by /pre-trade", () => {
    expect(API.observationNotes.byTicker("AAPL")).toBe(
      "/api/observation-notes/by-ticker/AAPL",
    );
  });

  it("byTicker encodes a KR ticker's suffix safely", () => {
    // "005930.KS" has no reserved chars, but the encode must not mangle it.
    expect(API.observationNotes.byTicker("005930.KS")).toBe(
      "/api/observation-notes/by-ticker/005930.KS",
    );
    expect(API.observationNotes.byTicker("A/B")).toBe(
      "/api/observation-notes/by-ticker/A%2FB",
    );
  });
});
