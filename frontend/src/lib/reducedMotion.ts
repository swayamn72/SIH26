export function prefersReducedMotion(): boolean {
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches === true;
}

/** Subscribe to system motion-preference changes, including older Safari. */
export function watchReducedMotion(onChange: (reduced: boolean) => void): () => void {
  if (typeof window === "undefined" || !window.matchMedia) return () => undefined;
  const query = window.matchMedia("(prefers-reduced-motion: reduce)");
  const handleChange = (event: MediaQueryListEvent) => onChange(event.matches);
  if (query.addEventListener) {
    query.addEventListener("change", handleChange);
    return () => query.removeEventListener("change", handleChange);
  }
  query.addListener(handleChange);
  return () => query.removeListener(handleChange);
}
