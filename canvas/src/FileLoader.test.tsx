import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { FileLoader } from "./FileLoader";
import type { GraphStructure } from "./types";

const VALID_STRUCTURE: GraphStructure = { schema_version: 1, nodes: [], edges: [] };

function jsonFile(name: string, contents: string): File {
  return new File([contents], name, { type: "application/json" });
}

describe("FileLoader", () => {
  it("calls onLoad with the parsed structure for a valid export", async () => {
    const onLoad = vi.fn();
    render(<FileLoader onLoad={onLoad} />);
    const user = userEvent.setup();

    const input = screen.getByLabelText("Choose file", { selector: "input" });
    await user.upload(input, jsonFile("graph.json", JSON.stringify(VALID_STRUCTURE)));

    await waitFor(() => expect(onLoad).toHaveBeenCalledWith(VALID_STRUCTURE));
  });

  it("shows an error and does not call onLoad for malformed JSON", async () => {
    const onLoad = vi.fn();
    render(<FileLoader onLoad={onLoad} />);
    const user = userEvent.setup();

    const input = screen.getByLabelText("Choose file", { selector: "input" });
    await user.upload(input, jsonFile("graph.json", "not json"));

    await waitFor(() => expect(screen.getByText(/Couldn't parse JSON/)).toBeInTheDocument());
    expect(onLoad).not.toHaveBeenCalled();
  });

  it("shows an error and does not call onLoad for a well-formed but wrong-shaped JSON file", async () => {
    const onLoad = vi.fn();
    render(<FileLoader onLoad={onLoad} />);
    const user = userEvent.setup();

    const input = screen.getByLabelText("Choose file", { selector: "input" });
    await user.upload(input, jsonFile("graph.json", JSON.stringify({ hello: "world" })));

    await waitFor(() =>
      expect(screen.getByText(/doesn't look like an .agentdraft explain/)).toBeInTheDocument(),
    );
    expect(onLoad).not.toHaveBeenCalled();
  });
});
