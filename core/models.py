from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class UserRole(models.TextChoices):
    REGISTERED = "registered", "Registered"
    OWNER = "owner", "Owner"
    ADMIN = "admin", "Admin"


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Users must have an email address.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("role", UserRole.ADMIN)
        extra_fields.setdefault("first_name", "Admin")
        extra_fields.setdefault("last_name", "User")
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser):
    """Maps to existing MySQL table `user` (see database/schema.sql)."""

    id = models.BigAutoField(primary_key=True)
    email = models.EmailField(max_length=255, unique=True)
    password = models.CharField(max_length=255, db_column="password_hash")
    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80)
    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.REGISTERED,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    class Meta:
        db_table = "user"

    @property
    def is_staff(self):
        return self.role == UserRole.ADMIN

    @property
    def is_active(self):
        return True

    def __str__(self):
        return self.email


class BeachBar(models.Model):
    id = models.BigAutoField(primary_key=True)
    owner = models.ForeignKey(
        User,
        on_delete=models.RESTRICT,
        related_name="beach_bars",
        db_column="owner_id",
    )
    name = models.CharField(max_length=120)
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=80)
    description = models.TextField(blank=True, null=True)
    opening_time = models.TimeField()
    closing_time = models.TimeField()
    map_url = models.CharField(max_length=512, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "beach_bar"

    def __str__(self):
        return self.name


class Amenity(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=80, unique=True)

    class Meta:
        db_table = "amenity"

    def __str__(self):
        return self.name


class BeachBarAmenity(models.Model):
    pk = models.CompositePrimaryKey("beach_bar", "amenity")
    beach_bar = models.ForeignKey(
        BeachBar,
        on_delete=models.CASCADE,
        db_column="beach_bar_id",
    )
    amenity = models.ForeignKey(
        Amenity,
        on_delete=models.CASCADE,
        db_column="amenity_id",
    )

    class Meta:
        db_table = "beach_bar_amenity"


class SunbedCategory(models.Model):
    id = models.BigAutoField(primary_key=True)
    beach_bar = models.ForeignKey(
        BeachBar,
        on_delete=models.CASCADE,
        related_name="sunbed_categories",
        db_column="beach_bar_id",
    )
    name = models.CharField(max_length=80)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = "sunbed_category"

    def __str__(self):
        return f"{self.beach_bar.name} — {self.name}"


class Sunbed(models.Model):
    id = models.BigAutoField(primary_key=True)
    beach_bar = models.ForeignKey(
        BeachBar,
        on_delete=models.CASCADE,
        related_name="sunbeds",
        db_column="beach_bar_id",
    )
    category = models.ForeignKey(
        SunbedCategory,
        on_delete=models.RESTRICT,
        related_name="sunbeds",
        db_column="category_id",
    )
    label = models.CharField(max_length=20)
    grid_row = models.PositiveSmallIntegerField()
    grid_col = models.PositiveSmallIntegerField()

    class Meta:
        db_table = "sunbed"
        constraints = [
            models.UniqueConstraint(
                fields=["beach_bar", "label"],
                name="uk_sunbed_bar_label",
            ),
        ]

    def __str__(self):
        return f"{self.beach_bar.name} {self.label}"


class ReservationStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    COMPLETED = "completed", "Completed"
    CANCELLED = "cancelled", "Cancelled"


class Reservation(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(
        User,
        on_delete=models.RESTRICT,
        related_name="reservations",
        db_column="user_id",
    )
    sunbed = models.ForeignKey(
        Sunbed,
        on_delete=models.RESTRICT,
        related_name="reservations",
        db_column="sunbed_id",
    )
    reservation_date = models.DateField()
    status = models.CharField(
        max_length=20,
        choices=ReservationStatus.choices,
        default=ReservationStatus.ACTIVE,
    )
    price_at_booking = models.DecimalField(max_digits=10, decimal_places=2)
    payment_status = models.CharField(max_length=20, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "reservation"
        constraints = [
            models.UniqueConstraint(
                fields=["sunbed", "reservation_date"],
                name="uk_reservation_sunbed_date",
            ),
        ]


class Bundle(models.Model):
    id = models.BigAutoField(primary_key=True)
    beach_bar = models.ForeignKey(
        BeachBar,
        on_delete=models.CASCADE,
        related_name="bundles",
        db_column="beach_bar_id",
    )
    name = models.CharField(max_length=120)
    description = models.CharField(max_length=255, blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "bundle"

    def __str__(self):
        return self.name


class ReservationBundle(models.Model):
    pk = models.CompositePrimaryKey("reservation", "bundle")
    reservation = models.ForeignKey(
        Reservation,
        on_delete=models.CASCADE,
        db_column="reservation_id",
    )
    bundle = models.ForeignKey(
        Bundle,
        on_delete=models.RESTRICT,
        db_column="bundle_id",
    )
    price_at_booking = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table = "reservation_bundle"


class Review(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="reviews",
        db_column="user_id",
    )
    beach_bar = models.ForeignKey(
        BeachBar,
        on_delete=models.CASCADE,
        related_name="reviews",
        db_column="beach_bar_id",
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    review_text = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "review"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(rating__gte=1, rating__lte=5),
                name="chk_review_rating",
            ),
        ]
