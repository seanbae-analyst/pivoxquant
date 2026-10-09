/**
 * iOS launch images for the installed app (apple-touch-startup-image).
 *
 * iOS ignores the manifest's background_color: without a launch image whose
 * media query matches the device EXACTLY, a home-screen launch flashes white
 * before the first paint. Each PNG is the AppCover picture (PIVOXQUANT on
 * Vantablack, components/pwa/app-welcome.tsx), so launch → cover never
 * changes picture.
 *
 * The list is JSON so scripts/render-pwa-assets.mjs renders exactly the files
 * this module links — add a device there, re-run the script, done.
 */
import screens from "./pwa-splash-screens.json";

export type SplashScreen = {
  file: string;
  /** CSS px (device-width / device-height in portrait). */
  width: number;
  height: number;
  dpr: number;
  devices: string;
};

export const SPLASH_SCREENS: ReadonlyArray<SplashScreen> = screens;

export function splashMedia(s: SplashScreen): string {
  return (
    `(device-width: ${s.width}px) and (device-height: ${s.height}px) and ` +
    `(-webkit-device-pixel-ratio: ${s.dpr}) and (orientation: portrait)`
  );
}

/** Shape of Next's `appleWebApp.startupImage` descriptors. */
export const SPLASH_STARTUP_IMAGES: Array<{ url: string; media: string }> =
  SPLASH_SCREENS.map((s) => ({ url: `/splash/${s.file}`, media: splashMedia(s) }));
