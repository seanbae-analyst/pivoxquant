"use client";

/**
 * DataTable — terminal-grade sortable table.
 *
 * Headless-ish table for dense dashboards. Features:
 *   - Sort by clicking a column header (click once asc, twice desc, thrice off).
 *   - Sticky header (optional, default true).
 *   - Keyboard navigation: J/K moves row focus, Enter drills in via onRowClick.
 *   - Inline edit (optional) via onEdit(rowId, colKey, newValue).
 *   - Virtual scroll is deferred to Phase 2.
 *
 * Generic over a Row type that must have an `id: string | number` field.
 *
 * Visual: #0B0E14 bg, #1A1F2E hairline rules, bronze active-row cue.
 */

import React, { useCallback, useMemo, useRef, useState } from "react";

export type CellValue = string | number | null | undefined;

export interface Column<R> {
  key: string;
  header: string;
  /** Cell render — defaults to String(row[key]). */
  render?: (row: R) => React.ReactNode;
  /** Value accessor for sorting. Defaults to row[key]. */
  sortAccessor?: (row: R) => number | string | null | undefined;
  /** If true, header click sorts by this column. Default true. */
  sortable?: boolean;
  /** Flex basis / explicit width. e.g. "120px" or "20%". */
  width?: string;
  align?: "left" | "right" | "center";
  /** When set, the cell becomes inline-editable via onEdit. */
  editable?: boolean;
}

export interface DataTableProps<R extends { id: string | number }> {
  columns: Column<R>[];
  rows: R[];
  onRowClick?: (row: R) => void;
  onEdit?: (rowId: R["id"], colKey: string, value: string) => void;
  stickyHeader?: boolean;
  /** aria label for the table. */
  label?: string;
  /** Empty state content. */
  emptyState?: React.ReactNode;
  className?: string;
  /** Default sort on mount. */
  initialSort?: { key: string; dir: "asc" | "desc" };
}

type SortState = { key: string; dir: "asc" | "desc" } | null;

function compare(a: unknown, b: unknown): number {
  if (a == null && b == null) return 0;
  if (a == null) return 1;
  if (b == null) return -1;
  if (typeof a === "number" && typeof b === "number") return a - b;
  return String(a).localeCompare(String(b));
}

