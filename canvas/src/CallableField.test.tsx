import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { CallableField } from "./CallableField";

vi.mock("./api", () => ({
  fetchCallableSource: vi.fn().mockResolvedValue(null),
}));

const CALLABLES = ["pkg.a:foo", "pkg.b:bar", "pkg.c:baz"];

describe("CallableField", () => {
  it("renders a single combobox showing the current value", async () => {
    render(
      <CallableField value="pkg.a:foo" onChange={vi.fn()} callables={CALLABLES} apiBase="http://api" />,
    );

    expect(await screen.findByRole("combobox")).toHaveValue("pkg.a:foo");
  });

  it("shows the placeholder as a fallback when empty", async () => {
    render(
      <CallableField
        value=""
        onChange={vi.fn()}
        callables={CALLABLES}
        apiBase="http://api"
        placeholder="module.path:function_name"
      />,
    );

    expect(await screen.findByPlaceholderText("module.path:function_name")).toHaveValue("");
  });

  it("lists every callable in the datalist even when a value is already set", async () => {
    render(
      <CallableField value="pkg.a:foo" onChange={vi.fn()} callables={CALLABLES} apiBase="http://api" />,
    );

    const input = await screen.findByRole("combobox");
    const datalistId = input.getAttribute("list");
    const datalist = document.getElementById(datalistId!);
    const optionValues = Array.from(datalist!.querySelectorAll("option")).map((o) =>
      o.getAttribute("value"),
    );

    expect(optionValues).toEqual(CALLABLES);
  });

  it("clears the displayed text on focus so all suggestions show, without changing the real value", async () => {
    const onChange = vi.fn();
    render(
      <CallableField value="pkg.a:foo" onChange={onChange} callables={CALLABLES} apiBase="http://api" />,
    );
    const user = userEvent.setup();

    await user.click(await screen.findByRole("combobox"));

    expect(screen.getByRole("combobox")).toHaveValue("");
    expect(onChange).not.toHaveBeenCalled();
  });

  it("restores the display to the real value on blur if nothing was typed", async () => {
    const onChange = vi.fn();
    render(
      <CallableField value="pkg.a:foo" onChange={onChange} callables={CALLABLES} apiBase="http://api" />,
    );
    const user = userEvent.setup();

    await user.click(await screen.findByRole("combobox"));
    await user.tab();

    expect(screen.getByRole("combobox")).toHaveValue("pkg.a:foo");
  });

  it("propagates typed input immediately via onChange", async () => {
    const onChange = vi.fn();
    render(<CallableField value="" onChange={onChange} callables={CALLABLES} apiBase="http://api" />);
    const user = userEvent.setup();

    await user.type(await screen.findByRole("combobox"), "x");

    expect(onChange).toHaveBeenCalledWith("x");
  });
});
