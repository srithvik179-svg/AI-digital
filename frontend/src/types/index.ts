export interface TelemetryData {
  id: number;
  device_id: string;
  timestamp: string;
  cpu_usage: number;
  memory_usage: number;
  disk_usage: number;
  cpu_temperature: number;
  battery_level: number;
  battery_health: number;
  fan_speed: number;
  power_source: 'battery' | 'ac';
  active_process_count: number;
  metadata_info?: Record<string, any>;
}

export interface ChatMessage {
  id: string;
  sender: 'user' | 'twin';
  text: string;
  timestamp: Date;
}
