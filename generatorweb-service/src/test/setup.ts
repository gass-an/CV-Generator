import "@testing-library/jest-dom/vitest";

if (!("createObjectURL" in URL)) {
  Object.defineProperty(URL, "createObjectURL", {
    configurable: true,
    value: () => "blob:test",
  });
}
if (!("revokeObjectURL" in URL)) {
  Object.defineProperty(URL, "revokeObjectURL", {
    configurable: true,
    value: () => undefined,
  });
}
