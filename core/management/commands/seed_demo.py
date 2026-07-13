from datetime import date, time, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import (
    Amenity,
    BeachBar,
    BeachBarAmenity,
    Bundle,
    Reservation,
    ReservationStatus,
    Sunbed,
    SunbedCategory,
    User,
    UserRole,
)

DEMO_PASSWORD = "demo1234"

BLUE_HORIZON_SUNBEDS = (
    ("Premium", [(f"P{i}", 0, i - 1) for i in range(1, 11)]),
    ("Standard", [(f"S{i}", 1, i - 1) for i in range(1, 11)]),
    ("Lazy Bag", [(f"L{i}", 2, i - 1) for i in range(1, 11)]),
    ("Cabana", [(f"C{i}", 3, i - 1) for i in range(1, 5)]),
)

# Labels marked taken in html_pages/beach-bar.html prototype
BLUE_HORIZON_TAKEN = {"P2", "P4", "P7", "P10", "S3", "S5", "S6", "S9", "L3", "L6", "L9", "C2"}


class Command(BaseCommand):
    help = "Load demo users, beach bars, sunbeds, and sample reservations (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset-passwords",
            action="store_true",
            help="Reset demo account passwords to demo1234",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        owner = self._ensure_user(
            "owner@beachbooker.test",
            "Demo",
            "Owner",
            UserRole.OWNER,
            options["reset_passwords"],
        )
        guest = self._ensure_user(
            "guest@beachbooker.test",
            "Demo",
            "Guest",
            UserRole.REGISTERED,
            options["reset_passwords"],
        )
        self._ensure_user(
            "admin@beachbooker.test",
            "Demo",
            "Admin",
            UserRole.ADMIN,
            options["reset_passwords"],
        )

        amenities = self._ensure_amenities(
            [
                "Wi-Fi",
                "Showers",
                "Restaurant",
                "Bar",
                "Umbrellas",
                "Card Payment",
                "Parking",
                "Changing Rooms",
                "Music",
            ]
        )

        blue = self._ensure_beach_bar(
            owner=owner,
            name="Riccardo Beach Bar",
            address="Slovenska obala bb",
            city="Budva",
            description="Flagship demo beach bar on Budva's Slovenska beach.",
            opening_time=time(8, 0),
            closing_time=time(20, 0),
            image_url=(
                "https://images.unsplash.com/photo-1519046904884-53103b34b206?w=1600&q=80"
            ),
        )
        aqua = self._ensure_beach_bar(
            owner=owner,
            name="Porto Skver Beach",
            address="Topolica 12",
            city="Bar",
            description="Second demo bar on Bar's waterfront near Porto Skver.",
            opening_time=time(9, 0),
            closing_time=time(19, 0),
            image_url=(
                "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=1600&q=80"
            ),
        )

        self._link_amenities(blue, amenities)
        self._link_amenities(aqua, amenities[:6])

        blue_categories = self._ensure_categories(
            blue,
            {
                "Premium": Decimal("25.00"),
                "Standard": Decimal("15.00"),
                "Lazy Bag": Decimal("10.00"),
                "Cabana": Decimal("60.00"),
            },
        )
        aqua_categories = self._ensure_categories(
            aqua,
            {
                "Standard": Decimal("12.00"),
                "Premium": Decimal("18.00"),
            },
        )

        blue_beds = self._ensure_sunbeds(blue, blue_categories, BLUE_HORIZON_SUNBEDS)
        aqua_beds = self._ensure_sunbeds(
            aqua,
            aqua_categories,
            [
                ("Standard", [(f"A{i}", 0, i - 1) for i in range(1, 7)]),
                ("Premium", [(f"B{i}", 1, i - 1) for i in range(1, 5)]),
            ],
        )

        tomorrow = date.today() + timedelta(days=1)
        reservations = self._ensure_reservations(
            guest,
            blue_beds,
            BLUE_HORIZON_TAKEN,
            tomorrow,
            blue_categories,
        )
        bundles = self._ensure_bundles(
            blue,
            [
                ("Drinks Package", "Two welcome drinks at the bar", Decimal("8.00")),
                ("Parking", "Reserved spot near the entrance", Decimal("5.00")),
            ],
        )

        self.stdout.write(self.style.SUCCESS("Demo data ready."))
        self.stdout.write(f"  Users: owner, guest, admin @beachbooker.test / {DEMO_PASSWORD}")
        self.stdout.write(f"  Beach bars: {BeachBar.objects.count()}")
        self.stdout.write(f"  Sunbeds: {Sunbed.objects.count()}")
        self.stdout.write(f"  Bundles: {bundles}")
        self.stdout.write(f"  Active reservations (tomorrow): {reservations}")

    def _ensure_user(self, email, first_name, last_name, role, reset_password):
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "first_name": first_name,
                "last_name": last_name,
                "role": role,
            },
        )
        if created or reset_password:
            user.set_password(DEMO_PASSWORD)
            user.first_name = first_name
            user.last_name = last_name
            user.role = role
            user.save()
        return user

    def _ensure_amenities(self, names):
        return [Amenity.objects.get_or_create(name=name)[0] for name in names]

    def _ensure_beach_bar(self, **fields):
        bar, created = BeachBar.objects.get_or_create(
            name=fields["name"],
            defaults=fields,
        )
        if not created:
            updates = {}
            for key in ("image_url", "description", "address", "city"):
                if key in fields and fields[key] and not getattr(bar, key, None):
                    updates[key] = fields[key]
            if updates:
                for key, value in updates.items():
                    setattr(bar, key, value)
                bar.save(update_fields=list(updates.keys()))
        return bar

    def _link_amenities(self, bar, amenities):
        for amenity in amenities:
            BeachBarAmenity.objects.get_or_create(beach_bar=bar, amenity=amenity)

    def _ensure_categories(self, bar, name_prices):
        categories = {}
        for name, price in name_prices.items():
            category, _ = SunbedCategory.objects.get_or_create(
                beach_bar=bar,
                name=name,
                defaults={"price": price},
            )
            categories[name] = category
        return categories

    def _ensure_sunbeds(self, bar, categories, layout):
        beds = {}
        for category_name, spots in layout:
            category = categories[category_name]
            for label, row, col in spots:
                bed, _ = Sunbed.objects.get_or_create(
                    beach_bar=bar,
                    label=label,
                    defaults={
                        "category": category,
                        "grid_row": row,
                        "grid_col": col,
                    },
                )
                beds[label] = bed
        return beds

    def _ensure_reservations(self, guest, beds, taken_labels, reservation_date, categories):
        count = 0
        for label in taken_labels:
            bed = beds.get(label)
            if not bed:
                continue
            category = categories.get(
                bed.category.name,
                bed.category,
            )
            _, created = Reservation.objects.get_or_create(
                sunbed=bed,
                reservation_date=reservation_date,
                defaults={
                    "user": guest,
                    "status": ReservationStatus.ACTIVE,
                    "price_at_booking": category.price if hasattr(category, "price") else bed.category.price,
                },
            )
            if created:
                count += 1
        return count

    def _ensure_bundles(self, bar, bundle_specs):
        count = 0
        for name, description, price in bundle_specs:
            _, created = Bundle.objects.get_or_create(
                beach_bar=bar,
                name=name,
                defaults={
                    "description": description,
                    "price": price,
                    "is_active": True,
                },
            )
            if created:
                count += 1
        return count
