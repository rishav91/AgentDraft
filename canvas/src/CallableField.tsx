import { useEffect, useState } from "react";

import { fetchCallableSource } from "./api";

type CallableFieldProps = {
  value: string;
  onChange: (value: string) => void;
  callables: string[];
  apiBase: string;
  datalistId: string;
  placeholder?: string;
};

// Text input with autocomplete suggestions from discovered module:function
// callables (FR-4.5), plus a read-only source preview when the current value
// matches a known one exactly. Always free text underneath - a reference the
// scanner missed (e.g. dynamically defined) can still be typed by hand.
export function CallableField({
  value,
  onChange,
  callables,
  apiBase,
  datalistId,
  placeholder,
}: CallableFieldProps) {
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
      <input
        list={datalistId}
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
      />
      {isKnown && loading && <p className="callable-field__hint">loading source…</p>}
      {isKnown && !loading && source && <pre className="callable-field__source">{source}</pre>}
    </div>
  );
}
