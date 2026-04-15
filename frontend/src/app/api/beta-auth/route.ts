import { NextRequest, NextResponse } from "next/server";
import { createHmac, timingSafeEqual } from "node:crypto";

const COOKIE_NAME = "pivox_beta_access";
const MAX_AGE_SECONDS = 60 * 60 * 24 * 30; // 30 days

function signedBetaToken(secret: string): string {
  return createHmac("sha256", secret).update("beta-verified").digest("hex");
}

export async function POST(req: NextRequest) {
  const correct = process.env.BETA_PASSWORD;
  const signingSecret =
    process.env.BETA_SIGNING_SECRET ?? process.env.SECRET_KEY ?? "";

  if (!correct) {
    return NextResponse.json(
      { error: "Beta gate is not configured" },
      { status: 500 },
    );
  }

  if (!signingSecret) {
    return NextResponse.json(
      { error: "Beta gate signing secret is not configured" },
      { status: 500 },
    );
  }

  let password: unknown;
  try {
    const body = (await req.json()) as { password?: unknown };
    password = body?.password;
  } catch {
    return NextResponse.json(
      { error: "Invalid request body" },
      { status: 400 },
    );
  }

  if (typeof password !== "string" || password.length === 0) {
    return NextResponse.json(
      { error: "Password required" },
      { status: 400 },
    );
  }

  const a = Buffer.from(password);
  const b = Buffer.from(correct);
  const matches = a.length === b.length && timingSafeEqual(a, b);

  if (!matches) {
    return NextResponse.json(
      { error: "Invalid password" },
      { status: 401 },
    );
  }

  const response = NextResponse.json({ ok: true });
  response.cookies.set(COOKIE_NAME, signedBetaToken(signingSecret), {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    maxAge: MAX_AGE_SECONDS,
    path: "/",
  });
  return response;
}

// Optional: allow clearing the cookie if we ever need a "sign out of beta" flow.
export async function DELETE() {
  const response = NextResponse.json({ ok: true });
  response.cookies.set(COOKIE_NAME, "", {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    maxAge: 0,
    path: "/",
  });
  return response;
}
