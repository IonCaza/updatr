export interface Host {
  id: string;
  display_name: string;
  hostname: string;
  os_type: "windows" | "linux" | "truenas" | "proxmox";
  ssh_port: number;
  winrm_port: number;
  winrm_use_ssl: boolean;
  site: string;
  is_self: boolean;
  worker_override: string | null;
  tags: string[];
  credential_id: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Credential {
  id: string;
  name: string;
  type: "ssh-password" | "ssh-key" | "winrm-password";
  username: string;
  created_at: string;
  updated_at: string;
}

export interface Job {
  id: string;
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  job_type: "patch" | "compliance";
  host_ids: string[];
  tags_filter: string[];
  patch_categories: string[];
  reboot_policy: "auto" | "never" | "if-required";
  schedule_id: string | null;
  started_at: string | null;
  completed_at: string | null;
  host_results: Record<string, unknown>;
  created_at: string;
}

export interface Schedule {
  id: string;
  name: string;
  cron_expression: string;
  host_ids: string[] | null;
  tags_filter: string[] | null;
  patch_categories: string[];
  reboot_policy: "auto" | "never" | "if-required";
  is_active: boolean;
  last_run_at: string | null;
  next_run_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ComplianceSummary {
  total_hosts: number;
  compliant: number;
  non_compliant: number;
  reboot_required: number;
  unreachable: number;
  last_scan_at: string | null;
}
