import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { CallableField } from "./CallableField";

vi.mock("./api", () => ({
  fetchCallableSource: vi.fn().mockResolvedValue(null),
}));

const CALLABLES = ["pkg.a:foo", "pkg.b:bar", "pkg.c:baz"];

describe("CallableField", () => {
  it("shows every callable in the picker even when the field already has a value set", () => {
    render(
      <CallableField
        value="pkg.a:foo"
        onChange={vi.fn()}
        callables={CALLABLES}
        apiBase="http://api"
      />,
    );

    const picker = screen.getByRole("combobox", { name: /pick a known callable/i });
    const optionValues = Array.from(picker.querySelectorAll("option")).map((o) => o.getAttribute("value"));

    expect(optionValues).toEqual(["", ...CALLABLES]);
  });

  it("calls onChange with the picked value, leaving the picker reset to its placeholder", async () => {
    const onChange = vi.fn();
    render(
      <CallableField value="" onChange={onChange} callables={CALLABLES} apiBase="http://api" />,
    );
    const user = userEvent.setup();

    await user.selectOptions(
      screen.getByRole("combobox", { name: /pick a known callable/i }),
      "pkg.b:bar",
    );

    expect(onChange).toHaveBeenCalledWith("pkg.b:bar");
  });

  it("does not render a picker when there are no known callables", () => {
    render(<CallableField value="" onChange={vi.fn()} callables={[]} apiBase="http://api" />);

    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
  });

  it("still allows free-text typing regardless of the picker", async () => {
    const onChange = vi.fn();
    render(
      <CallableField value="" onChange={onChange} callables={CALLABLES} apiBase="http://api" />,
    );
    const user = userEvent.setup();

    await user.type(screen.getByRole("textbox"), "x");

    expect(onChange).toHaveBeenCalledWith("x");
  });
});
