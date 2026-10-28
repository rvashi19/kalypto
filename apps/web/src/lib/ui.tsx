import { Badge } from "@repo/ui";

export const inputCls =
  "flex h-11 w-full rounded-lg border border-[#b7b9be] bg-white px-3.5 py-2 text-sm text-[#101214] transition-colors placeholder:text-[#42526e]/60 focus:border-[#1868db] focus:outline-none focus:ring-2 focus:ring-[#1868db]/25 focus:ring-offset-2 focus:ring-offset-white disabled:opacity-50";

export const selectCls = `${inputCls} cursor-pointer`;

export function AiBadge() {
  return <Badge tone="info">AI assist</Badge>;
}
