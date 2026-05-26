export interface AntibiogramCell {
  organism_taxid: number;
  organism_name: string;
  antibiotic_atc: string;
  antibiotic_name: string;
  drug_class: string | null;
  n_total: number;
  n_susceptible: number;
  percent_susceptible: number | null;
  aware_category: "ACCESS" | "WATCH" | "RESERVE" | null;
}

export interface Antibiogram {
  facility_id: string;
  period_start: string;
  period_end: string;
  stratification: string;
  cells: AntibiogramCell[];
  generated_at: string;
}

export interface Alert {
  alert_id: string;
  facility_id: string;
  organism_taxid: number;
  organism_name: string;
  antibiotic_atc: string | null;
  antibiotic_name: string | null;
  alert_type: string;
  severity: "HIGH" | "MODERATE" | "INVESTIGATE" | "NONE";
  current_rate: number | null;
  baseline_rate: number | null;
  details: Record<string, unknown>;
  acknowledged: boolean;
  triggered_at: string;
  resolved_at: string | null;
}

export interface AgentResponse {
  recommendation: string;
  tools_called: string[];
  confidence_score: number;
  data_provenance: Record<string, unknown>;
  generated_at: string;
}

export interface AuthResponse {
  token: string;
  user: {
    user_id: string;
    email: string;
    facility_id: string;
    role: string;
    name: string;
  };
}
