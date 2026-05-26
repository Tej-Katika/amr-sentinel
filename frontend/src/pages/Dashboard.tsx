import { useEffect, useState } from "react";
import { alerts } from "../services/api";
import type { Alert } from "../types";

export default function Dashboard() {
  const [data, setData] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    alerts
      .list("ALL", 30)
      .then((r) => setData(r.alerts))
      .finally(() => setLoading(false));
  }, []);

  const counts = {
    HIGH: data.filter((a) => a.severity === "HIGH").length,
    MODERATE: data.filter((a) => a.severity === "MODERATE").length,
    INVESTIGATE: data.filter((a) => a.severity === "INVESTIGATE").length,
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Surveillance Overview</h1>
        <p className="text-sm text-gray-500">Last 30 days</p>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <Stat label="HIGH alerts" value={counts.HIGH} color="bg-red-500" />
        <Stat label="MODERATE alerts" value={counts.MODERATE} color="bg-amber-500" />
        <Stat label="INVESTIGATE alerts" value={counts.INVESTIGATE} color="bg-blue-500" />
      </div>

      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="font-semibold mb-3">Recent alerts</h2>
        {loading ? (
          <p className="text-gray-500">Loading…</p>
        ) : data.length === 0 ? (
          <p className="text-gray-500 text-sm">No alerts in the last 30 days.</p>
        ) : (
          <table className="w-full text-sm">
            <thead className="text-left text-gray-500">
              <tr>
                <th className="py-1">Severity</th>
                <th>Type</th>
                <th>Organism</th>
                <th>Antibiotic</th>
                <th>Triggered</th>
              </tr>
            </thead>
            <tbody>
              {data.slice(0, 10).map((a) => (
                <tr key={a.alert_id} className="border-t">
                  <td className="py-2">
                    <span className={`px-2 py-0.5 rounded text-xs text-white ${
                      a.severity === "HIGH" ? "bg-red-500"
                      : a.severity === "MODERATE" ? "bg-amber-500"
                      : "bg-blue-500"
                    }`}>{a.severity}</span>
                  </td>
                  <td>{a.alert_type}</td>
                  <td className="italic">{a.organism_name}</td>
                  <td>{a.antibiotic_name ?? "—"}</td>
                  <td className="text-gray-500 text-xs">
                    {new Date(a.triggered_at).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function Stat({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="bg-white rounded-lg shadow p-5">
      <div className={`w-2 h-2 rounded-full ${color} inline-block mr-2`} />
      <span className="text-sm text-gray-600">{label}</span>
      <div className="text-3xl font-bold mt-1">{value}</div>
    </div>
  );
}
