"use client";

/**
 * StorageProofToggle — the "show, don't tell" trust artifact for one journal
 * entry. On expand it asks the backend for the caller's OWN rationale in two
 * forms — the plaintext they see, and the exact ciphertext stored in the
 * database — so the user *witnesses* the at-rest encryption instead of reading
 * a claim about it on a policy page.
 *
 * Honesty: the note_kr / note_en copy comes from the server and states the
 * current tier plainly — the key is server-held, so this defeats a DB leak but
 * is NOT "we cannot read it" (that is the end-to-end stage). We render that
 * note verbatim and never upgrade the claim.
 *
 * Fetch-on-expand (no SWR) — keeps the per-row cost zero until the user opts in,
 * and avoids adding a hook key for a rarely-opened affordance.
 *
 * v3 design: Vantablack + Bronze + mono. Ciphertext shown in a bordered mono
 * block so it reads as raw stored bytes, not prose.
 */

import { useState, useCallback } from "react";
import { Lock, ChevronDown } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { API } from "@/lib/endpoints";
import type {
  PreTradeStorageProof,
  PreTradeStorageProofResponse,
} from "@/lib/types";

export function StorageProofToggle({ reflectionId }: { reflectionId: number }) {
  const [open, setOpen] = useState(false);
  const [proof, setProof] = useState<PreTradeStorageProof | null>(null);
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);

  const toggle = useCallback(async () => {
    const next = !open;
    setOpen(next);
    if (!next || proof || loading) return;
    setLoading(true);
    setFailed(false);
    try {
      const res = await apiFetch<PreTradeStorageProofResponse>(
        API.preTrade.storageProof(reflectionId),
      );
      if (res?.ok && res.storage_proof) setProof(res.storage_proof);
      else setFailed(true);
    } catch {
      setFailed(true);
    } finally {
      setLoading(false);
    }
  }, [open, proof, loading, reflectionId]);

  return (
    <div
      className="mt-3 border-t pt-3"
      style={{ borderColor: "var(--pq-ivory-line-soft)" }}
    >
      <button
        type="button"
        onClick={() => void toggle()}
        className="flex w-full items-center gap-2 text-left"
        aria-expanded={open}
      >
        <Lock
          className="h-3 w-3 shrink-0 text-[var(--pq-bronze-light)]"
          aria-hidden="true"
        />
        <span className="font-mono text-pq-caption uppercase tracking-[0.18em] text-[var(--pq-bronze-light)]">
          저장 형태 보기 · HOW THIS IS STORED
        </span>
        <ChevronDown
          className="h-3.5 w-3.5 shrink-0 text-[var(--pq-ivory-faint)] transition-transform duration-200"
          style={{ transform: open ? "rotate(180deg)" : undefined }}
        />
      </button>

      {open && (
        <div className="mt-3 space-y-3">
          {loading && (
            <p className="font-mono text-pq-caption text-[var(--pq-ivory-faint)]">
              불러오는 중…
            </p>
          )}
          {failed && (
            <p className="font-mono text-pq-caption text-[var(--pq-ivory-faint)]">
              저장 형태를 불러올 수 없습니다.
            </p>
          )}
          {proof && (
            <>
              <ProofRow
                label="당신이 입력한 내용 · PLAINTEXT"
                value={proof.rationale_plaintext}
                serif
              />
              <ProofRow
                label={
                  proof.encrypted
                    ? `데이터베이스 저장 형태 · ${proof.cipher}`
                    : "데이터베이스 저장 형태 · 평문(레거시)"
                }
                value={proof.rationale_stored ?? ""}
                cipher={proof.encrypted}
              />
              <p
                className="font-sans text-pq-caption"
                style={{ lineHeight: 1.5, color: "var(--pq-ivory-faint)" }}
              >
                {proof.note_kr}
              </p>
            </>
          )}
        </div>
      )}
    </div>
  );
}

function ProofRow({
  label,
  value,
  serif,
  cipher,
}: {
  label: string;
  value: string;
  serif?: boolean;
  cipher?: boolean;
}) {
  return (
    <div className="space-y-1">
      <span className="font-mono text-pq-caption uppercase tracking-[0.14em] text-[rgba(245,240,232,0.4)]">
        {label}
      </span>
      <p
        className={serif ? "font-serif" : "font-mono"}
        style={{
          fontSize: cipher ? 11 : undefined,
          lineHeight: 1.5,
          color: cipher
            ? "var(--pq-bronze-light)"
            : "rgba(245,240,232,0.82)",
          wordBreak: "break-all",
          padding: cipher ? "8px 10px" : undefined,
          border: cipher ? "0.5px solid var(--pq-ivory-line)" : undefined,
          borderRadius: cipher ? 2 : undefined,
          background: cipher ? "var(--pq-ivory-line-faint)" : undefined,
        }}
      >
        {value}
      </p>
    </div>
  );
}
