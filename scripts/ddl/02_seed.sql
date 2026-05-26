-- Seed data for development. Idempotent — safe to re-run.

INSERT INTO facilities (facility_id, name, country_iso3, region, facility_type)
VALUES
    ('FACILITY_001', 'Demo General Hospital', 'USA', 'North America', 'hospital'),
    ('FACILITY_002', 'Demo University Medical Center', 'GBR', 'Europe', 'hospital'),
    ('FACILITY_003', 'Demo Regional Reference Lab', 'IND', 'South Asia', 'reference_lab')
ON CONFLICT (facility_id) DO NOTHING;

INSERT INTO wards (ward_id, facility_id, name, ward_type)
VALUES
    ('WARD_001_ICU',     'FACILITY_001', 'ICU',         'ICU'),
    ('WARD_001_GEN',     'FACILITY_001', 'General',     'general'),
    ('WARD_001_SURG',    'FACILITY_001', 'Surgical',    'surgical'),
    ('WARD_001_PED',     'FACILITY_001', 'Pediatrics',  'pediatric'),
    ('WARD_002_ICU',     'FACILITY_002', 'ICU',         'ICU'),
    ('WARD_002_GEN',     'FACILITY_002', 'General',     'general'),
    ('WARD_003_REF',     'FACILITY_003', 'Reference',   'general')
ON CONFLICT (ward_id) DO NOTHING;

-- bcrypt hash of "demo_password" — for development only.
INSERT INTO users (facility_id, email, password_hash, role, name)
VALUES
    ('FACILITY_001',
     'demo@amrsentinel.org',
     '$2a$10$N9qo8uLOickgx2ZMRZoMyeIjZAgcfl7p92ldGxad68LJZdL17lhWy',
     'admin',
     'Demo Admin')
ON CONFLICT (email) DO NOTHING;
