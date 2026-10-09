import { useMemo, useState } from "react";
import rawFields from "./data/localRecords.json";

type FieldDef = { id: string; label: string; type: string; group: string; required: boolean; pattern: string };
const fields = rawFields as FieldDef[];

function validate(field: FieldDef, value: string, required: boolean) {
  if (required && !value) return `${field.id} is required`;
  if (field.pattern === "email" && value && !value.includes("@")) return `Invalid email for ${field.id}`;
  if (field.pattern === "phone" && value && !/^[-0-9 ]+$/.test(value)) return `Invalid phone for ${field.id}`;
  if (field.pattern === "number" && value && Number.isNaN(Number(value))) return `Invalid number for ${field.id}`;
  if (field.pattern === "checked" && required && value !== "checked") return `${field.id} must be checked`;
  return "";
}

function App() {
  const [selectedId, setSelectedId] = useState("FORM-EMAIL");
  const [added, setAdded] = useState<string[]>([]);
  const [requiredOverrides, setRequiredOverrides] = useState<Record<string, boolean>>({});
  const [values, setValues] = useState<Record<string, string>>({});
  const selected = fields.find((field) => field.id === selectedId) ?? fields[0];
  const addedFields = added.map((id) => fields.find((field) => field.id === id)).filter(Boolean) as FieldDef[];
  const addSelected = () => setAdded((current) => current.includes(selectedId) ? current : [...current, selectedId]);
  const moveUp = () => setAdded((current) => { const index = current.indexOf(selectedId); if (index <= 0) return current; const next = [...current]; [next[index - 1], next[index]] = [next[index], next[index - 1]]; return next; });
  const setRequired = (id: string, value: boolean) => setRequiredOverrides((current) => ({ ...current, [id]: value }));
  const errors = addedFields.map((field) => validate(field, values[field.id] || "", requiredOverrides[field.id] ?? field.required)).filter(Boolean);
  const schema = { fields: addedFields.map((field) => ({ id: field.id, type: field.type, required: requiredOverrides[field.id] ?? field.required })) };
  return <main className="app-shell" aria-label="Form builder validation workspace"><header className="topbar"><div><p className="eyebrow">Form builder</p><h1>Live validation form builder</h1><p className="lead">Add protected fields to the preview, edit sample values, toggle required state, reorder fields, and inspect generated schema.</p></div></header><section className="controls" aria-label="Builder controls"><button type="button" onClick={addSelected}>Add selected field</button><button type="button" onClick={moveUp}>Move field up</button><label><input type="checkbox" aria-label="Required field" checked={requiredOverrides[selected.id] ?? selected.required} onChange={(event) => setRequired(selected.id, event.target.checked)} /> Required field</label><button type="button" onClick={() => setAdded([])}>Clear form</button></section><section className="metrics" aria-label="Validation metrics"><article className="metric"><span>Field count</span><strong>{addedFields.length}</strong><small>{added.join(" / ") || "none"}</small></article><article className="metric"><span>Required fields</span><strong>{addedFields.filter((field) => requiredOverrides[field.id] ?? field.required).length}</strong><small>Current schema</small></article><article className="metric"><span>Validation errors</span><strong>{errors.length}</strong><small>{errors[0] || "No errors"}</small></article><article className="metric"><span>Selected field</span><strong>{selected.id}</strong><small>{selected.label}</small></article></section><section className="workspace"><section className="builder-grid"><section className="panel"><p className="eyebrow">Field palette</p><div className="palette">{fields.map((field) => <button type="button" className={`field-button ${field.id === selectedId ? "active" : ""}`} data-field-id={field.id} key={field.id} onClick={() => setSelectedId(field.id)}><strong>{field.id} - {field.label}</strong><small>{field.group} / {field.type} / {field.pattern}</small></button>)}</div></section><section className="panel"><p className="eyebrow">Form preview</p><div className="preview" aria-label="Form preview">{addedFields.map((field) => { const required = requiredOverrides[field.id] ?? field.required; const error = validate(field, values[field.id] || "", required); return <div className={`field-row ${field.id === selectedId ? "active" : ""}`} data-preview-field-id={field.id} key={field.id} onClick={() => setSelectedId(field.id)}><label>{field.id} - {field.label}<input aria-label={`${field.id} sample value`} type={field.type === "checkbox" ? "text" : field.type} value={values[field.id] || ""} onChange={(event) => setValues((current) => ({ ...current, [field.id]: event.target.value }))} placeholder={required ? "required" : "optional"}/></label>{error ? <p className="error">{error}</p> : <p className="valid">Valid</p>}</div>; })}</div></section></section><aside className="inspector" aria-live="polite" aria-label="Schema preview"><p className="eyebrow">Schema preview</p><h2>{selected.id} - {selected.label}</h2><div className="detail-grid"><div className="fact"><span>Group</span><strong>{selected.group}</strong></div><div className="fact"><span>Type</span><strong>{selected.type}</strong></div><div className="fact"><span>Pattern</span><strong>{selected.pattern}</strong></div><div className="fact"><span>Required</span><strong>{String(requiredOverrides[selected.id] ?? selected.required)}</strong></div></div><pre className="schema">{JSON.stringify(schema, null, 2)}</pre></aside></section></main>;
}
export default App;
