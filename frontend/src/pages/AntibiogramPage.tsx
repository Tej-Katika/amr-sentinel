import { useEffect, useState } from "react";
import { antibiograms } from "../services/api";
import type { Antibiogram, AntibiogramCell } from "../types";

const STRATIFICATIONS = ["ALL", "ICU", "NON_ICU", "BLOOD", "URINE"];

export default function AntibiogramPage() {
  const [data, setData] = useState<Antibiogram | null>(null);
  const [stratification, setStratification] = useState("ALL");
  const [periodMonths, setPeriodMonths] = useState(12);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    antibiograms
      .current({ period_months: periodMonths, stratification })
      .then(setData)
      .finally(() => setLoading(false));
  }, [stratification, periodMonths]);

  const organisms = data
    ? Array.from(new Set(data.cells.map((c) => c.organism_name))).sort()
    : [];
  const antibiotics = data
    ? Array.from(
        new Map(data.cells.map((c) => [c.antibiotic_atc, c.antibiotic_name])).entries(),
      )
    : [];
  const cellByPair = (org: string, atc: string): AntibiogramCell | undefined =>
    data?.cells.find((c) => c.organism_name === org && c.antibiotic_atc === atc);

  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Cumulative Antibiogram</h1>
          {data && (
            <p className="text-sm text-gray-500">
              {data.period_start} to {data.period_end}
            </p>
          )}
        </div>
        <div className="flex gap-3 text-sm">
          <label>
            Period{" "}
            <select
              value={periodMonths}
              onChange={(e) => setPeriodMonths(Number(e.target.value))}
              className="border rounded px-2 py-1"
            >
              <option value={3}>3 months</option>
              <option value={6}>6 months</option>
              <option value={12}>12 months</option>
              <option value={24}>24 months</option>
            </select>
          </label>
          <label>
            Stratification{" "}
            <select
              value={stratification}
              onChange={(e) => setStratification(e.target.value)}
              className="border rounded px-2 py-1"
            >
              {STRATIFICATIONS.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </label>
        </div>
      </div>

      {loading ? (
        <p className="text-gray-500">Loading…</p>
      ) : !data || data.cells.length === 0 ? (
        <p className="text-gray-500 text-sm">No antibiogram data available.</p>
      ) : (
        <div className="bg-white rounded-lg shadow overflow-x-auto">
          <table className="text-xs w-full">
            <thead>
              <tr>
                <th className="sticky left-0 bg-sentinel-700 text-white px-3 py-2 text-left z-10">
                  Organism
                </th>
                {antibiotics.map(([atc, name]) => (
                  <th key={atc} className="bg-sentinel-700 text-white px-2 py-2 text-center whitespace-nowrap">
                    {name}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {organisms.map((org) => (
                <tr key={org}>
                  <td className="sticky left-0 bg-white px-3 py-2 italic font-medium border-r">
                    {org}
                  </td>
                  {antibiotics.map(([atc]) => {
                    const cell = cellByPair(org, atc);
                    if (!cell || cell.percent_susceptible === null) {
                      return (
                        <td key={atc} className="text-center text-gray-400 px-2 py-2 bg-gray-100">
                          n/a
                        </td>
                      );
                    }
                    const pct = cell.percent_susceptible;
                    const bg = pct >= 80 ? "#a8e6a3" : pct >= 60 ? "#fff2a8" : "#f7b6b6";
                    return (
                      <td
                        key={atc}
                        style={{ backgroundColor: bg }}
                        className="text-center px-2 py-2"
                      >
                        <div className="font-semibold">{pct}%</div>
                        <div className="text-[10px] text-gray-700">n={cell.n_total}</div>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
