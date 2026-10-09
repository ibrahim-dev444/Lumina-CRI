-- Fake FLEXCUBE core banking system.
-- Docker runs this file once, when the database volume is first created. To reload it into an existing
-- database, run:  python manage.py load_fake_flexcube   (it reuses everything below the \connect line).
--
-- Column names copy the Oracle style on purpose, so connectors must map them to Lumina's fields.
-- Data is deliberately messy: odd spacing, +91 prefixes, upper case, gender codes, a missing email.
-- Identity numbers are FAKE: PANs follow the real format but belong to nobody; Aadhaar numbers here
-- are random 12-digit strings (Lumina keeps only the last 4 digits of them).

CREATE DATABASE src_flexcube;
\connect src_flexcube

DROP TABLE IF EXISTS "CUST_MASTER";
CREATE TABLE "CUST_MASTER" (
    "CUST_ID"       VARCHAR(12) PRIMARY KEY,
    "CUST_NAME"     VARCHAR(100) NOT NULL,
    "FATHER_NAME"   VARCHAR(100),
    "GENDER"        VARCHAR(1),
    "MOB_NO"        VARCHAR(20),
    "EMAIL_ID"      VARCHAR(100),
    "ADDR1"         VARCHAR(200),
    "PERM_ADDR"     VARCHAR(200),
    "DOB"           DATE,
    "PAN_NO"        VARCHAR(10),
    "AADHAAR_NO"    VARCHAR(14),
    "CKYC_NO"       VARCHAR(14),
    "OCCUPATION"    VARCHAR(60),
    "ANNUAL_INCOME" VARCHAR(40),
    "LAST_UPD_DT"   TIMESTAMP NOT NULL DEFAULT now()
);

INSERT INTO "CUST_MASTER" ("CUST_ID", "CUST_NAME", "FATHER_NAME", "GENDER", "MOB_NO", "EMAIL_ID", "ADDR1", "PERM_ADDR", "DOB", "PAN_NO", "AADHAAR_NO", "CKYC_NO", "OCCUPATION", "ANNUAL_INCOME", "LAST_UPD_DT") VALUES
('FX0000101', 'SURESH KUMAR',     'Ramesh Kumar',          'M', '+91 98221 04521', 'suresh.kumar@mail.example',     '14 Shanti Apts., Kothrud, Pune 411038',              'Plot 7, Sector 21, Nigdi, Pune 411044',            '1984-07-12', 'ABCPK1234F', '4821 7730 4521', '50012345678821', 'Business owner',       '25 to 50 lakh',   '2025-11-02 10:15'),
('FX0000102', 'Anita  Deshmukh',  'Shripad Deshmukh',      'F', '9890012345',      'anita.d@mail.example',          'B-203 Lake View, Powai, Mumbai 400076',              '22 Tilak Road, Nashik 422001',                     '1990-03-05', 'BDEPD2345G', '3310 9921 7719', '50023456789104', 'Salaried',             '10 to 25 lakh',   '2026-01-18 16:40'),
('FX0000103', 'Rajesh R Iyer',    'Ramanathan Iyer',       'M', '098450-98450',    'rajesh.iyer@mail.example',      '42 Cathedral Road, Gopalapuram, Chennai 600086',     '9 Lake Area, Nungambakkam, Chennai 600034',        '1972-11-21', 'CFGPI3456H', '7702 4410 3308', '50034567890217', 'Chartered accountant', '50 lakh to 1 crore', '2024-08-30 09:05'),
('FX0000104', 'FARAH SHEIKH',     'Imtiaz Sheikh',         'F', '9967033441',      NULL,                            '5 Hill Road, Bandra West, Mumbai 400050',            '18 Station Road, Thane 400601',                    '1993-05-14', 'DGHPS4567J', '5519 2087 6642', '50045678901336', 'Salaried',             '5 to 10 lakh',    '2025-06-11 12:00'),
('FX0000105', 'Gurpreet Sandhu',  'Harbhajan Singh Sandhu','M', '+919815567001',   'gurpreet.sandhu@mail.example',  'House 310, Sector 35, Chandigarh 160022',            'Village Road, Kharar, Mohali 140301',              '1979-01-30', 'EHJPS5678K', '6620 1145 9015', '50056789012448', 'Agri business',        '25 to 50 lakh',   '2026-03-02 11:20'),
('FX0000106', 'Nandini V Rao',    'Venkatesh Rao',         'F', '9741200765',      'NRAO@CLINIC.EXAMPLE',           '77 12th Main, Indiranagar, Bengaluru 560038',        '3 Temple Street, Malleshwaram, Bengaluru 560003',  '1981-09-09', 'FJKPR6789L', '2208 6631 2276', '50067890123559', 'Doctor',               '50 lakh to 1 crore', '2025-12-24 15:45'),
('FX0000107', 'Joseph Mathew',    'Mathew Varghese',       'M', '94470 11882',     'joseph.mathew@mail.example',    'Rose Villa, Kadavanthra, Kochi 682020',              'MC Road, Kottayam 686001',                         '1987-12-01', 'GKLPM7890M', '9014 3376 5580', '50078901234662', 'Salaried',             '10 to 25 lakh',   '2025-02-07 10:10'),
('FX0000108', 'Kavitha Joshi',    'Ramesh Joshi',          'F', '9925044170',      'kavita.joshi@mail.example',     '12 Satellite Road, Ahmedabad 380015',                'Ring Road, Rajkot 360001',                         '1995-02-17', 'HLMPJ8901N', '1187 5502 4417', '50089012345773', 'Teacher',              '5 to 10 lakh',    '2026-05-29 17:30'),
('FX0000109', 'Mohd Faisal',      'Abdul Faisal',          'M', '9849077563',      'm.faizal@mail.example',         '8-2-120 Road No 3, Banjara Hills, Hyderabad 500034', 'Charminar Road, Hyderabad 500002',                 '1989-06-25', 'JMNPF9012P', '4476 0913 7756', '50090123456884', 'Retail business',      '10 to 25 lakh',   '2024-12-12 13:00'),
('FX0000110', 'Priya Chatterjee', 'Subrata Chatterjee',    'F', '9830045127',      'priya.chatterjee@mail.example', '21 Ballygunge Place, Kolkata 700019',                'Salt Lake Sector 2, Kolkata 700091',               '1986-04-03', 'KNPPC0123Q', '8135 2240 8134', '50001234567995', 'Architect',            '25 to 50 lakh',   '2026-07-15 09:50');
