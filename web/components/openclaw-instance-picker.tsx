import type { OpenClawInstanceResponse } from "@/lib/types";

interface OpenClawInstancePickerProps {
  instances: OpenClawInstanceResponse[];
  value: string;
  onChange: (nextValue: string) => void;
}

export function OpenClawInstancePicker({ instances, value, onChange }: OpenClawInstancePickerProps) {
  // 多數管理頁都要先選 instance，因此把 selector 抽成共用元件。
  return (
    <select
      value={value}
      onChange={(event) => onChange(event.target.value)}
      className="border-4 border-ink bg-white px-4 py-3 text-sm outline-none"
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
