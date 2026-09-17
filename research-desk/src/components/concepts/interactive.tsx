import type { InteractiveId } from "@/lib/concepts/concepts";
import { ContractSim } from "./contract-sim";
import { LayersDiagram } from "./layers-diagram";
import { LineageGraph } from "./lineage-graph";
import { MiniCatalog } from "./mini-catalog";
import { ReadinessMeter } from "./readiness-meter";
import { SchemaSim } from "./schema-sim";
import { Scene3D } from "./three/scene-frame";

/**
 * 개념마다 만져보기 하나. 깊이가 개념의 일부인 둘(리니지·레이크하우스)만 3D 로 세우고,
 * 나머지는 평면이 더 정직하다. 3D 는 언제든 "평면" 으로 되돌릴 수 있다.
 */
export function Interactive({ id, slug }: { id: InteractiveId; slug: string }) {
  switch (id) {
    case "catalog":
      return <MiniCatalog highlight={slug === "data-ownership" ? "owner" : slug === "data-governance" ? "pii" : "search"} />;
    case "lineage": {
      const incident = slug === "data-observability";
      const initial = incident ? "orders_raw.currency" : "daily_revenue.revenue_krw";
      return (
        <Scene3D
          kind="pipeline"
          mode={incident ? "incident" : "lineage"}
          initial={initial}
          label={incident ? "이상이 번지는 길" : "컬럼이 흘러온 길"}
          flat={<LineageGraph mode={incident ? "incident" : "lineage"} initial={initial} />}
        />
      );
    }
    case "contract":
      return <ContractSim />;
    case "readiness":
      return <ReadinessMeter />;
    case "layers": {
      const focus = slug === "open-table-format" ? "format" : "engines";
      return <Scene3D kind="lakehouse" focus={focus} label="쌓인 다섯 층" flat={<LayersDiagram focus={focus} />} />;
    }
    case "schema":
      return <SchemaSim />;
  }
}
