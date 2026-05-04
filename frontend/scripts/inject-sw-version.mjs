#!/usr/bin/env node
/**
 * inject-sw-version.mjs
 *
 * Replaces the placeholder `__SW_BUILD_ID__` (or any existing `sp-v*` /
 * `pq-build-*` literal) inside `public/sw.js` with a deterministic build
 * identifier so PWA-installed users get a fresh cache on every deploy
 * without anyone having to remember to bump a manual `sp-vN`.
 *
 * Build ID resolution order:
 *   1. PIVOX_SW_BUILD_ID  (explicit override)
 *   2. VERCEL_GIT_COMMIT_SHA  (Vercel build env)
 *   3. GITHUB_SHA  (GitHub Actions)
 *   4. `git rev-parse --short HEAD`  (local clone)
 *   5. `dev-<unix-ts>` fallback
 *
 * The injection is idempotent: running it twice in a row produces the
 * same file. We always normalise to the form `pq-build-<id>` so the
 * activate step in sw.js still nukes any cache that does not match the
 * current build (existing `sp-v*` caches purge naturally because the
 * key prefix changes).
 */

import { readFileSync, writeFileSync } from "fs";
import { dirname, join } from "path";
import { fileURLToPath } from "url";
import { execSync } from "child_process";

const __dirname = dirname(fileURLToPath(import.meta.url));
const SW_PATH = join(__dirname, "../public/sw.js");

function resolveBuildId() {
  if (process.env.PIVOX_SW_BUILD_ID) return process.env.PIVOX_SW_BUILD_ID;
  if (process.env.VERCEL_GIT_COMMIT_SHA)
    return process.env.VERCEL_GIT_COMMIT_SHA.slice(0, 8);
  if (process.env.GITHUB_SHA) return process.env.GITHUB_SHA.slice(0, 8);
  try {
    return execSync("git rev-parse --short=8 HEAD", { encoding: "utf8" }).trim();
  } catch {
    return `dev-${Date.now()}`;
  }
}

function injectVersion() {
  const buildId = resolveBuildId();
  const cacheVersion = `pq-build-${buildId}`;

  const original = readFileSync(SW_PATH, "utf8");

  // Match either the placeholder, an existing `pq-build-*`, or a legacy
  // `sp-v*` literal. The CACHE_VERSION constant is the only place where
  // these tokens should appear, so a global replace on the assignment is
  // safe and idempotent.
  const constRegex =
    /^const\s+CACHE_VERSION\s*=\s*"(?:__SW_BUILD_ID__|pq-build-[A-Za-z0-9._-]+|sp-v[\w.-]+)";/m;

  if (!constRegex.test(original)) {
    console.error(
      "[inject-sw-version] Could not find CACHE_VERSION literal in",
      SW_PATH,
    );
    process.exit(1);
  }

  const updated = original.replace(
    constRegex,
    `const CACHE_VERSION = "${cacheVersion}";`,
  );

  if (updated === original) {
    console.log(`[inject-sw-version] CACHE_VERSION already set to ${cacheVersion}`);
    return;
  }

  writeFileSync(SW_PATH, updated, "utf8");
  console.log(`[inject-sw-version] CACHE_VERSION → ${cacheVersion}`);
}

injectVersion();
