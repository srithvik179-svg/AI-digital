-- Step 1: Create telemetry_snapshots
CREATE TABLE IF NOT EXISTS telemetry_snapshots (
    id VARCHAR(36) PRIMARY KEY,
    device_id VARCHAR(255) NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Step 2: Create child metrics tables
CREATE TABLE IF NOT EXISTS cpu_metrics (
    snapshot_id VARCHAR(36) PRIMARY KEY REFERENCES telemetry_snapshots(id) ON DELETE CASCADE,
    cpu_usage REAL NOT NULL CHECK (cpu_usage >= 0.0 AND cpu_usage <= 100.0),
    active_process_count INTEGER NOT NULL CHECK (active_process_count >= 0),
    cpu_frequency_mhz REAL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS gpu_metrics (
    snapshot_id VARCHAR(36) PRIMARY KEY REFERENCES telemetry_snapshots(id) ON DELETE CASCADE,
    gpu_usage REAL NOT NULL CHECK (gpu_usage >= 0.0 AND gpu_usage <= 100.0),
    gpu_temperature REAL,
    gpu_memory_usage REAL CHECK (gpu_memory_usage >= 0.0 AND gpu_memory_usage <= 100.0),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS memory_metrics (
    snapshot_id VARCHAR(36) PRIMARY KEY REFERENCES telemetry_snapshots(id) ON DELETE CASCADE,
    memory_usage REAL NOT NULL CHECK (memory_usage >= 0.0 AND memory_usage <= 100.0),
    total_mb REAL,
    used_mb REAL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS battery_metrics (
    snapshot_id VARCHAR(36) PRIMARY KEY REFERENCES telemetry_snapshots(id) ON DELETE CASCADE,
    battery_level REAL NOT NULL CHECK (battery_level >= 0.0 AND battery_level <= 100.0),
    battery_health REAL NOT NULL CHECK (battery_health >= 0.0 AND battery_health <= 100.0),
    battery_temperature REAL,
    cycle_count INTEGER CHECK (cycle_count >= 0),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS disk_metrics (
    snapshot_id VARCHAR(36) PRIMARY KEY REFERENCES telemetry_snapshots(id) ON DELETE CASCADE,
    disk_usage REAL NOT NULL CHECK (disk_usage >= 0.0 AND disk_usage <= 100.0),
    read_bytes_sec BIGINT,
    write_bytes_sec BIGINT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS wifi_metrics (
    snapshot_id VARCHAR(36) PRIMARY KEY REFERENCES telemetry_snapshots(id) ON DELETE CASCADE,
    signal_strength_dbm INTEGER CHECK (signal_strength_dbm <= 0 AND signal_strength_dbm >= -100),
    ssid VARCHAR(255),
    link_speed_mbps INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS thermal_metrics (
    snapshot_id VARCHAR(36) PRIMARY KEY REFERENCES telemetry_snapshots(id) ON DELETE CASCADE,
    cpu_temperature REAL NOT NULL,
    fan_speed_rpm INTEGER NOT NULL CHECK (fan_speed_rpm >= 0),
    thermal_state VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS power_metrics (
    snapshot_id VARCHAR(36) PRIMARY KEY REFERENCES telemetry_snapshots(id) ON DELETE CASCADE,
    power_source VARCHAR(50) NOT NULL CHECK (power_source IN ('battery', 'ac')),
    power_draw_watts REAL,
    voltage_mv REAL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Step 3: Performance Indices
CREATE INDEX IF NOT EXISTS idx_snapshots_device_timestamp ON telemetry_snapshots (device_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_snapshots_timestamp ON telemetry_snapshots (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_thermal_state ON thermal_metrics (thermal_state) WHERE thermal_state IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_battery_level ON battery_metrics (battery_level);
CREATE INDEX IF NOT EXISTS idx_cpu_temperature ON thermal_metrics (cpu_temperature);
CREATE INDEX IF NOT EXISTS idx_cpu_usage ON cpu_metrics (cpu_usage);

-- Step 4: Data Migration (from old telemetry_records table to new normalized tables)
DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'telemetry_records') THEN
        -- Insert into telemetry_snapshots
        INSERT INTO telemetry_snapshots (id, device_id, timestamp, created_at)
        SELECT 
            COALESCE((metadata_info->>'uuid'), md5(id::text || timestamp::text)::uuid::text),
            device_id, 
            timestamp, 
            timestamp
        FROM telemetry_records;

        -- Insert into cpu_metrics
        INSERT INTO cpu_metrics (snapshot_id, cpu_usage, active_process_count, cpu_frequency_mhz)
        SELECT 
            COALESCE((metadata_info->>'uuid'), md5(id::text || timestamp::text)::uuid::text),
            cpu_usage,
            active_process_count,
            COALESCE((metadata_info->>'cpu_frequency_mhz')::real, 2400.0)
        FROM telemetry_records;

        -- Insert into gpu_metrics
        INSERT INTO gpu_metrics (snapshot_id, gpu_usage, gpu_temperature, gpu_memory_usage)
        SELECT 
            COALESCE((metadata_info->>'uuid'), md5(id::text || timestamp::text)::uuid::text),
            COALESCE((metadata_info->>'gpu_usage')::real, 0.0),
            COALESCE((metadata_info->>'gpu_temperature')::real, cpu_temperature - 2.0),
            COALESCE((metadata_info->>'gpu_memory_usage')::real, 0.0)
        FROM telemetry_records;

        -- Insert into memory_metrics
        INSERT INTO memory_metrics (snapshot_id, memory_usage, total_mb, used_mb)
        SELECT 
            COALESCE((metadata_info->>'uuid'), md5(id::text || timestamp::text)::uuid::text),
            memory_usage,
            16384.0,
            16384.0 * (memory_usage / 100.0)
        FROM telemetry_records;

        -- Insert into battery_metrics
        INSERT INTO battery_metrics (snapshot_id, battery_level, battery_health, battery_temperature, cycle_count)
        SELECT 
            COALESCE((metadata_info->>'uuid'), md5(id::text || timestamp::text)::uuid::text),
            battery_level,
            battery_health,
            COALESCE((metadata_info->>'battery_temperature')::real, 30.0),
            COALESCE((metadata_info->>'cycle_count')::integer, 120)
        FROM telemetry_records;

        -- Insert into disk_metrics
        INSERT INTO disk_metrics (snapshot_id, disk_usage, read_bytes_sec, write_bytes_sec)
        SELECT 
            COALESCE((metadata_info->>'uuid'), md5(id::text || timestamp::text)::uuid::text),
            disk_usage,
            0,
            0
        FROM telemetry_records;

        -- Insert into wifi_metrics
        INSERT INTO wifi_metrics (snapshot_id, signal_strength_dbm, ssid, link_speed_mbps)
        SELECT 
            COALESCE((metadata_info->>'uuid'), md5(id::text || timestamp::text)::uuid::text),
            COALESCE((metadata_info->>'signal_strength_dbm')::integer, -50),
            COALESCE(metadata_info->>'ssid', 'Dell_Secure_WiFi'),
            COALESCE((metadata_info->>'link_speed_mbps')::integer, 866)
        FROM telemetry_records;

        -- Insert into thermal_metrics
        INSERT INTO thermal_metrics (snapshot_id, cpu_temperature, fan_speed_rpm, thermal_state)
        SELECT 
            COALESCE((metadata_info->>'uuid'), md5(id::text || timestamp::text)::uuid::text),
            cpu_temperature,
            fan_speed,
            CASE 
                WHEN cpu_temperature >= 85.0 THEN 'critical'
                WHEN cpu_temperature >= 75.0 THEN 'serious'
                WHEN cpu_temperature >= 60.0 THEN 'fair'
                ELSE 'nominal'
            END
        FROM telemetry_records;

        -- Insert into power_metrics
        INSERT INTO power_metrics (snapshot_id, power_source, power_draw_watts, voltage_mv)
        SELECT 
            COALESCE((metadata_info->>'uuid'), md5(id::text || timestamp::text)::uuid::text),
            power_source,
            CASE WHEN power_source = 'ac' THEN 15.0 ELSE 8.5 END,
            12000.0
        FROM telemetry_records;

        -- Drop the old table
        DROP TABLE telemetry_records;
    END IF;
END $$;
