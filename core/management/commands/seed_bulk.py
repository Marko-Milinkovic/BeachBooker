import re
from datetime import date, time, timedelta
from decimal import Decimal
from random import Random

from django.core.management.base import BaseCommand
from django.db import transaction

from core.data.bulk_bar_images import bulk_image_url
from core.data.bulk_seed_data import (
    BULK_GUEST_EMAIL_DOMAIN,
    BULK_GUEST_EMAIL_PREFIX,
    BULK_GUEST_POOL_SIZE,
    BULK_OWNER_EMAIL_DOMAIN,
    BULK_OWNER_EMAIL_PREFIX,
    BULK_PASSWORD,
    BUNDLE_SPECS,
    CATEGORY_POOL,
    CITY_ASSIGNMENTS,
    REVIEW_SNIPPETS,
    STREET_TEMPLATES,
    bulk_bar_name,
)
from core.models import (
    Amenity,
    BeachBar,
    BeachBarAmenity,
    Bundle,
    Reservation,
    ReservationStatus,
    Review,
    Sunbed,
    SunbedCategory,
    User,
    UserRole,
)
from core.services.beach_bar import BAR_IMAGES

BULK_OWNER_EMAIL_RE = re.compile(
    rf"^{BULK_OWNER_EMAIL_PREFIX}(\d{{3}})@{re.escape(BULK_OWNER_EMAIL_DOMAIN)}$"
)
BULK_GUEST_EMAIL_RE = re.compile(
    rf"^{BULK_GUEST_EMAIL_PREFIX}\d{{3}}@{re.escape(BULK_GUEST_EMAIL_DOMAIN)}$"
)

DEMO_BAR_NAMES = frozenset(BAR_IMAGES.keys())


