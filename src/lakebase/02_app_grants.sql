-- Least privilege for the app's Postgres role (the app service principal client id).
-- Placeholder {app_role}. Run after the app exists and after the synced tables are ONLINE.
GRANT USAGE ON SCHEMA pdm_ops TO "{app_role}";
GRANT SELECT, INSERT, UPDATE ON pdm_ops.work_orders TO "{app_role}";
GRANT SELECT, INSERT ON pdm_ops.sim_commands TO "{app_role}";
GRANT USAGE ON SCHEMA pdm_live TO "{app_role}";
GRANT SELECT ON ALL TABLES IN SCHEMA pdm_live TO "{app_role}";
