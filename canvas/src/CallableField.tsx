import { useEffect, useState } from "react";

import { fetchCallableSource } from "./api";

type CallableFieldProps = {
  value: string;
  onChange: (value: string) => void;
  callables: string[];
  apiBase: string;
  placeholder?: string;
};

// Text input for a module:function reference, with a source preview when the
// current value matches a known one (FR-4.5). Suggestions come from an
// explicit "pick from list" <select> rather than a <datalist> on the text
// input itself: once a datalist-backed input's value exactly matches an
// option, most browsers only show that single match on reopen, making it
// look like there's no way back to the full list. A plain <select> always
// shows every option regardless of the text field's current value.
export function CallableField({ value, onChange, callables, apiBase, placeholder }: CallableFieldProps) {
  const isKnown = callables.includes(value);
  const [source, setSource] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

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
      <div className="callable-field__row">
        <input value={value} placeholder={placeholder} onChange={(e) => onChange(e.target.value)} />
        {callables.length > 0 && (
          <select
            className="callable-field__picker"
            value=""
            aria-label="pick a known callable"
            onChange={(e) => {
              if (e.target.value) onChange(e.target.value);
            }}
          >
            <option value="">▾</option>
            {callables.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        )}
      </div>
      {isKnown && loading && <p className="callable-field__hint">loading source…</p>}
      {isKnown && !loading && source && <pre className="callable-field__source">{source}</pre>}
    </div>
  );
}