class Command(BaseCommand):
    help = "Seed many beach bars for realistic Explore browsing (idempotent top-up)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--bars",
            type=int,
            default=100,
            help="Target number of bulk beach bars (default: 100).",
        )
        parser.add_argument(
            "--clear-bulk",
            action="store_true",
            help="Remove bulk-seeded owners, guests, and beach bars only.",
        )
        parser.add_argument(
            "--refresh-images",
            action="store_true",
            help="Re-assign image_url on bulk bars from core/static/core/images/bars/.",
        )
        parser.add_argument(
            "--seed",
            type=int,
            default=42,
            help="Random seed for reproducible layouts and reservations.",
        )

    def handle(self, *args, **options):
        if options["refresh_images"]:
            updated = self._refresh_bulk_images()
            self.stdout.write(self.style.SUCCESS(f"Refreshed images on {updated} bulk bars."))
            return

        if options["clear_bulk"]:
            self._clear_bulk()
            self.stdout.write(self.style.SUCCESS("Bulk seed data removed."))
            return

        target = max(0, options["bars"])
        if target == 0:
            self.stdout.write("Nothing to do (--bars 0).")
            return

        created = self._seed_bulk(target=target, seed=options["seed"])
        total_bulk = self._bulk_bars().count()
        self.stdout.write(self.style.SUCCESS("Bulk seed complete."))
        self.stdout.write(f"  Created bars this run: {created}")
        self.stdout.write(f"  Bulk bars total: {total_bulk}")
        self.stdout.write(f"  All beach bars: {BeachBar.objects.count()}")
        self.stdout.write(
            f"  Bulk owners: {BULK_OWNER_EMAIL_PREFIX}001@… / {BULK_PASSWORD}"
        )

    @transaction.atomic
    def _clear_bulk(self):
        owners = self._bulk_owners()
        bars = self._bulk_bars()
        Reservation.objects.filter(sunbed__beach_bar__in=bars).delete()
        bars.delete()
        owners.delete()
        User.objects.filter(email__regex=BULK_GUEST_EMAIL_RE.pattern).delete()

    @transaction.atomic
    def _seed_bulk(self, target, seed):
        rng = Random(seed)
        amenities = self._ensure_amenities()
        review_guests = self._ensure_review_guests()
        booking_guest = self._ensure_booking_guest()
        city_plan = CITY_ASSIGNMENTS[:target]
        created = 0

        for index in range(1, target + 1):
            owner_email = self._owner_email(index)
            owner = self._ensure_owner(owner_email, index)
            if BeachBar.objects.filter(owner=owner).exists():
                continue

            city = city_plan[index - 1]
            bar_name = bulk_bar_name(index)
            image_url = bulk_image_url(index - 1)
            opening_hour = rng.randint(7, 9)
            closing_hour = rng.randint(18, 22)

            bar = BeachBar.objects.create(
                owner=owner,
                name=bar_name,
                address=self._address_for(city, index, rng),
                city=city,
                description=(
                    f"Seaside lounge on the {city} coast with sunbeds, "
                    "drinks, and Adriatic views."
                ),
                opening_time=time(opening_hour, 0),
                closing_time=time(closing_hour, 0),
                image_url=image_url,
            )

            self._link_amenities(bar, amenities, rng)
            categories = self._create_categories(bar, rng)
            sunbeds = self._create_sunbeds(bar, categories, rng)
            if rng.random() < 0.4:
                self._create_bundles(bar, rng)
            self._create_reviews(bar, review_guests, rng)
            self._create_reservations(bar, sunbeds, booking_guest, review_guests, rng)
            created += 1

        return created

    def _refresh_bulk_images(self):
        from core.data.bulk_bar_images import unique_urls_for_bars
        from core.services.beach_bar import BAR_IMAGES

        bars_needing_images = []
        for bar in BeachBar.objects.order_by("name"):
            if bar.name in DEMO_BAR_NAMES:
                continue
            bars_needing_images.append(bar)

        reserved = set(BAR_IMAGES.values())
        try:
            urls = unique_urls_for_bars(len(bars_needing_images), reserved_urls=reserved)
        except ValueError as exc:
            self.stderr.write(self.style.ERROR(str(exc)))
            return 0

        updated = 0
        for bar, url in zip(bars_needing_images, urls):
            if bar.image_url != url:
                bar.image_url = url
                bar.save(update_fields=["image_url"])
                updated += 1

        for bar in BeachBar.objects.filter(name__in=BAR_IMAGES):
            url = BAR_IMAGES[bar.name]
            if bar.image_url != url:
                bar.image_url = url
                bar.save(update_fields=["image_url"])
                updated += 1

        return updated

    def _bulk_owners(self):
        return User.objects.filter(email__regex=BULK_OWNER_EMAIL_RE.pattern)

    def _bulk_bars(self):
        return BeachBar.objects.filter(owner__in=self._bulk_owners())

    def _owner_email(self, index):
        return (
            f"{BULK_OWNER_EMAIL_PREFIX}{index:03d}"
            f"@{BULK_OWNER_EMAIL_DOMAIN}"
        )

    def _guest_email(self, index):
        return (
            f"{BULK_GUEST_EMAIL_PREFIX}{index:03d}"
            f"@{BULK_GUEST_EMAIL_DOMAIN}"
        )

    def _ensure_owner(self, email, index):
        owner, created = User.objects.get_or_create(
            email=email,
            defaults={
                "first_name": "Owner",
                "last_name": f"{index:03d}",
                "role": UserRole.OWNER,
            },
        )
        if created:
            owner.set_password(BULK_PASSWORD)
            owner.save()
        return owner

    def _ensure_booking_guest(self):
        guest, created = User.objects.get_or_create(
            email=f"guest@{BULK_GUEST_EMAIL_DOMAIN}",
            defaults={
                "first_name": "Bulk",
                "last_name": "Guest",
                "role": UserRole.REGISTERED,
            },
        )
        if created:
            guest.set_password(BULK_PASSWORD)
            guest.save()
        return guest

    def _ensure_review_guests(self):
        guests = []
        for index in range(1, BULK_GUEST_POOL_SIZE + 1):
            email = self._guest_email(index)
            guest, created = User.objects.get_or_create(
                email=email,
                defaults={
                    "first_name": "Reviewer",
                    "last_name": f"{index:02d}",
                    "role": UserRole.REGISTERED,
                },
            )
            if created:
                guest.set_password(BULK_PASSWORD)
                guest.save()
            guests.append(guest)
        return guests

    def _ensure_amenities(self):
        names = [
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
        return [Amenity.objects.get_or_create(name=name)[0] for name in names]

    def _address_for(self, city, index, rng):
        template = STREET_TEMPLATES[(index - 1) % len(STREET_TEMPLATES)]
        return f"{template.format(n=index)}, {city}"

    def _link_amenities(self, bar, amenities, rng):
        count = rng.randint(3, min(7, len(amenities)))
        for amenity in rng.sample(amenities, count):
            BeachBarAmenity.objects.get_or_create(beach_bar=bar, amenity=amenity)

    def _create_categories(self, bar, rng):
        count = rng.randint(2, 4)
        picked = rng.sample(CATEGORY_POOL, count)
        categories = {}
        for name, low, high in picked:
            price = Decimal(str(rng.randint(low, high)))
            category = SunbedCategory.objects.create(
                beach_bar=bar,
                name=name,
                price=price,
                description=f"{name} zone at {bar.name}",
            )
            categories[name] = category
        return categories

    def _create_sunbeds(self, bar, categories, rng):
        total = rng.randint(15, 35)
        category_names = list(categories.keys())
        rows = rng.randint(3, 6)
        cols = (total + rows - 1) // rows
        sunbeds = []
        label_index = 1

        for row in range(rows):
            for col in range(cols):
                if label_index > total:
                    break
                category_name = category_names[(label_index - 1) % len(category_names)]
                label = f"S{label_index}"
                sunbed = Sunbed.objects.create(
                    beach_bar=bar,
                    category=categories[category_name],
                    label=label,
                    grid_row=row,
                    grid_col=col,
                )
                sunbeds.append(sunbed)
                label_index += 1

        return sunbeds

    def _create_bundles(self, bar, rng):
        count = rng.randint(1, 2)
        for name, description, low, high in rng.sample(BUNDLE_SPECS, count):
            Bundle.objects.create(
                beach_bar=bar,
                name=name,
                description=description,
                price=Decimal(str(rng.randint(low, high))),
                is_active=True,
            )

    def _create_reviews(self, bar, guests, rng):
        count = rng.randint(3, 8)
        for guest in rng.sample(guests, min(count, len(guests))):
            rating = 5 if rng.random() < 0.3 else rng.randint(3, 5)
            Review.objects.create(
                user=guest,
                beach_bar=bar,
                rating=rating,
                review_text=rng.choice(REVIEW_SNIPPETS),
            )

    def _create_reservations(self, bar, sunbeds, primary_guest, guests, rng):
        if not sunbeds:
            return

        occupancy = rng.uniform(0.25, 0.35)
        pool = list(sunbeds)
        rng.shuffle(pool)
        take_count = max(1, int(len(pool) * occupancy))
        selected = pool[:take_count]
        bookers = [primary_guest, *guests]

        for offset in range(7):
            reservation_date = date.today() + timedelta(days=offset)
            day_slice = (
                selected
                if offset < 3
                else rng.sample(selected, max(1, len(selected) // 2))
            )
            for sunbed in day_slice:
                guest = rng.choice(bookers)
                Reservation.objects.get_or_create(
                    sunbed=sunbed,
                    reservation_date=reservation_date,
                    defaults={
                        "user": guest,
                        "status": ReservationStatus.ACTIVE,
                        "price_at_booking": sunbed.category.price,
                    },
                )
