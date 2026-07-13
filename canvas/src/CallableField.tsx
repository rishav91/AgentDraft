import { useEffect, useId, useState } from "react";

import { fetchCallableSource } from "./api";

type CallableFieldProps = {
  value: string;
  onChange: (value: string) => void;
  callables: string[];
  apiBase: string;
  placeholder?: string;
};

// A single combobox: one <input> backed by a <datalist>, showing the current
// value (or the placeholder as a fallback when empty) - not a separate
// text-field-plus-picker. Free typing still works; picking a suggestion just
// fills the same field.
//
// Native datalist quirk this works around: once the field's value exactly
// matches an option, most browsers only show that one match if you reopen
// the list without editing - looks like there's no way back to the full
// list. Clearing the *displayed* text on focus (not the real value) makes
// the browser filter against "", so every option shows again; blurring
// without picking/typing anything just reveals the unchanged real value.
export function CallableField({ value, onChange, callables, apiBase, placeholder }: CallableFieldProps) {
  const datalistId = useId();
  const isKnown = callables.includes(value);
  const [source, setSource] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [draft, setDraft] = useState<string | null>(null);

  useEffect(() => {
    if (!isKnown) {
      setSource(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    fetchCallableSource(apiBase, value).then((result) => {
      if (!cancelled) {
        setSource(result);
        setLoading(false);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [isKnown, value, apiBase]);

  return (
    <div className="callable-field">
      <input
        list={datalistId}
        value={draft ?? value}
        placeholder={placeholder}
        onFocus={() => setDraft("")}
        onBlur={() => setDraft(null)}
        onChange={(e) => {
          setDraft(e.target.value);
          onChange(e.target.value);
        }}
      />
      <datalist id={datalistId}>
        {callables.map((c) => (
          <option key={c} value={c} />
        ))}
      </datalist>
      {isKnown && loading && <p className="callable-field__hint">loading source…</p>}
      {isKnown && !loading && source && <pre className="callable-field__source">{source}</pre>}
    </div>
  );
}
