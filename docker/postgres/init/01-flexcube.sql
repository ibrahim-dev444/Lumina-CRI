-- Creates the empty fake core banking database. Docker runs this once, when the data volume is first created.
-- Each organization's rows are loaded into their own schema by:
--   python manage.py tenant_command load_fake_flexcube --schema=<org>
-- using fake_sources/<org>/flexcube.sql.

CREATE DATABASE src_flexcube;
