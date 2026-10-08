-- Fake FLEXCUBE core banking system.
-- Column names copy the Oracle style on purpose, so connectors must map them
-- to Lumina's standard fields (name, mobile, email, address, dob).
-- Data is deliberately messy: odd spacing, +91 prefixes, upper case, a missing email.

CREATE DATABASE src_flexcube;
\connect src_flexcube

CREATE TABLE "CUST_MASTER" (
    "CUST_ID"     VARCHAR(12) PRIMARY KEY,
    "CUST_NAME"   VARCHAR(100) NOT NULL,
    "MOB_NO"      VARCHAR(20),
    "EMAIL_ID"    VARCHAR(100),
    "ADDR1"       VARCHAR(200),
    "DOB"         DATE,
    "PAN_NO"      VARCHAR(10),
    "LAST_UPD_DT" TIMESTAMP NOT NULL DEFAULT now()
);

INSERT INTO "CUST_MASTER" ("CUST_ID", "CUST_NAME", "MOB_NO", "EMAIL_ID", "ADDR1", "DOB", "PAN_NO", "LAST_UPD_DT") VALUES
('FX0000101', 'SURESH KUMAR',      '+91 98221 04521', 'suresh.kumar@mail.example',     '14 Shanti Apts., Kothrud, Pune 411038',              '1984-07-12', 'ABCPK1234F', '2025-11-02 10:15'),
('FX0000102', 'Anita  Deshmukh',   '9890012345',      'anita.d@mail.example',          'B-203 Lake View, Powai, Mumbai 400076',              '1990-03-05', 'BDEPD2345G', '2026-01-18 16:40'),
('FX0000103', 'Rajesh R Iyer',     '098450-98450',    'rajesh.iyer@mail.example',      '42 Cathedral Road, Gopalapuram, Chennai 600086',     '1972-11-21', 'CFGPI3456H', '2024-08-30 09:05'),
('FX0000104', 'FARAH SHEIKH',      '9967033441',      NULL,                            '5 Hill Road, Bandra West, Mumbai 400050',            '1993-05-14', 'DGHPS4567J', '2025-06-11 12:00'),
('FX0000105', 'Gurpreet Sandhu',   '+919815567001',   'gurpreet.sandhu@mail.example',  'House 310, Sector 35, Chandigarh 160022',            '1979-01-30', 'EHJPS5678K', '2026-03-02 11:20'),
('FX0000106', 'Nandini V Rao',     '9741200765',      'NRAO@CLINIC.EXAMPLE',           '77 12th Main, Indiranagar, Bengaluru 560038',        '1981-09-09', 'FJKPR6789L', '2025-12-24 15:45'),
('FX0000107', 'Joseph Mathew',     '94470 11882',     'joseph.mathew@mail.example',    'Rose Villa, Kadavanthra, Kochi 682020',              '1987-12-01', 'GKLPM7890M', '2025-02-07 10:10'),
('FX0000108', 'Kavitha Joshi',     '9925044170',      'kavita.joshi@mail.example',     '12 Satellite Road, Ahmedabad 380015',                '1995-02-17', 'HLMPJ8901N', '2026-05-29 17:30'),
('FX0000109', 'Mohd Faisal',       '9849077563',      'm.faizal@mail.example',         '8-2-120 Road No 3, Banjara Hills, Hyderabad 500034', '1989-06-25', 'JMNPF9012P', '2024-12-12 13:00'),
('FX0000110', 'Priya Chatterjee',  '9830045127',      'priya.chatterjee@mail.example', '21 Ballygunge Place, Kolkata 700019',                '1986-04-03', 'KNPPC0123Q', '2026-07-15 09:50');
