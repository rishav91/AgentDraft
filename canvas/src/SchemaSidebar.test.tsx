import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { SchemaEntry } from "./api";
import { SchemaSidebar } from "./SchemaSidebar";

const SCHEMAS: SchemaEntry[] = [
  { path: "schema.yaml", valid: true, node_count: 2 },
  { path: "other.yaml", valid: true, node_count: 1 },
  { path: "broken.yaml", valid: false, node_count: null },
];

describe("SchemaSidebar", () => {
  it("renders a tile per discovered schema, with node counts", () => {
    render(
      <SchemaSidebar schemas={SCHEMAS} activePath="schema.yaml" disabled={false} onSelect={vi.fn()} />,
    );

    expect(screen.getByText("schema.yaml")).toBeInTheDocument();
    expect(screen.getByText("2 nodes")).toBeInTheDocument();
    expect(screen.getByText("1 node")).toBeInTheDocument();
  });

  it("marks the active tile disabled and non-clickable", () => {
    render(
      <SchemaSidebar schemas={SCHEMAS} activePath="schema.yaml" disabled={false} onSelect={vi.fn()} />,
    );

    expect(screen.getByText("schema.yaml").closest("button")).toBeDisabled();
    expect(screen.getByText("other.yaml").closest("button")).toBeEnabled();
  });

  it("marks invalid schemas disabled and shows 'invalid'", () => {
    render(
      <SchemaSidebar schemas={SCHEMAS} activePath="schema.yaml" disabled={false} onSelect={vi.fn()} />,
    );

    expect(screen.getByText("broken.yaml").closest("button")).toBeDisabled();
    expect(screen.getByText("invalid")).toBeInTheDocument();
  });

  it("calls onSelect with the tile's path when clicked", async () => {
    const onSelect = vi.fn();
    render(
      <SchemaSidebar schemas={SCHEMAS} activePath="schema.yaml" disabled={false} onSelect={onSelect} />,
    );
    const user = userEvent.setup();

    await user.click(screen.getByText("other.yaml"));

    expect(onSelect).toHaveBeenCalledWith("other.yaml");
  });

  it("disables every tile and shows a notice when disabled (unsaved changes)", () => {
    const onSelect = vi.fn();
    render(
      <SchemaSidebar schemas={SCHEMAS} activePath="schema.yaml" disabled={true} onSelect={onSelect} />,
    );

    expect(screen.getByText("other.yaml").closest("button")).toBeDisabled();
    expect(screen.getByText(/Save or discard changes/)).toBeInTheDocument();
  });

  it("shows an empty-state message when there are no schemas", () => {
    render(<SchemaSidebar schemas={[]} activePath={null} disabled={false} onSelect={vi.fn()} />);

    expect(screen.getByText(/No \.yaml\/\.yml files found/)).toBeInTheDocument();
  });

  it("collapses and expands via the toggle button", async () => {
    render(
      <SchemaSidebar schemas={SCHEMAS} activePath="schema.yaml" disabled={false} onSelect={vi.fn()} />,
    );
    const user = userEvent.setup();

    await user.click(screen.getByTitle("Hide schemas"));
    expect(screen.queryByText("schema.yaml")).not.toBeInTheDocument();

    await user.click(screen.getByTitle("Show schemas"));
    expect(screen.getByText("schema.yaml")).toBeInTheDocument();
  });
});
