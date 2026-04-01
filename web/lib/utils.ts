import { clsx } from "clsx";

export function cn(...values: Array<string | false | null | undefined>) {
  // 小型 className 合併工具，避免每個元件都手動拼接字串。
  return clsx(values);
}

export function formatDateTime(value?: string | null) {
  // 前端日期顯示統一在這裡集中處理，避免各頁面格式不一致。
  if (!value) {
    return "未執行";
  }

  return new Intl.DateTimeFormat("zh-TW", {
    dateStyle: "medium",
    timeStyle: "short"
  }).format(new Date(value));
}

