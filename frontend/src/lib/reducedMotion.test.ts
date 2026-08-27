import { describe, expect, it, vi } from "vitest";
import { watchReducedMotion } from "./reducedMotion";

describe("watchReducedMotion", () => {
  it("reacts to system motion preference changes and unsubscribes", () => {
    const listener = vi.fn();
    const removeEventListener = vi.fn();
    const addEventListener = vi.fn((_event: string, callback: (event: MediaQueryListEvent) => void) => {
      listener.mockImplementationOnce(() => callback({ matches: true } as MediaQueryListEvent));
    });
    vi.stubGlobal("matchMedia", () => ({ matches: false, addEventListener, removeEventListener }));
    const onChange = vi.fn();

    const stop = watchReducedMotion(onChange);
    expect(addEventListener).toHaveBeenCalledWith("change", expect.any(Function));
    listener();
    expect(onChange).toHaveBeenCalledWith(true);

    stop();
    expect(removeEventListener).toHaveBeenCalledWith("change", expect.any(Function));
  });
});
