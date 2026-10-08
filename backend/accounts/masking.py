"""Hide personal data from roles that do not need it. Applied on the server, so masked values never
reach the browser, its cache, or a screenshot.
"""


def mask_mobile(value):
    """9822104521 -> 98xxxx4521"""
    if not value or len(value) < 6:
        return value
    return value[:2] + "x" * (len(value) - 6) + value[-4:]


def mask_email(value):
    """suresh.kumar@mail.example -> s•••@mail.example"""
    if not value or "@" not in value:
        return value
    local, domain = value.split("@", 1)
    return f"{local[:1]}•••@{domain}"


def mask_dob(value):
    """1984-07-12 -> 1984-••-••  (the year is enough to tell two people apart on a call)"""
    if not value:
        return value
    text = str(value)
    return text[:4] + "-••-••"


MASKERS = {"mobile": mask_mobile, "email": mask_email, "dob": mask_dob}


def mask(field, value):
    masker = MASKERS.get(field)
    return masker(value) if masker else value
