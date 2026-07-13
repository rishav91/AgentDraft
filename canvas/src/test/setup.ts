import "@testing-library/jest-dom/vitest";

// jsdom's File doesn't implement Blob.text() - polyfill via FileReader so
// FileLoader's `await file.text()` works under Vitest's jsdom environment.
if (typeof File !== "undefined" && !File.prototype.text) {
  File.prototype.text = function (this: Blob): Promise<string> {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result));
      reader.onerror = () => reject(reader.error);
      reader.readAsText(this);
    });
  };
}
