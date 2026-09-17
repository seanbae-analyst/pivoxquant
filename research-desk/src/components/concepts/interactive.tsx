import type { InteractiveId } from "@/lib/concepts/concepts";
import { ContractSim } from "./contract-sim";
import { LayersDiagram } from "./layers-diagram";
import { LineageGraph } from "./lineage-graph";
import { MiniCatalog } from "./mini-catalog";
import { ReadinessMeter } from "./readiness-meter";
import { SchemaSim } from "./schema-sim";

export function Interactive({ id, slug }: { id: InteractiveId; slug: string }) {
  switch (id) {
    case "catalog":
      return <MiniCatalog highlight={slug === "data-ownership" ? "owner" : slug === "data-governance" ? "pii" : "search"} />;
    case "lineage":
      return <LineageGraph mode={slug === "data-observability" ? "incident" : "lineage"} initial={slug === "data-observability" ? "orders_raw.currency" : "daily_revenue.revenue_krw"} />;
    case "contract":
      return <ContractSim />;
    case "readiness":
      return <ReadinessMeter />;
    case "layers":
      return <LayersDiagram focus={slug === "open-table-format" ? "format" : "engines"} />;
    case "schema":
      return <SchemaSim />;
  }
}
