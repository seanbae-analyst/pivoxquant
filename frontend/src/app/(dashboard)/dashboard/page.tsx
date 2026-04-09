"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";

/** /dashboard redirects to /home (unified portfolio page) */
export default function DashboardRedirect() {
  const router = useRouter();
  useEffect(() => { router.replace("/home"); }, [router]);
  return null;
}
