import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

import "@testing-library/jest-dom/vitest";

// Vitest runs without globals, so React Testing Library cannot register its own
// cleanup hook — tear the DOM down between tests here instead.
afterEach(() => {
  cleanup();
});

// jsdom does not implement scrollIntoView, which the timeline auto-scroll uses.
if (typeof Element.prototype.scrollIntoView !== "function") {
  Element.prototype.scrollIntoView = () => undefined;
}
