import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import {
  removeNode,
  setOutgoingConditional,
  setOutgoingDirect,
  updateNode,
} from "./editorActions";
import { Inspector } from "./Inspector";
import type { GraphNode, GraphStructure } from "./types";

vi.mock("./api", () => ({
  fetchCallableSource: vi.fn().mockResolvedValue(null),
}));

// Inspector's labels aren't `htmlFor`-associated to their controls (a
// separate accessibility gap, not fixed here) - find a field by its
// `.inspector__field` wrapper's label text instead of getByLabelText.
function field(container: HTMLElement, labelText: string): HTMLElement {
  const match = Array.from(container.querySelectorAll(".inspector__field")).find(
    (el) => el.querySelector("label")?.textContent === labelText,
  );
  if (!match) throw new Error(`no .inspector__field with label "${labelText}"`);
  return match as HTMLElement;
}

function fieldControl(container: HTMLElement, labelText: string): HTMLElement {
  const control = field(container, labelText).querySelector("input, select, textarea");
  if (!control) throw new Error(`field "${labelText}" has no input/select/textarea`);
  return control as HTMLElement;
}

function llmSchema(): GraphStructure {
  return {
    schema_version: 1,
    nodes: [
      {
        id: "chat",
        kind: "llm",
        llm: { provider: "anthropic", model: "claude-sonnet-5", system: null },
        handler: null,
        tools: [],
      },
      {
        id: "b",
        kind: "llm",
        llm: { provider: "anthropic", model: "claude-sonnet-5", system: null },
        handler: null,
        tools: [],
      },
    ],
    edges: [{ from: "chat", kind: "direct", to: "b", condition: null, routes: null }],
  };
}

function conditionalSchema(): GraphStructure {
  return {
    schema_version: 1,
    nodes: [
      {
        id: "router",
        kind: "llm",
        llm: { provider: "anthropic", model: "claude-sonnet-5", system: null },
        handler: null,
        tools: [],
      },
      {
        id: "b",
        kind: "llm",
        llm: { provider: "anthropic", model: "claude-sonnet-5", system: null },
        handler: null,
        tools: [],
      },
      {
        id: "c",
        kind: "llm",
        llm: { provider: "anthropic", model: "claude-sonnet-5", system: null },
        handler: null,
        tools: [],
      },
    ],
    edges: [
      {
        from: "router",
        kind: "conditional",
        to: null,
        condition: "pkg:route",
        routes: { positive: "b", negative: "c" },
      },
    ],
  };
}

// Mirrors how Editor.tsx actually wires Inspector's callbacks, so these tests
// exercise a real toggle-and-back user flow, not just isolated prop changes.
function TestHarness({ initial, nodeId }: { initial: GraphStructure; nodeId: string }) {
  const [structure, setStructure] = useState(initial);
  return (
    <Inspector
      structure={structure}
      nodeId={nodeId}
      apiBase="http://api"
      callables={[]}
      providers={["anthropic"]}
      onUpdateNode={(patch: Partial<GraphNode>) => setStructure(updateNode(structure, nodeId, patch))}
      onRemoveNode={() => setStructure(removeNode(structure, nodeId).structure)}
      onSetOutgoingDirect={(targets) => setStructure(setOutgoingDirect(structure, nodeId, targets))}
      onSetOutgoingConditional={(condition, routes) =>
        setStructure(setOutgoingConditional(structure, nodeId, condition, routes))
      }
    />
  );
}

describe("Inspector - kind switch caching", () => {
  it("restores llm fields after switching to handler and back", async () => {
    const { container } = render(<TestHarness initial={llmSchema()} nodeId="chat" />);
    const user = userEvent.setup();

    expect(fieldControl(container, "provider")).toHaveValue("anthropic");

    await user.click(screen.getByRole("radio", { name: "handler" }));
    expect(screen.getByRole("radio", { name: "llm" })).not.toBeChecked();

    await user.click(screen.getByRole("radio", { name: "llm" }));

    expect(fieldControl(container, "provider")).toHaveValue("anthropic");
    expect(fieldControl(container, "model")).toHaveValue("claude-sonnet-5");
  });

  it("restores the handler reference after switching to llm and back", async () => {
    const schema: GraphStructure = {
      schema_version: 1,
      nodes: [{ id: "shout", kind: "handler", llm: null, handler: "pkg:fn", tools: [] }],
      edges: [],
    };
    render(<TestHarness initial={schema} nodeId="shout" />);
    const user = userEvent.setup();

    await user.click(screen.getByRole("radio", { name: "llm" }));
    await user.click(screen.getByRole("radio", { name: "handler" }));

    expect(screen.getByPlaceholderText("module.path:function_name")).toHaveValue("pkg:fn");
  });
});

describe("Inspector - outgoing routing switch caching", () => {
  it("restores the condition and routes after switching to direct and back", async () => {
    render(<TestHarness initial={conditionalSchema()} nodeId="router" />);
    const user = userEvent.setup();

    const conditionField = screen.getByPlaceholderText("module.path:function_name");
    expect(conditionField).toHaveValue("pkg:route");
    expect(screen.getByDisplayValue("positive")).toBeInTheDocument();

    await user.click(screen.getByRole("radio", { name: "direct" }));
    await user.click(screen.getByRole("radio", { name: "conditional" }));

    expect(screen.getByPlaceholderText("module.path:function_name")).toHaveValue("pkg:route");
    expect(screen.getByDisplayValue("positive")).toBeInTheDocument();
    expect(screen.getByDisplayValue("negative")).toBeInTheDocument();
  });

  it("restores the direct target after switching to conditional and back", async () => {
    const { container } = render(<TestHarness initial={llmSchema()} nodeId="chat" />);
    const user = userEvent.setup();

    const routingField = () => field(container, "outgoing routing");
    expect(routingField().querySelector("select")).toHaveValue("b");

    await user.click(screen.getByRole("radio", { name: "conditional" }));
    await user.click(screen.getByRole("radio", { name: "direct" }));

    expect(routingField().querySelector("select")).toHaveValue("b");
  });
});
