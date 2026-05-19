/**
 * Re-export shim — Wave 2 Phase 1A infra.
 *
 * Eyebrow originally lived under components/landing/ because it was a
 * landing-page primitive. The Wave 2 sweep needs it on dashboard surfaces
 * too (sections, modal headers, weekly memo cards), so it gets a UI-tier
 * alias path. The original module stays put to preserve the 4 existing
 * imports (`@/components/landing/eyebrow`) — this file is the new
 * preferred import.
 *
 * Preferred:
 *   import { Eyebrow } from "@/components/ui/eyebrow";
 *
 * Legacy (kept working):
 *   import { Eyebrow } from "@/components/landing/eyebrow";
 */
export { Eyebrow } from "@/components/landing/eyebrow";
