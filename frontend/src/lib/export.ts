/** CSV/JSON export utilities for dashboard data. */

export type ExportFormat = "csv" | "json";

/** Convert array of objects to CSV string. */
function toCSV(data: Record<string, unknown>[], columns?: string[]): string {
  if (data.length === 0) return "";
  const keys = columns ?? Object.keys(data[0]);
  const header = keys.join(",");
  const rows = data.map((row) =>
    keys
      .map((k) => {
        const v = row[k];
        if (v == null) return "";
        const s = String(v);
        // Quote if contains comma, newline, or double-quote
        if (s.includes(",") || s.includes("\n") || s.includes('"')) {
          return `"${s.replace(/"/g, '""')}"`;
        }
        return s;
      })
      .join(","),
  );
  return [header, ...rows].join("\n");
}

/** Trigger a browser download of a text blob. */
function downloadBlob(content: string, filename: string, mime: string) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

/** Export an array of objects as CSV or JSON file download. */
export function exportData(
  data: Record<string, unknown>[],
  filenameBase: string,
  format: ExportFormat,
  columns?: string[],
) {
  const timestamp = new Date().toISOString().slice(0, 19).replace(/:/g, "-");
  if (format === "json") {
    const content = JSON.stringify(data, null, 2);
    downloadBlob(content, `${filenameBase}_${timestamp}.json`, "application/json");
  } else {
    const content = toCSV(data, columns);
    downloadBlob(content, `${filenameBase}_${timestamp}.csv`, "text/csv");
  }
}
