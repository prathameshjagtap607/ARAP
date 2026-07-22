-- Dev seed: creates test org + admin user + regular user
-- Password for both accounts: Test@1234
-- Run: docker exec -i <db-container> psql -U arap -d arap_dev < scripts/seed-dev.sql

INSERT INTO orgs (id, name, plan_tier)
VALUES ('00000000-0000-0000-0000-000000000001', 'Fidelitus Corp', 'trial')
ON CONFLICT DO NOTHING;

INSERT INTO users (org_id, email, role, password_hash)
VALUES
  ('00000000-0000-0000-0000-000000000001', 'admin@fidelitus.com', 'admin',
   '$2b$12$K8BpSMcmCPMjCCn1DdMQBu5V3iFpIZEnfHyXFMqKfFJOhpvPBJ5fi'),
  ('00000000-0000-0000-0000-000000000001', 'user@fidelitus.com',  'user',
   '$2b$12$K8BpSMcmCPMjCCn1DdMQBu5V3iFpIZEnfHyXFMqKfFJOhpvPBJ5fi')
ON CONFLICT DO NOTHING;
