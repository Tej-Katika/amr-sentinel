import { useEffect, useState } from "react";
import { alerts as alertsApi } from "../services/api";
import type { Alert } from "../types";

export default function AlertsPage() {
  const [data, setData] = useState<Alert[]>([]);
  const [severity, setSeverity] = useState("ALL");
  const [days, setDays] = useState(30);

  useEffect(() => {
    alertsApi.list(severity, days).then((r) => setData(r.alerts));
  }, [severity, days]);

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Outbreak Alerts</h1>
      <div className="flex gap-3 text-sm">
        <select value={severity} onChange={(e) => setSeverity(e.target.value)} className="border rounded px-2 py-1">
          <option value="ALL">All severities</option>
          <option value="HIGH">HIGH</option>
          <option value="MODERATE">MODERATE</option>
          <option value="INVESTIGATE">INVESTIGATE</option>
        </select>
        <select value={days} onChange={(e) => setDays(Number(e.target.value))} className="border rounded px-2 py-1">
          <option value={7}>7 days</option>
          <option value={30}>30 days</option>
          <option value={90}>90 days</option>
        </select>
      </div>
      <div className="bg-white rounded-lg shadow divide-y">
        {data.length === 0 && <div className="p-6 text-gray-500 text-sm">No alerts.</div>}
        {data.map((a) => (
          <div key={a.alert_id} className="p-5 grid grid-cols-12 gap-3 items-start">
            <div className="col-span-1">
              <span
                className={`px-2 py-0.5 rounded text-xs text-white ${
                  a.severity === "HIGH"
                    ? "bg-red-500"
                    : a.severity === "MODERATE"
                    ? "bg-amber-500"
                    : "bg-blue-500"
                }`}
              >
                {a.severity}
              </span>
            </div>
            <div className="col-span-3 italic">{a.organism_name}</div>
            <div className="col-span-2">{a.antibiotic_name ?? "—"}</div>
            <div className="col-span-2">{a.alert_type}</div>
            <div className="col-span-2 text-xs text-gray-500">
              {new Date(a.triggered_at).toLocaleString()}
            </div>
            <div className="col-span-2 text-xs text-gray-600 truncate">
              {Object.entries(a.details ?? {}).slice(0, 2).map(([k, v]) => (
                <div key={k}>
                  <span className="font-medium">{k}:</span> {String(v)}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
