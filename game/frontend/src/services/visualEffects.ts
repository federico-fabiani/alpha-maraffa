export const CRT_FLICKER_EVENT = "app:crt-flicker";

export function triggerCrtFlicker(): void {
  if (typeof window === "undefined") {
    return;
  }

  window.dispatchEvent(new CustomEvent(CRT_FLICKER_EVENT));
}
