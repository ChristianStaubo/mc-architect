-- The ghost's own database (Temporal makes its own two). The ops room reads through ghost_ops,
-- which is granted SELECT only (ghost/db.py sets its password and grants after migrating).
CREATE DATABASE ghost_app OWNER ghost;
CREATE ROLE ghost_ops LOGIN;
