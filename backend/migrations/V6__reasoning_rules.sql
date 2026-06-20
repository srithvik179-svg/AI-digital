-- Phase 21: Rule-Based Reasoning Engine — dynamic rules schema

CREATE TABLE IF NOT EXISTS reasoning_rules (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    conditions JSONB NOT NULL,
    logical_operator VARCHAR(10) NOT NULL DEFAULT 'AND',
    conclusion VARCHAR(255) NOT NULL,
    severity VARCHAR(20) NOT NULL DEFAULT 'info',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Index active rules for fast retrieval during telemetry evaluation
CREATE INDEX IF NOT EXISTS idx_reasoning_rules_active
    ON reasoning_rules (is_active);

-- Seed initial default rules
INSERT INTO reasoning_rules (id, name, description, conditions, logical_operator, conclusion, severity, is_active, created_at, updated_at)
VALUES 
(
    'rule-thermal-stress',
    'Thermal Stress Detection',
    'Triggers when CPU load is high and temperature is hot.',
    '[{"metric": "cpu_usage", "operator": ">", "value": 80.0}, {"metric": "cpu_temperature", "operator": ">", "value": 85.0}]',
    'AND',
    'Thermal Stress',
    'critical',
    TRUE,
    NOW(),
    NOW()
),
(
    'rule-system-overload',
    'System Overload',
    'Triggers when both CPU and memory usages are extremely high.',
    '[{"metric": "cpu_usage", "operator": ">", "value": 90.0}, {"metric": "memory_usage", "operator": ">", "value": 85.0}]',
    'AND',
    'System Overload',
    'critical',
    TRUE,
    NOW(),
    NOW()
),
(
    'rule-eco-warning',
    'Low Battery AC Recommendation',
    'Triggers when battery is low and running on battery power.',
    '[{"metric": "battery_level", "operator": "<", "value": 20.0}, {"metric": "power_source", "operator": "==", "value": "battery"}]',
    'AND',
    'Low Power Mode Recommended',
    'warning',
    TRUE,
    NOW(),
    NOW()
),
(
    'rule-unstable-wifi',
    'Weak WiFi Connection',
    'Triggers when signal strength is very weak.',
    '[{"metric": "signal_strength_dbm", "operator": "<", "value": -80.0}]',
    'AND',
    'Weak WiFi Connection',
    'warning',
    TRUE,
    NOW(),
    NOW()
)
ON CONFLICT (id) DO NOTHING;

COMMENT ON TABLE reasoning_rules IS 'Dynamic user-defined and default rules for Phase 21 Rule-Based Reasoning Engine';
