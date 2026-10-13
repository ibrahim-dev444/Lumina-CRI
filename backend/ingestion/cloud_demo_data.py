"""Synthetic customers for the cloud demo sources (Phase 6). Nobody here is a real person.

Each bank's systems overlap on purpose, so matching and review have real work to do:
- the same four people in every system of that bank, under the same PAN (they merge automatically);
- one of them moved and changed phone number, but only the mobile app knows (newer value wins);
- a duplicate account with a typo in the name and no PAN in core banking (goes to match review);
- one person without a PAN in two systems, spelled differently (goes to match review);
- a family member sharing a phone number but with a different name (never merged).
Seeds: 1 = core banking on PostgreSQL, 2 = core banking on MySQL, 3 = mobile app on MongoDB.
Generated from fixed lists, so every run produces exactly the same rows.
"""

CORE_SEEDS = (1, 2)
APP_SEED = 3

FIRST = [
    "Aarav", "Diya", "Kabir", "Meera", "Rohan", "Isha", "Vikram", "Ananya", "Arjun", "Kavya", "Siddharth", "Nisha",
    "Rahul", "Pooja", "Karthik", "Sneha", "Aditya", "Riya", "Manish", "Lakshmi", "Varun", "Tanvi", "Harsh", "Priya",
]
LAST = [
    "Sharma", "Iyer", "Nair", "Reddy", "Patel", "Gupta", "Menon", "Rao", "Joshi", "Das", "Kulkarni", "Bose",
    "Pillai", "Chopra", "Mehta", "Banerjee", "Singh", "Khan", "Verma", "Shetty",
]
CITIES = [
    ("Koramangala, Bengaluru", "560034"), ("Andheri East, Mumbai", "400069"), ("Salt Lake, Kolkata", "700091"),
    ("Banjara Hills, Hyderabad", "500034"), ("Aundh, Pune", "411007"), ("Adyar, Chennai", "600020"),
    ("Vaishali Nagar, Jaipur", "302021"), ("Gomti Nagar, Lucknow", "226010"), ("Navrangpura, Ahmedabad", "380009"),
    ("Kakkanad, Kochi", "682030"),
]
JOBS = ["Salaried", "Business owner", "Doctor", "Software engineer", "Teacher", "Consultant", "Retired", "Student"]
INCOME = ["Below 5 lakh", "5 to 10 lakh", "10 to 25 lakh", "25 to 50 lakh", "50 lakh to 1 crore"]

# People who already exist in each bank's demo data, so the cloud source joins them by PAN.
OVERLAP = {
    "axis": [
        ("Suresh Kumar", "ABCPK1234F", "1984-07-12", "9822104521", "suresh.kumar@mail.example", "M"),
        ("Anita Deshmukh", "BDEPD2345G", "1990-03-05", "9890012345", "anita.d@mail.example", "F"),
        ("Rajesh R Iyer", "CFGPI3456H", "1972-11-21", "9845098450", "rajesh.iyer@mail.example", "M"),
        ("Gurpreet Sandhu", "EHJPS5678K", "1979-01-30", "9815567001", "gurpreet.sandhu@mail.example", "M"),
    ],
    "hdfc": [
        ("Amit Verma", "AKVPV4321B", "1986-04-22", "9811022334", "amit.verma@mail.example", "M"),
        ("Pooja Nair", "BPNPN5432C", "1991-08-03", "9820133445", "pooja.nair@mail.example", "F"),
        ("Mohammed Irfan", "CQRPI6543D", "1976-12-15", "9900177881", "irfan.m@mail.example", "M"),
        ("Rohit Malhotra", "GYZPM1234H", "1982-03-11", "9988112233", "rohit.malhotra@mail.example", "M"),
    ],
}


