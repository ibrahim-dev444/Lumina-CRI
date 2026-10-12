-- HDFC Bank's core banking rows (fake core banking CUST_MASTER table, same layout as Axis's).
-- Loaded by:  python manage.py tenant_command load_fake_flexcube --schema=hdfc
-- Synthetic people only. PANs follow the real format but belong to nobody. Suresh Kumar (ABCPK1234F) also
-- banks with Axis: each bank sees only its own copy of him.

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
('HF0000201', 'AMIT VERMA', 'Rajendra Verma', 'M', '+91 98110 22334', 'amit.verma@mail.example', 'C-14 Vasant Kunj, New Delhi 110070', '12 Civil Lines, Jaipur 302006', '1986-04-22', 'AKVPV4321B', '6612 3409 8821', '60011223344551', 'Software engineer', '25 to 50 lakh', '2026-02-11 09:30'),
('HF0000202', 'Pooja  Nair', 'Suresh Nair', 'F', '9820133445', 'pooja.nair@mail.example', 'Flat 9, Marine Lines, Mumbai 400020', 'Thrissur Road, Palakkad 678001', '1991-08-03', 'BPNPN5432C', '7720 1189 3345', '60022334455662', 'Architect', '10 to 25 lakh', '2025-10-05 14:10'),
('HF0000203', 'MOHAMMED IRFAN', 'Abdul Rahim', 'M', '+91-99001 77881', 'irfan.m@mail.example', '19 Frazer Town, Bengaluru 560005', '19 Frazer Town, Bengaluru 560005', '1976-12-15', 'CQRPI6543D', '3398 2210 7781', '60033445566773', 'Restaurant owner', '50 lakh to 1 crore', '2024-06-20 11:00'),
('HF0000204', 'Sneha Patil', 'Vijay Patil', 'F', '9850044556', 'sneha.patil@mail.example', 'Shivaji Nagar, Pune 411005', 'Kolhapur Road, Sangli 416416', '1998-01-27', 'DSTPP7654E', '4410 5563 2209', '60044556677884', 'Student', 'Below 5 lakh', '2026-04-14 10:45'),
('HF0000205', 'Harish Chandra Gupta', 'Om Prakash Gupta', 'M', '9415066778', NULL, 'Hazratganj, Lucknow 226001', 'Chowk, Lucknow 226003', '1963-06-08', 'EUVPG8765F', '8823 4401 6634', '60055667788995', 'Retired', '5 to 10 lakh', '2023-11-30 16:00'),
('HF0000206', 'Deepa Krishnan', 'K Krishnan', 'F', '9445077889', 'deepa.k@mail.example', 'Anna Nagar, Chennai 600040', 'Anna Nagar, Chennai 600040', '1985-10-19', 'FWXPK9876G', '5530 8812 9905', '60066778899106', 'Government officer', '25 to 50 lakh', '2025-08-18 12:20'),
('HF0000207', 'Rohit Malhotra', 'Sunil Malhotra', 'M', '99881 12233', 'rohit.malhotra@mail.example', 'Sector 17, Chandigarh 160017', 'Model Town, Ludhiana 141002', '1982-03-11', 'GYZPM1234H', '9901 2234 5567', '60077889900217', 'Exporter', '50 lakh to 1 crore', '2026-01-09 18:05'),
('HF0000208', 'Suresh Kumar', 'Ramesh Kumar', 'M', '9822155660', 'suresh.kumar@mail.example', 'Baner Road, Pune 411045', 'Plot 7, Sector 21, Nigdi, Pune 411044', '1984-07-12', 'ABCPK1234F', '4821 7730 4521', '60088990011328', 'Business owner', '25 to 50 lakh', '2026-06-03 13:15');
