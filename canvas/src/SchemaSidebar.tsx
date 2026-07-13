import { useState } from "react";

import type { SchemaEntry } from "./api";

type SchemaSidebarProps = {
  schemas: SchemaEntry[];
  activePath: string | null;
  disabled: boolean;
  onSelect: (path: string) => void;
};

export function SchemaSidebar({ schemas, activePath, disabled, onSelect }: SchemaSidebarProps) {
  const [collapsed, setCollapsed] = useState(false);

  if (collapsed) {
    return (
      <div className="schema-sidebar schema-sidebar--collapsed">
        <button type="button" onClick={() => setCollapsed(false)} title="Show schemas">
          ▸
        </button>
      </div>
    );
  }

  return (
    <aside className="schema-sidebar">
      <div className="schema-sidebar__header">
        <span>Schemas</span>
        <button type="button" onClick={() => setCollapsed(true)} title="Hide schemas">
          ◂
        </button>
      </div>
      {disabled && (
        <p className="schema-sidebar__notice">Save or discard changes to switch schemas.</p>
      )}
      <div className="schema-sidebar__list">
        {schemas.length === 0 && (
          <p className="schema-sidebar__empty">No .yaml/.yml files found.</p>
        )}
        {schemas.map((entry) => {
          const isActive = entry.path === activePath;
          const classNames = ["schema-sidebar__tile"];
          if (isActive) classNames.push("schema-sidebar__tile--active");
          if (!entry.valid) classNames.push("schema-sidebar__tile--invalid");

          return (
            <button
              type="button"
              key={entry.path}
              className={classNames.join(" ")}
              disabled={!entry.valid || isActive || disabled}
              onClick={() => onSelect(entry.path)}
              title={entry.valid ? entry.path : `${entry.path} (invalid schema)`}
            >
              <span className="schema-sidebar__tile-name">{entry.path}</span>
              <span className="schema-sidebar__tile-meta">
                {entry.valid
                  ? `${entry.node_count} node${entry.node_count === 1 ? "" : "s"}`
                  : "invalid"}
              </span>
            </button>
          );
        })}
      </div>
    </aside>
  );
}