# The deliberate edge cases, per bank. Same dob as the person they echo, so matching compares them.
TRICKY = {
    "axis": {
        "typo": "Suresh Kumaar",  # duplicate of OVERLAP[0] in core banking, no PAN
        "no_pan": [("Neha Kapoor", "Neha Kapur"), "1993-09-14", "neha.k@mail.example"],  # core / app spelling
        "family": "Lata Iyer",  # shares OVERLAP[2]'s phone, different person
        "moved_to": "402, Prestige Shantiniketan, Whitefield, Bengaluru 560048",
    },
    "hdfc": {
        "typo": "Amit Varma",
        "no_pan": [("Farhan Qureshi", "Farhan Qureshy"), "1988-02-27", "farhan.q@mail.example"],
        "family": "Sana Shaikh",
        "moved_to": "B-1204, Lodha Splendora, Ghodbunder Road, Thane 400615",
    },
}


def _pan(first, last, n):
    letters = "ABCDEFGHJKLMNPQRSTUVWXYZ"
    a, b, c = letters[n % 24], letters[(n * 7) % 24], letters[(n * 11) % 24]
    return f"{a}{b}{c}P{last[0].upper()}{1000 + (n * 37) % 9000:04d}{letters[(n * 5) % 24]}"


def customers(bank, count=24, seed=0):
    """`count` synthetic customers for one bank's source. Different `seed` gives a different but overlapping set."""
    rows = []
    tricky = TRICKY[bank]
    for i, (name, pan, dob, mobile, email, gender) in enumerate(OVERLAP[bank]):
        area, pin = CITIES[i]
        address = f"{12 + i * 9}, {area} {pin}"
        if seed == APP_SEED and i == 1:  # moved house and changed number; only the app has heard about it
            mobile, address = mobile[:-2] + "99", tricky["moved_to"]
        rows.append({"name": name, "pan": pan, "dob": dob, "mobile": mobile, "email": email, "gender": gender,
                     "address": address})

    first = OVERLAP[bank][0]
    if seed in CORE_SEEDS:  # a second account opened with a typo and no PAN
        rows.append({"name": tricky["typo"], "pan": None, "dob": first[2], "mobile": "9" + first[3][1:5] + "70707",
                     "email": None, "gender": first[5]})
    (core_name, app_name), dob, email = tricky["no_pan"]
    rows.append({"name": app_name if seed == APP_SEED else core_name, "pan": None, "dob": dob,
                 "mobile": "9" + dob.replace("-", "")[2:8] + "321" if seed == APP_SEED else "8" + dob.replace("-", "")[2:8] + "456",
                 "email": email if seed == APP_SEED else None, "gender": "F" if bank == "axis" else "M"})
    if seed == APP_SEED:  # a relative using the same phone number
        echo = OVERLAP[bank][2]
        rows.append({"name": tricky["family"], "pan": None, "dob": "1999-05-18", "mobile": echo[3], "email": None,
                     "gender": "F"})
    n = 0
    while len(rows) < count:
        k = n + seed * 7 + (0 if bank == "axis" else 100)
        first, last = FIRST[k % len(FIRST)], LAST[(k * 3) % len(LAST)]
        area, pin = CITIES[k % len(CITIES)]
        rows.append({
            "name": f"{first} {last}",
            "pan": _pan(first, last, k) if k % 4 else None,  # some customers have no PAN on file
            "dob": f"{1960 + k % 40}-{1 + k % 12:02d}-{1 + (k * 3) % 28:02d}",
            "mobile": f"9{(7340000000 + k * 104729) % 1000000000:09d}",
            "email": f"{first.lower()}.{last.lower()}{k % 90}@mail.example" if k % 5 else None,
            "gender": "F" if first in {"Diya", "Meera", "Isha", "Ananya", "Kavya", "Nisha", "Pooja", "Sneha",
                                      "Riya", "Lakshmi", "Tanvi", "Priya"} else "M",
            "address": f"{10 + k % 90}, {area} {pin}",
            "occupation": JOBS[k % len(JOBS)],
            "income": INCOME[k % len(INCOME)],
        })
        n += 1
    for i, row in enumerate(rows):
        row["id"] = f"{bank.upper()[:2]}{seed}-{1001 + i}"
        row["updated_at"] = f"2026-0{1 + i % 9}-{10 + i % 18:02d}T{8 + i % 10:02d}:15:00"
        row.setdefault("address", "")
        row.setdefault("occupation", "")
        row.setdefault("income", "")
    return rows
