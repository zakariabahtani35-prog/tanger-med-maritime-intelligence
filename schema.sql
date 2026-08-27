-- Database Initialization Script for Morocco Maritime & Port Supply Chain Intelligence
-- Target Warehouse: Supabase / PostgreSQL + PostGIS

-- 1. Enable PostGIS Extension if available
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "postgis";

-- 2. Staging Table: public.stg_vessel_ais_raw
CREATE TABLE IF NOT EXISTS public.stg_vessel_ais_raw (
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

-- 3. Dimension Table: public.dim_vessels
CREATE TABLE IF NOT EXISTS public.dim_vessels (
    mmsi VARCHAR(20) PRIMARY KEY,
    imo VARCHAR(20),
    vessel_name VARCHAR(150) NOT NULL,
    vessel_type VARCHAR(50) NOT NULL,
    flag_country VARCHAR(50),
    first_seen_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 4. Fact Table: public.fact_vessel_movements
CREATE TABLE IF NOT EXISTS public.fact_vessel_movements (
    movement_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mmsi VARCHAR(20) NOT NULL REFERENCES public.dim_vessels(mmsi) ON DELETE CASCADE,
    vessel_name VARCHAR(150) NOT NULL,
    vessel_type VARCHAR(50) NOT NULL,
    latitude NUMERIC(10, 6) NOT NULL,
    longitude NUMERIC(10, 6) NOT NULL,
    speed_knots NUMERIC(5, 2) NOT NULL,
    heading NUMERIC(5, 2),
    nav_status VARCHAR(50),
    destination VARCHAR(100),
    port_code VARCHAR(10), -- 'MAPTM' (Tanger Med) or 'MACAS' (Casablanca)
    is_at_berth BOOLEAN DEFAULT FALSE,
    is_at_anchor BOOLEAN DEFAULT FALSE,
    predicted_dwell_hours NUMERIC(6, 2),
    anomaly_score NUMERIC(5, 3),
    is_anomaly BOOLEAN DEFAULT FALSE,
    timestamp_utc TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Schema Migration: Ensure columns exist if table was already created
ALTER TABLE public.fact_vessel_movements 
ADD COLUMN IF NOT EXISTS predicted_dwell_hours NUMERIC(6, 2),
ADD COLUMN IF NOT EXISTS anomaly_score NUMERIC(5, 3),
ADD COLUMN IF NOT EXISTS is_anomaly BOOLEAN DEFAULT FALSE;

-- 5. Fact Table: public.fact_port_dwell_time
CREATE TABLE IF NOT EXISTS public.fact_port_dwell_time (
    dwell_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mmsi VARCHAR(20) NOT NULL REFERENCES public.dim_vessels(mmsi) ON DELETE CASCADE,
    port_code VARCHAR(10) NOT NULL, -- 'MAPTM' or 'MACAS'
    port_name VARCHAR(100) NOT NULL,
    arrival_time TIMESTAMP WITH TIME ZONE NOT NULL,
    departure_time TIMESTAMP WITH TIME ZONE,
    dwell_hours NUMERIC(8, 2),
    status VARCHAR(50) DEFAULT 'BERTHED',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 6. Create Indexes for High-Speed Query Performance
CREATE INDEX IF NOT EXISTS idx_stg_vessel_ais_mmsi ON public.stg_vessel_ais_raw (mmsi);
CREATE INDEX IF NOT EXISTS idx_stg_vessel_ais_timestamp ON public.stg_vessel_ais_raw (timestamp_utc DESC);
CREATE INDEX IF NOT EXISTS idx_fact_movements_mmsi_ts ON public.fact_vessel_movements (mmsi, timestamp_utc DESC);
CREATE INDEX IF NOT EXISTS idx_fact_movements_port_code ON public.fact_vessel_movements (port_code);
CREATE INDEX IF NOT EXISTS idx_fact_movements_berth_anchor ON public.fact_vessel_movements (port_code, is_at_berth, is_at_anchor);
CREATE INDEX IF NOT EXISTS idx_dim_vessels_type ON public.dim_vessels (vessel_type);
CREATE INDEX IF NOT EXISTS idx_fact_dwell_port ON public.fact_port_dwell_time (port_code, status);

-- 7. PostGIS Spatial Index (EPSG:4326 WGS 84)
CREATE INDEX IF NOT EXISTS idx_stg_vessel_ais_geom ON public.stg_vessel_ais_raw 
USING GIST (ST_SetSRID(ST_MakePoint(longitude, latitude), 4326));

CREATE INDEX IF NOT EXISTS idx_fact_movements_geom ON public.fact_vessel_movements 
USING GIST (ST_SetSRID(ST_MakePoint(longitude, latitude), 4326));
