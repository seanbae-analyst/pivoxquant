/**
 * Phone × broker → fill automation route (2026-10-10). Toss announces fills
 * by app push, so an iPhone opens on the iOS 27 notification route; every
 * other broker (or none picked) opens on SMS, which works on any iOS.
 * Every key the rules point at must exist in both catalogs — a missing one
 * would show the raw key on the onboarding screen.
 */
import { describe, it, expect } from "vitest";
import ko from "@/messages/ko.json";
import en from "@/messages/en.json";
import {
  FILL_BROKERS,
  brokerHintKey,
  defaultIosRoute,
  fillRoute,
  kickerKey,
  statusKey,
  stepKeys,
  type FillRoute,
} from "../fill-setup";

function lookup(catalog: unknown, key: string): unknown {
  return key.split(".").reduce<unknown>(
    (node, part) => (node && typeof node === "object" ? (node as Record<string, unknown>)[part] : undefined),
    catalog,
  );
}

describe("fill-setup rules", () => {
  it("opens an iPhone on the app-notification route only for Toss", () => {
    expect(defaultIosRoute("toss")).toBe("app");
    for (const b of FILL_BROKERS.filter((x) => x !== "toss")) {
      expect(defaultIosRoute(b)).toBe("sms");
    }
    expect(defaultIosRoute(null)).toBe("sms");
  });

  it("Android has one route whatever the iPhone choice", () => {
    expect(fillRoute("android", "app")).toBe("android");
    expect(fillRoute("android", "sms")).toBe("android");
    expect(fillRoute("ios", "app")).toBe("ios-app");
    expect(fillRoute("ios", "sms")).toBe("ios-sms");
  });

  it("the app-notification route has its own trigger and body steps, and shares the request and link steps", () => {
    const app = stepKeys("ios-app");
    const sms = stepKeys("ios-sms");
    expect(app).toHaveLength(7);
    expect(app).toContain("settingsV2.importTokens.iosApp2");
    expect(app).not.toContain("settingsV2.importTokens.ios2");
    for (const shared of ["ios3", "ios4", "ios7"]) {
      expect(app).toContain(`settingsV2.importTokens.${shared}`);
      expect(sms).toContain(`settingsV2.importTokens.${shared}`);
    }
  });

  it("gives a sourced hint only to brokers we checked; the rest get the generic one", () => {
    expect(brokerHintKey("toss")).toBe("fillsOnboarding.hint.toss");
    expect(brokerHintKey("kb")).toBe("fillsOnboarding.hint.kb");
    expect(brokerHintKey("mirae")).toBe("fillsOnboarding.hint.check");
    expect(brokerHintKey("other")).toBe("fillsOnboarding.hint.check");
  });

  it("every key it points at exists in ko and en", () => {
    const routes: FillRoute[] = ["android", "ios-sms", "ios-app"];
    const keys = [
      ...routes.flatMap((r) => [...stepKeys(r), kickerKey(r), statusKey(r)]),
      ...FILL_BROKERS.flatMap((b) => [brokerHintKey(b), `fillsOnboarding.broker.${b}`]),
      "fillsOnboarding.brokerLabel",
      "fillsOnboarding.brokerPrompt",
      "fillsOnboarding.iosRouteLabel",
      "fillsOnboarding.iosRoute.sms",
      "fillsOnboarding.iosRoute.app",
      "settingsV2.importTokens.iosAppCaveat",
    ];
    for (const key of keys) {
      expect(typeof lookup(ko, key), `ko ${key}`).toBe("string");
      expect(typeof lookup(en, key), `en ${key}`).toBe("string");
    }
  });
});
