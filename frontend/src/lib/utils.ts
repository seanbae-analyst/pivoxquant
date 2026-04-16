import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * Detect Korean stock ticker (numeric-only like "005930")
 * or explicit `is_korean` flag from API response.
 */
export function isKoreanTicker(ticker: string, isKorean?: boolean): boolean {
  if (isKorean != null) return isKorean;
  return /^\d+$/.test(ticker);
}
