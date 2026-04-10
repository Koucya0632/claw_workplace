import type { OpenClawInstanceResponse } from "@/lib/types";

interface OpenClawInstancePickerProps {
  instances: OpenClawInstanceResponse[];
  value: string;
  onChange: (nextValue: string) => void;
  disabled?: boolean;
}

export function OpenClawInstancePicker({
  instances,
  value,
  onChange,
  disabled = false
}: OpenClawInstancePickerProps) {
  // 多數管理頁都要先選 instance，因此把 selector 抽成共用元件。
  return (
    <select
      value={value}
      onChange={(event) => onChange(event.target.value)}
      disabled={disabled}
      className="border-4 border-ink bg-white px-4 py-3 text-sm outline-none disabled:cursor-not-allowed disabled:opacity-60"
    >
      {instances.length === 0 ? (
        <option value="">尚無 OpenClaw Instance</option>
      ) : null}
      {instances.map((instance) => (
        <option key={instance.id} value={instance.id}>
          {instance.name}
        </option>
      ))}
    </select>
  );
}
