import '@testing-library/jest-dom/vitest';

// jsdom implements neither, and components that use them would otherwise throw
// during tests for reasons unrelated to what is being tested.
globalThis.matchMedia ??= (query) => ({
  matches: false,
  media: query,
  addEventListener() {},
  removeEventListener() {},
  addListener() {},
  removeListener() {},
  dispatchEvent: () => false,
});

globalThis.ResizeObserver ??= class {
  observe() {}
  unobserve() {}
  disconnect() {}
};