export function DataTable<R extends { id: string | number }>({
  columns,
  rows,
  onRowClick,
  onEdit,
  stickyHeader = true,
  label,
  emptyState,
  className = "",
  initialSort,
}: DataTableProps<R>) {
  const [sort, setSort] = useState<SortState>(initialSort ?? null);
  const [focusIdx, setFocusIdx] = useState<number>(-1);
  const [editing, setEditing] = useState<
    { id: R["id"]; key: string } | null
  >(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const sortedRows = useMemo(() => {
    if (!sort) return rows;
    const col = columns.find((c) => c.key === sort.key);
    if (!col) return rows;
    const accessor =
      col.sortAccessor ??
      ((r: R) => (r as unknown as Record<string, unknown>)[sort.key] as CellValue);
    const copy = [...rows];
    copy.sort((a, b) => {
      const va = accessor(a);
      const vb = accessor(b);
      const d = compare(va, vb);
      return sort.dir === "asc" ? d : -d;
    });
    return copy;
  }, [rows, sort, columns]);

  const cycleSort = useCallback((key: string) => {
    setSort((cur) => {
      if (!cur || cur.key !== key) return { key, dir: "asc" };
      if (cur.dir === "asc") return { key, dir: "desc" };
      return null;
    });
  }, []);

  // Keyboard navigation — J/K + Enter
  const onKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLDivElement>) => {
      if (editing) return;
      if (e.key === "j" || e.key === "ArrowDown") {
        e.preventDefault();
        setFocusIdx((i) => Math.min(sortedRows.length - 1, Math.max(i, -1) + 1));
      } else if (e.key === "k" || e.key === "ArrowUp") {
        e.preventDefault();
        setFocusIdx((i) => Math.max(0, i - 1));
      } else if (e.key === "Enter" && focusIdx >= 0 && onRowClick) {
        const row = sortedRows[focusIdx];
        if (row) onRowClick(row);
      }
    },
    [editing, focusIdx, onRowClick, sortedRows],
  );

  // Reset focus when rows shrink beneath it. Doing this during render avoids
  // queuing a redundant render via setState-in-effect.
  if (sortedRows.length > 0 && focusIdx >= sortedRows.length) {
    setFocusIdx(sortedRows.length - 1);
  }

  const rowCount = sortedRows.length;

  return (
    <div
      ref={containerRef}
      tabIndex={0}
      role="grid"
      aria-label={label}
      onKeyDown={onKeyDown}
      className={`pq-data-table font-mono ${className}`.trim()}
      style={{
        background: "#0B0E14",
        border: "1px solid #1A1F2E",
        overflow: "auto",
        outline: "none",
      }}
    >
      <table
        style={{
          width: "100%",
          borderCollapse: "collapse",
          fontSize: 11.5,
          color: "rgba(245,240,232,0.92)",
        }}
      >
        <thead
          style={
            stickyHeader
              ? {
                  position: "sticky",
                  top: 0,
                  background: "#0B0E14",
                  zIndex: 1,
                }
              : undefined
          }
        >
          <tr
            style={{
              borderBottom: "1px solid #1A1F2E",
            }}
          >
            {columns.map((c) => {
              const active = sort?.key === c.key;
              const sortable = c.sortable !== false;
              return (
                <th
                  key={c.key}
                  scope="col"
                  onClick={sortable ? () => cycleSort(c.key) : undefined}
                  style={{
                    textAlign: c.align ?? "left",
                    padding: "8px 12px",
                    fontWeight: 500,
                    fontSize: 9.5,
                    letterSpacing: "0.2em",
                    textTransform: "uppercase",
                    color: active
                      ? "var(--pq-bronze, #B8956A)"
                      : "rgba(245,240,232,0.55)",
                    cursor: sortable ? "pointer" : "default",
                    userSelect: "none",
                    width: c.width,
                    whiteSpace: "nowrap",
                    borderRight: "1px solid #1A1F2E",
                  }}
                  aria-sort={
                    active
                      ? sort!.dir === "asc"
                        ? "ascending"
                        : "descending"
                      : "none"
                  }
                >
                  <span>
                    {c.header}
                    {active && (
                      <span
                        style={{ marginLeft: 6, opacity: 0.85 }}
                        aria-hidden
                      >
                        {sort!.dir === "asc" ? "▲" : "▼"}
                      </span>
                    )}
                  </span>
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {rowCount === 0 ? (
            <tr>
              <td
                colSpan={columns.length}
                style={{
                  padding: 24,
                  textAlign: "center",
                  color: "rgba(245,240,232,0.45)",
                  fontSize: 11.5,
                }}
              >
                {emptyState ?? "No rows."}
              </td>
            </tr>
          ) : (
            sortedRows.map((row, rIdx) => {
              const focused = rIdx === focusIdx;
              return (
                <tr
                  key={String(row.id)}
                  onClick={() => {
                    setFocusIdx(rIdx);
                    onRowClick?.(row);
                  }}
                  style={{
                    cursor: onRowClick ? "pointer" : "default",
                    background: focused
                      ? "rgba(184,149,106,0.05)"
                      : "transparent",
                    borderBottom: "1px solid rgba(26,31,46,0.55)",
                    boxShadow: focused
                      ? "inset 2px 0 0 var(--pq-bronze, #B8956A)"
                      : "none",
                    transition: "background-color 0.15s ease",
                  }}
                  onMouseEnter={() => setFocusIdx(rIdx)}
                >
                  {columns.map((c) => {
                    const cellRaw = (row as unknown as Record<string, unknown>)[
                      c.key
                    ];
                    const display = c.render
                      ? c.render(row)
                      : cellRaw == null
                        ? "—"
                        : String(cellRaw);
                    const isEditing =
                      editing?.id === row.id && editing?.key === c.key;

                    return (
                      <td
                        key={c.key}
                        onDoubleClick={(e) => {
                          if (c.editable && onEdit) {
                            e.stopPropagation();
                            setEditing({ id: row.id, key: c.key });
                          }
                        }}
                        style={{
                          textAlign: c.align ?? "left",
                          padding: "9px 12px",
                          whiteSpace: "nowrap",
                          borderRight: "1px solid rgba(26,31,46,0.45)",
                        }}
                      >
                        {isEditing ? (
                          <input
                            autoFocus
                            defaultValue={cellRaw == null ? "" : String(cellRaw)}
                            onBlur={(e) => {
                              onEdit?.(row.id, c.key, e.target.value);
                              setEditing(null);
                            }}
                            onKeyDown={(e) => {
                              if (e.key === "Enter") {
                                onEdit?.(
                                  row.id,
                                  c.key,
                                  (e.target as HTMLInputElement).value,
                                );
                                setEditing(null);
                              } else if (e.key === "Escape") {
                                setEditing(null);
                              }
                            }}
                            style={{
                              width: "100%",
                              background: "#0A0D13",
                              border: "1px solid var(--pq-bronze, #B8956A)",
                              color: "rgba(245,240,232,0.98)",
                              fontFamily: "inherit",
                              fontSize: 11.5,
                              padding: "3px 6px",
                              outline: "none",
                            }}
                          />
                        ) : (
                          display
                        )}
                      </td>
                    );
                  })}
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}

export default DataTable;
