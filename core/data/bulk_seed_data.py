"""Static data for bulk beach bar seeding."""

# 100 bars distributed across Adriatic coastal cities (Montenegro + nearby).
CITY_ASSIGNMENTS = (
    ["Budva"] * 18
    + ["Bar"] * 12
    + ["Kotor"] * 14
    + ["Tivat"] * 10
    + ["Herceg Novi"] * 10
    + ["Ulcinj"] * 11
    + ["Petrovac"] * 8
    + ["Bečići"] * 7
    + ["Sutomore"] * 5
    + ["Dubrovnik"] * 5
)

# Curated Adriatic beach bar names (one per bulk owner001–owner100).
BULK_BAR_NAMES = (
    # Budva (18)
    "Mogren Beach Club",
    "Slovenska Plaza Beach",
    "Jaz Beach Bar",
    "Ploče Beach Lounge",
    "Carmina Beach Bar",
    "Havana Beach Budva",
    "Tropico Beach Club",
    "Bermuda Beach Bar",
    "Guvat Lounge",
    "Almara Beach Club",
    "Kudadon Beach Club",
    "Casper Beach Bar",
    "Maestral Budva",
    "Beach Greco",
    "Tiva Beach Bar",
    "Safari Beach Lounge",
    "Avala Beach Terrace",
    "Olympia Beach Bar",
    # Bar (12)
    "Šušanj Beach Club",
    "Čanj Riviera",
    "Zeleni Port Beach",
    "Oblatno Beach Club",
    "Utjeha Beach Bar",
    "Kraljičina Plaža Bar",
    "Maljevik Beach Lounge",
    "Zukotrlica Beach Bar",
    "Pinjes Beach Club",
    "Bar Marina Beach",
    "Sutomore Bay Bar",
    "Ratac Beach Lounge",
    # Kotor (14)
    "Plavi Horizont Kotor",
    "Galija Beach Club",
    "Ljuta Beach Bar",
    "Orahovac Beach Lounge",
    "Dobrota Beach Terrace",
    "Plagent Beach Bar",
    "Stoliv Beach Club",
    "Đuraševići Beach Bar",
    "Morinj Beach Lounge",
    "Marko Polo Beach Bar",
    "Picigin Beach Club",
    "Žanjic Beach Bar",
    "Mirišta Beach Lounge",
    "Plavi Horizont Dobrota",
    # Tivat (10)
    "Pržno Beach Bar",
    "Donja Lastva Lounge",
    "Copacabana Tivat",
    "Al Posto Giusto Beach",
    "Pine Beach Club",
    "Kalardovo Beach Bar",
    "Seljanovo Bay Lounge",
    "Marina Tivat Beach",
    "Belane Beach Club",
    "Luštica Bay Beach",
    # Herceg Novi (10)
    "Žanjice Beach Club",
    "Mirište Beach Bar",
    "Plaza Beach Herceg Novi",
    "Igalo Beach Bar",
    "Kumbor Beach Club",
    "Meljine Beach Terrace",
    "Bijela Bay Bar",
    "Rose Beach Bar",
    "Bijela Beach Lounge",
    "Luštica Village Beach",
    # Ulcinj (11)
    "Copacabana Ulcinj",
    "Miami Beach Ulcinj",
    "Valdanos Beach Bar",
    "Ada Bojana Beach Club",
    "Long Beach Lounge",
    "Šaško Beach Bar",
    "Ladies Beach Terrace",
    "Velika Plaža Bar",
    "Safari Beach Ulcinj",
    "London Ulcinj Beach",
    "Albatros Beach Club",
    # Petrovac (8)
    "Castello Beach Bar",
    "Perla Beach Club",
    "Lučice Beach Lounge",
    "Buljarica Bay Bar",
    "Petrovac Riviera Club",
    "Olive Beach Petrovac",
    "Kamenovo Beach Bar",
    "Reževići Beach Terrace",
    # Bečići (7)
    "Maestral Bečići",
    "Drobni Pijesak Beach Bar",
    "Rafailovići Beach Club",
    "Kamenovo Lounge",
    "Riviera Bečići",
    "Splendid Beach Terrace",
    "Aria Beach Bečići",
    # Sutomore (5)
    "Sutomore Beach Club",
    "Zagreda Beach Bar",
    "Čanj Sunset Lounge",
    "Boro Beach Sutomore",
    "Čanj Beach House",
    # Dubrovnik (5)
    "Banje Beach Club",
    "Coral Beach Dubrovnik",
    "Copacabana Dubrovnik",
    "Sv. Jakov Beach Bar",
    "Betina Cave Beach",
    "Lapad Beach Bar",
    "Lozica Beach Club",
)


def bulk_bar_name(index):
    """Return curated bar name for 1-based bulk owner index."""
    if index < 1 or index > len(BULK_BAR_NAMES):
        return f"Beach Bar {index:03d}"
    return BULK_BAR_NAMES[index - 1]

STREET_TEMPLATES = (
    "Obala {n}",
    "Šetalište {n}",
    "Marina bb {n}",
    "Riviera {n}",
    "Plaža {n}",
)

CATEGORY_POOL = (
    ("Standard", 12, 18),
    ("Premium", 20, 32),
    ("Lazy Bag", 8, 14),
    ("Cabana", 45, 75),
    ("VIP", 35, 55),
)

BUNDLE_SPECS = (
    ("Drinks Package", "Two welcome drinks at the bar", 6, 12),
    ("Parking", "Reserved parking near the entrance", 4, 8),
    ("Lunch Combo", "Light lunch served at your sunbed", 12, 22),
    ("Towel Set", "Fresh towels for the day", 3, 6),
)

REVIEW_SNIPPETS = (
    "Great spot, friendly staff and clean beach.",
    "Lovely view of the Adriatic. Would book again.",
    "Sunbeds were comfortable and well organized.",
    "Perfect for a relaxed day by the sea.",
    "Good value for the premium zone.",
    "Easy booking and smooth check-in.",
    "Nice music and atmosphere in the afternoon.",
    "Family-friendly layout with shaded options.",
    "Excellent cocktails and quick service.",
    "One of the best beaches in town.",
)

BULK_PASSWORD = "demo1234"
BULK_OWNER_EMAIL_PREFIX = "owner"
BULK_GUEST_EMAIL_PREFIX = "guest"
BULK_OWNER_EMAIL_DOMAIN = "beachbooker.test"
BULK_GUEST_EMAIL_DOMAIN = "beachbooker.test"
BULK_GUEST_POOL_SIZE = 20
