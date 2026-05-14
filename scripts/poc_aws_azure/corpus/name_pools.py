import random
import unicodedata

FRENCH_FIRST_NAMES = [
    "H\u00e9l\u00e8ne", "\u00c9tienne", "Fran\u00e7ois", "Genevi\u00e8ve", "Ren\u00e9",
    "Th\u00e9r\u00e8se", "Andr\u00e9", "C\u00e9cile", "No\u00ebl", "D\u00e9sir\u00e9",
    "Beno\u00eet", "Am\u00e9lie", "J\u00e9r\u00f4me", "Val\u00e9rie", "S\u00e9bastien",
    "\u00c9milie", "Rapha\u00ebl", "Gabrielle", "C\u00e9dric", "\u00c9lo\u00efse",
]

FRENCH_LAST_NAMES = [
    "C\u00f4t\u00e9", "Gagn\u00e9", "Pelletier", "L\u00e9vesque", "B\u00e9langer",
    "Tremblay", "Gauthier", "Bouchard", "Desch\u00eanes", "M\u00e9nard",
    "B\u00e9rub\u00e9", "Lavoie", "Fortin", "Ouellet", "Beaulieu",
    "Thibault", "Lefebvre", "B\u00e9land", "Desjardins", "Chr\u00e9tien",
]

BANK_NAMES = [
    "Royal Bank of Canada", "TD Canada Trust", "Bank of Montreal",
    "Scotiabank", "CIBC", "National Bank of Canada",
    "Desjardins", "HSBC Canada", "Laurentian Bank",
]

QUEBEC_CITIES = [
    "Montreal", "Quebec City", "Laval", "Gatineau", "Longueuil",
    "Sherbrooke", "Levis", "Saguenay", "Trois-Rivieres", "Terrebonne",
]

PROVINCES = ["Ontario", "Quebec", "British Columbia", "Alberta", "Manitoba"]

CITIES_BY_PROVINCE = {
    "Ontario": ["Toronto", "Ottawa", "Mississauga", "Hamilton", "London"],
    "Quebec": ["Montreal", "Quebec City", "Laval", "Gatineau", "Sherbrooke"],
    "British Columbia": ["Vancouver", "Victoria", "Burnaby", "Surrey", "Richmond"],
    "Alberta": ["Calgary", "Edmonton", "Red Deer", "Lethbridge", "Medicine Hat"],
    "Manitoba": ["Winnipeg", "Brandon", "Steinbach", "Thompson", "Portage la Prairie"],
}

AREA_CODES = ["416", "647", "905", "514", "438", "613", "819", "450"]

FAKE_DOMAINS = ["example.com", "example.ca", "testbank.ca", "acmecorp.ca", "synthco.com"]

POSTAL_FIRST_CHARS = "ABCEGHJKLMNPRSTVXY"
POSTAL_OTHER_CHARS = "ABCEGHJKLMNPRSTVWXYZ"


def generate_postal_code() -> str:
    """Generate a valid-format Canadian postal code: A1A 1A1."""
    return (
        random.choice(POSTAL_FIRST_CHARS)
        + str(random.randint(0, 9))
        + random.choice(POSTAL_OTHER_CHARS)
        + " "
        + str(random.randint(0, 9))
        + random.choice(POSTAL_OTHER_CHARS)
        + str(random.randint(0, 9))
    )


def generate_phone() -> str:
    """Generate a Canadian phone number: (416) 555-0123."""
    area = random.choice(AREA_CODES)
    exchange = str(random.randint(200, 999))
    subscriber = str(random.randint(0, 9999)).zfill(4)
    return f"({area}) {exchange}-{subscriber}"


def generate_email(first_name: str, last_name: str) -> str:
    """Generate an email from a person name."""
    def strip_accents(s):
        return "".join(
            c for c in unicodedata.normalize("NFD", s)
            if unicodedata.category(c) != "Mn"
        )
    local = f"{strip_accents(first_name).lower()}.{strip_accents(last_name).lower()}"
    domain = random.choice(FAKE_DOMAINS)
    return f"{local}@{domain}"


def generate_account_number() -> str:
    """Generate a 7-digit numeric account number string."""
    return str(random.randint(1000000, 9999999))
