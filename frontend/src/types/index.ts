// Phase 6: Alert Detection Engine types
export interface ActiveAlert {
  rule_id: string;
  category: 'Overheating' | 'Battery' | 'Disk' | 'Network' | string;
  severity: 'Info' | 'Warning' | 'Critical' | string;
  message: string;
  metric_name: string;
  metric_value: number;
}

// Phase 7: Natural Language Summary
export interface NLSummary {
  headline: string;
  paragraph: string;
  observations: string[];
  severity: 'Healthy' | 'Warning' | 'Critical' | string;
  generated_in_ms: number;
}

export interface TelemetryData {
  id: string;
  device_id: string;
  timestamp: string;

  // Core performance
  cpu_usage: number;
  memory_usage: number;
  disk_usage: number;
  active_process_count: number;
  cpu_frequency_mhz?: number;

  // Thermals
  cpu_temperature: number;
  fan_speed: number;
  thermal_state?: 'nominal' | 'moderate' | 'critical' | 'serious' | string;

  // GPU
  gpu_usage?: number;
  gpu_temperature?: number;
  gpu_memory_usage?: number;

  // Battery
  battery_level: number;
  battery_health: number;
  battery_temperature?: number;
  cycle_count?: number;
  power_source: 'battery' | 'ac';
  power_draw_watts?: number;
  voltage_mv?: number;

  // Disk I/O
  read_bytes_sec?: number;
  write_bytes_sec?: number;

  // WiFi
  signal_strength_dbm?: number;
  ssid?: string;
  link_speed_mbps?: number;

  // Phase 5: Health Score Engine
  health_score?: number;
  health_category?: 'Healthy' | 'Warning' | 'Critical' | string;
  health_breakdown?: {
    cpu: number;
    memory: number;
    gpu: number;
    temperature: number;
    battery: number;
    disk: number;
    wifi: number;
  };
  health_recommendations?: string[];

  // Phase 6: Alert Detection Engine
  active_alerts?: ActiveAlert[];
  alert_count?: number;

  // Phase 7: NL Summary
  nl_summary?: NLSummary;
}

export interface ChatMessage {
  id: string;
  sender: 'user' | 'twin';
  text: string;
  timestamp: Date;
}
