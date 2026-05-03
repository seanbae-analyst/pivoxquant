/**
 * editorial-html — strict allowlist renderer for editorial headlines.
 *
 * The hero components historically used `dangerouslySetInnerHTML` to render
 * Playfair-italic accent words (`<span class="br">…</span>`) inside an
 * otherwise-prose H1. That works as long as the string is a hand-written
 * literal, but the prop is also fed by server-side editorial copy — once
 * the upstream CMS or AI pipeline produces the string, an injection in
 * that pipeline becomes a stored XSS in the dashboard.
 *
 * This helper renders the same grammar without ever calling innerHTML:
 *
 *   Allowed tokens:
 *     <br/> | <br> | <br />            → React <br />
 *     <span class="br">…</span>        → bronze italic accent
 *
 *   Everything else is rendered as plain text. React escapes string
 *   children automatically, so any `<script>`, `<img onerror=…>`, or
 *   stray attribute injected upstream becomes inert text in the DOM.
 *
 * Why not DOMPurify: avoids a new dependency for a 2-tag allowlist and
 * keeps SSR / client output identical (no DOMParser involved).
 */

import * as React from "react";

const TOKEN = /(<br\s*\/?>|<span\s+class="br">|<\/span>)/gi;

export function renderEditorialHeadline(html: string): React.ReactNode[] {
  const parts = html.split(TOKEN);
  const out: React.ReactNode[] = [];
  let inAccent = false;
  let accentBuffer: string[] = [];

  parts.forEach((chunk, idx) => {
    if (!chunk) return;
    const lower = chunk.toLowerCase();

    if (lower === "<br>" || lower === "<br/>" || lower === "<br />") {
      out.push(<br key={`br-${idx}`} />);
      return;
    }
    if (lower === '<span class="br">') {
      inAccent = true;
      accentBuffer = [];
      return;
    }
    if (lower === "</span>") {
      if (inAccent) {
        out.push(
          <span className="br" key={`br-span-${idx}`}>
            {accentBuffer.join("")}
          </span>,
        );
        inAccent = false;
        accentBuffer = [];
      }
      return;
    }
    // Plain text chunk — React escapes it on render.
    if (inAccent) {
      accentBuffer.push(chunk);
    } else {
      out.push(chunk);
    }
  });

  // Defensive: an unclosed <span class="br"> falls through as plain text.
  if (inAccent && accentBuffer.length > 0) {
    out.push(accentBuffer.join(""));
  }

  return out;
}
