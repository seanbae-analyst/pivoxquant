/**
 * Tapping the bottom-nav tab you are already on scrolls that screen back to
 * the top (native tab-bar behaviour). The window scrolls itself; screens with
 * their own inner scrollers (the phone pagers) listen for this event and
 * scroll their visible page.
 */
export const SCROLL_TOP_EVENT = "pq:scroll-top";
