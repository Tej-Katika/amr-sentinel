import { useState } from "react";
import api from "../services/api";

export default function GLASSPage() {
  const [year, setYear] = useState(new Date().getFullYear() - 1);
  const [busy, setBusy] = useState(false);

  async function downloadFile(path: string, filename: string) {
    setBusy(true);
    try {
      const r = await api.get(path, { params: { year }, responseType: "blob" });
      const url = URL.createObjectURL(new Blob([r.data]));
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">GLASS Export</h1>
      <p className="text-sm text-gray-500 max-w-2xl">
        Generate WHO GLASS-compliant submission files (RIS, SAMPLE, quality
        indicators) for a calendar year. CLSI M39 first-isolate rules and
        breakpoint version pinning are applied automatically.
      </p>
      <label className="text-sm">
        Year{" "}
        <input
          type="number"
          value={year}
          onChange={(e) => setYear(Number(e.target.value))}
          className="border rounded px-2 py-1 w-24"
        />
      </label>
      <div className="flex gap-3">
        <button
          disabled={busy}
          onClick={() => downloadFile("/glass/ris.csv", `glass_ris_${year}.csv`)}
          className="bg-sentinel-700 text-white px-4 py-2 rounded text-sm disabled:opacity-50"
        >
          Download RIS
        </button>
        <button
          disabled={busy}
          onClick={() => downloadFile("/glass/sample.csv", `glass_sample_${year}.csv`)}
          className="bg-sentinel-700 text-white px-4 py-2 rounded text-sm disabled:opacity-50"
        >
          Download SAMPLE
        </button>
      </div>
    </div>
  );
}
