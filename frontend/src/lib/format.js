export function formatRupiah(value) {
  if (value === null || value === undefined) return "—";
  return new Intl.NumberFormat("id-ID", {
    style: "currency",
    currency: "IDR",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

export function formatNumber(value) {
  if (value === null || value === undefined) return "—";
  return new Intl.NumberFormat("id-ID").format(value);
}

export function formatPercent(value, digits = 1) {
  if (value === null || value === undefined) return "—";
  return `${new Intl.NumberFormat("id-ID", { maximumFractionDigits: digits }).format(value * 100)}%`;
}

export function formatMissing(value, formatter = formatNumber) {
  return value === null || value === undefined ? "—" : formatter(value);
}
