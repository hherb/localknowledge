CREATE ROLE readonly_user WITH LOGIN PASSWORD 'yourpassword';
GRANT CONNECT ON DATABASE  knowledgebase TO readonly_user;
GRANT USAGE ON SCHEMA public TO readonly_user;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO readonly_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO readonly_user;