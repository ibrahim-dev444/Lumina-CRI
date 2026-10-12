"""Synthetic customers for the cloud demo sources (Phase 6). Nobody here is a real person.

Each bank's systems overlap on purpose: some people already exist in that bank's demo data under the same PAN
(so they merge), some appear with a typo or a new phone number (so matching and review have work to do), and
the rest are new. Generated from fixed lists, so every run produces exactly the same rows.
"""

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


def _pan(first, last, n):
    letters = "ABCDEFGHJKLMNPQRSTUVWXYZ"
    a, b, c = letters[n % 24], letters[(n * 7) % 24], letters[(n * 11) % 24]
    return f"{a}{b}{c}P{last[0].upper()}{1000 + (n * 37) % 9000:04d}{letters[(n * 5) % 24]}"


def customers(bank, count=24, seed=0):
    """`count` synthetic customers for one bank's source. Different `seed` gives a different but overlapping set."""
    rows = []
    for i, (name, pan, dob, mobile, email, gender) in enumerate(OVERLAP[bank]):
        if seed % 2 and i == 1:
            mobile = mobile[:-2] + "99"  # same person, newer phone number in this system
        rows.append({"name": name, "pan": pan, "dob": dob, "mobile": mobile, "email": email, "gender": gender})
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
