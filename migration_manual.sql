-- ETAP 2 - Initial Database Schema Migration
-- Execute this SQL in Supabase SQL Editor (https://supabase.com/dashboard/project/_/sql/new)
-- This creates the plans and plan_versions tables for trip planning system

BEGIN;

-- Create alembic version tracking table
CREATE TABLE IF NOT EXISTS alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Create plans table (stores trip metadata)
CREATE TABLE plans (
    id UUID NOT NULL, 
    location VARCHAR NOT NULL, 
    group_type VARCHAR NOT NULL, 
    days_count INTEGER NOT NULL, 
    budget_level INTEGER NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    trip_metadata JSON NOT NULL, 
    PRIMARY KEY (id)
);

-- Create plan_versions table (stores version history and snapshots)
CREATE TABLE plan_versions (
    id UUID NOT NULL, 
    plan_id UUID NOT NULL, 
    version_number INTEGER NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    change_type VARCHAR NOT NULL, 
    parent_version_id UUID, 
    days_json JSON NOT NULL, 
    change_summary TEXT, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_plan_version UNIQUE (plan_id, version_number), 
    FOREIGN KEY(plan_id) REFERENCES plans (id) ON DELETE CASCADE, 
    FOREIGN KEY(parent_version_id) REFERENCES plan_versions (id)
);

-- Create performance indexes
CREATE INDEX ix_plan_versions_plan_id ON plan_versions (plan_id);
CREATE INDEX ix_plan_versions_version_number ON plan_versions (version_number);

-- Mark migration as applied
INSERT INTO alembic_version (version_num) VALUES ('360e3cae0377');

COMMIT;

-- Verification query (run separately after migration)
-- SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name;
