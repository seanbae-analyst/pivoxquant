import { NotFoundView } from "@/components/ui/not-found-view";

/** notFound() inside a dashboard route — the layout's shell stays around it. */
export default function DashboardNotFound() {
  return <NotFoundView inShell />;
}
