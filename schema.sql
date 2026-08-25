-- Database Initialization Script for Morocco Maritime & Port Supply Chain Intelligence
-- Target Warehouse: PostgreSQL / Supabase with PostGIS

-- 1. Enable PostGIS Extension if available
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "postgis";

-- 2. Create Staging Schema
CREATE SCHEMA IF NOT EXISTS staging;

-- 3. Create Staging Table: staging.stg_vessel_ais_raw
CREATE TABLE IF NOT EXISTS staging.stg_vessel_ais_raw (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mmsi VARCHAR(20) NOT NULL,
    imo VARCHAR(20),
    vessel_name VARCHAR(150) NOT NULL,
    vessel_type VARCHAR(50),
    flag_country VARCHAR(50),
    latitude NUMERIC(10, 6) NOT NULL,
    longitude NUMERIC(10, 6) NOT NULL,
    speed_knots NUMERIC(5, 2) NOT NULL,
    heading NUMERIC(5, 2),
    nav_status VARCHAR(50),
    destination VARCHAR(100),
    eta TIMESTAMP WITH TIME ZONE,
    timestamp_utc TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 4. Create Indexes for Operational & Analytical Queries
CREATE INDEX IF NOT EXISTS idx_stg_vessel_ais_mmsi ON staging.stg_vessel_ais_raw (mmsi);
CREATE INDEX IF NOT EXISTS idx_stg_vessel_ais_timestamp ON staging.stg_vessel_ais_raw (timestamp_utc DESC);
CREATE INDEX IF NOT EXISTS idx_stg_vessel_ais_vessel_type ON staging.stg_vessel_ais_raw (vessel_type);
CREATE INDEX IF NOT EXISTS idx_stg_vessel_ais_mmsi_ts ON staging.stg_vessel_ais_raw (mmsi, timestamp_utc DESC);

-- 5. PostGIS Spatial Index (EPSG:4326 WGS 84)
-- Note: Geometry column generated dynamically or computed via spatial index expression
CREATE INDEX IF NOT EXISTS idx_stg_vessel_ais_geom ON staging.stg_vessel_ais_raw 
USING GIST (ST_SetSRID(ST_MakePoint(longitude, latitude), 4326));
