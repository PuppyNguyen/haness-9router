export function ModelPicker({ models = [], value, disabled, onChange }) {
  return <div class="model-picker"><label for="modelSelect">Model cho tác vụ</label><div class="model-picker-row"><select id="modelSelect" value={value} disabled={disabled} onChange={(event) => onChange(event.currentTarget.value)}>
    <option value="">Chọn model…</option>{models.map((model) => <option key={model} value={model}>{model}</option>)}
  </select></div></div>;
}
