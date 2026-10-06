-- Read access for the app service principal (Genie answers run as the app SP).
-- Placeholders: {catalog}, {app_sp}
GRANT USE CATALOG ON CATALOG {catalog} TO `{app_sp}`;
GRANT USE SCHEMA, SELECT ON SCHEMA {catalog}.pdm_core TO `{app_sp}`;
GRANT USE SCHEMA, SELECT ON SCHEMA {catalog}.pdm_ops TO `{app_sp}`;
GRANT USE SCHEMA ON SCHEMA {catalog}.pdm_raw TO `{app_sp}`;
GRANT SELECT ON TABLE {catalog}.pdm_raw.station_master TO `{app_sp}`;
