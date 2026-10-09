import { RouteSkeleton } from "@/components/layout/route-skeleton";

/**
 * (dashboard) loading UI — shown inside the dashboard shell while a screen's
 * route segment loads, so a tab tap answers at once (2026-10-09). The app
 * bar, bottom nav and the layout's single disclaimer stay mounted around it.
 */
export default function DashboardLoading() {
  return <RouteSkeleton />;
}
