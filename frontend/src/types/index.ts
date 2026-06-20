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

  // Phase 17: Virtual Twin State
  twin_state?: VirtualTwinState;
}

export interface VirtualTwinState {
  device_id: string;
  overall_health: {
    score: number | null;
    category: string | null;
  };
  components: {
    cpu: {
      current_usage: number;
      active_process_count: number;
      frequency_mhz?: number | null;
      rolling_load_average: number;
    };
    gpu: {
      current_usage: number;
      temperature?: number | null;
      memory_usage?: number | null;
    };
    ram: {
      current_usage: number;
    };
    battery: {
      level: number;
      health: number;
      temperature?: number | null;
      cycle_count: number;
      power_source: string;
      projected_wear_percentage: number;
      projected_remaining_health_days: number;
    };
    disk: {
      usage: number;
      read_bytes_sec: number;
      write_bytes_sec: number;
      estimated_wear_accumulated_tb: number;
    };
    wifi: {
      signal_strength_dbm?: number | null;
      ssid?: string | null;
      link_speed_mbps?: number | null;
    };
    thermal: {
      cpu_temperature: number;
      fan_speed_rpm: number;
      thermal_state?: string | null;
      target_fan_speed_rpm: number;
    };
  };
}

export interface ChatMessage {
  id: string;
  sender: 'user' | 'twin';
  text: string;
  timestamp: Date;
}

// Phase 14: Telemetry Relationship Graph types
export interface RelationshipNode {
  id: string;
  label: string;
  description: string;
}

export interface RelationshipEdge {
  source: string;
  target: string;
  relationship_type: string;
  correlation_strength: number;
  description: string;
}

export interface RelationshipGraph {
  device_id: string;
  nodes: RelationshipNode[];
  edges: RelationshipEdge[];
  total_records_analyzed: number;
}

// Phase 21: Rule-Based Reasoning Engine types
export interface RuleCondition {
  metric: string;
  operator: string;
  value: number | string;
}

export interface ReasoningRule {
  id: string;
  name: string;
  description?: string;
  conditions: RuleCondition[];
  logical_operator: 'AND' | 'OR' | string;
  conclusion: string;
  severity: 'info' | 'warning' | 'critical' | string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface RuleEvaluationResult {
  rule_id: string;
  rule_name: string;
  triggered: boolean;
  explanation: string;
  evidence: Record<string, any>;
  severity: string;
}

