# BeachBooker — conceptual data model

### What this file is for

This document is the **team’s agreed picture of the data** before we draw the IE model (MySQL Workbench), write SQL, or build Django models. It is **not** the final database script or the course **Specifikacija baze** — those come next and must match what is written here.

Faculty templates and submission rules live in **`database/coursework/`**.

### How we design the database

- **Support the product we specified** — tables and relationships must cover MVP needs from the project spec: users and roles, beach bars, sunbeds and categories, reservations (book/cancel by date), owner management, and explore filters. The **web app and AJAX UI are built on top of this schema**, not the other way around.
- **Keep it as simple as possible** — few clear entities, normal foreign keys, no duplicate structures (e.g. one `User` table with roles, no separate “availability” table). Easy to map **one Django model per main table** and to load map/search data via **HTTP + AJAX** without storing UI state in MySQL.
- **Tables now, screens later** — some tables (e.g. bundles, reviews) exist early so we do not redesign the DB when we add features; the **MVP app may not expose every screen yet**. Empty tables are fine until implementation catches up.

If this file and the IE diagram disagree, **update this file first**, then the diagram and SQL.

## Design decisions (locked)

| Topic | Decision |
|--------|----------|
| **Users & admin** | One **User** table with a **role** field: registered customer, beach bar owner, or system admin. People browsing **without logging in** are not stored — they are only “guest” in the app. |
| **Owner ↔ bar** | In the database, **one owner can have many beach bars** (`owner_id` on each bar, not unique). The **first version of the app** can still only let them create **one** bar; adding more bars is a UI change later, not a schema change. |
| **Reservation** | A booking is for **one sunbed on one calendar date** (no hour slots in v1). **Status:** `active`, `completed`, or `cancelled`. Only **logged-in registered users** can reserve (not anonymous guests). |
| **Price** | When someone books, store **`price_at_booking`** on the reservation (and on bundle lines if used). If the owner changes category prices later, **old bookings keep their original price**. |
| **Sunbed identity** | Each spot is identified **inside its bar** by a **label** (e.g. `P3`, `S7`). **Unique together:** beach bar + label — not globally unique across all bars. |
| **Availability** | There is **no “availability” table**. A spot is **free on a date** if there is **no active reservation** for that spot on that date (computed in queries / AJAX). |
| **Bundles** | **`Bundle`** (packages per bar) and **`ReservationBundle`** (what was added to a booking) **exist in the schema**. **MVP booking UI** can ignore bundles until that flow is built. |
| **Reviews** | **`Review`** table exists (user, bar, rating, text, date). **MVP UI** can keep fake/static stars until real reviews are implemented. |
| **Payment** | **No full payment system in v1.** You may add a simple **`payment_status`** on a reservation later when payment is simulated. |

---

## Entities

### User
Account for login and authorization.

- **Attributes (conceptual):** id, email, password (hashed), first name, last name, role, created_at.
- **Roles:** `registered` (books sunbeds), `owner` (manages bar(s)), `admin` (system maintenance).
- One person = one row; role drives permissions.

### BeachBar
A beach bar on the platform.

- **Attributes:** id, owner (FK → User), name, address, city/region, description, opening time, closing time, optional map URL, optional image URLs (or separate media later).
- **Owned by** exactly one owner user; owner may have **many** bars.

### Amenity
Lookup of filterable facilities (parking, Wi‑Fi, food & drinks, showers, …).

- **Attributes:** id, name (unique).

### BeachBarAmenity
Which amenities a bar offers (explore filters).

- **Attributes:** beach_bar_id, amenity_id.
- **Composite PK:** (beach_bar_id, amenity_id).

### SunbedCategory
Pricing / zone group **within one bar** (Premium, Standard, Shade, Cabana, …).

- **Attributes:** id, beach_bar_id, name, price (per day or per bar’s pricing unit), optional description.
- Owner sets prices in dashboard “Pricing”.

### Sunbed
One bookable spot on the interactive map.

- **Attributes:** id, beach_bar_id, category_id, **label** (e.g. P3), layout position (row/col or x/y for map editor).
- **Business key:** (beach_bar_id, label) unique.

### Reservation
Booking of one sunbed for one date.

- **Attributes:** id, user_id, sunbed_id, **reservation_date**, status, **price_at_booking**, optional payment_status, created_at.
- **Rule:** at most one **active** reservation per (sunbed_id, reservation_date).
- Completed = date in past; cancelled = user/owner cancelled.

### Bundle
Optional add-on package defined by owner for a bar.

- **Attributes:** id, beach_bar_id, name, description, price, active flag.

### ReservationBundle
Bundles attached to a reservation (0..n per reservation).

- **Attributes:** reservation_id, bundle_id, **price_at_booking** (snapshot).
- **Composite PK:** (reservation_id, bundle_id).

### Review
User feedback for a beach bar (future UI).

- **Attributes:** id, user_id, beach_bar_id, rating (e.g. 1–5), optional text, created_at.
- **Policy (flexible):** allow multiple reviews per user per bar over time unless you later add UNIQUE(user, bar).

---

## Relationships & cardinalities

```
User [owner]           (1,n) ──< BeachBar
User [registered]      (1,n) ──< Reservation
User                   (0,n) ──< Review

BeachBar               (1,n) ──< SunbedCategory
BeachBar               (1,n) ──< Sunbed
BeachBar               (1,n) ──< Bundle
BeachBar               (n,m) ── Amenity          via BeachBarAmenity

SunbedCategory         (1,n) ──< Sunbed
Sunbed                 (1,n) ──< Reservation

Reservation            (0,n) ──< ReservationBundle >── (n,1) Bundle
Review                 (n,1) ──> BeachBar
Review                 (n,1) ──> User
```

---

## Derived / not modeled as entities

| Concept | Handling |
|---------|----------|
| **Guest** (not logged in) | No table; browse via app without user_id. |
| **Spot availability** | Query reservations for sunbed + date. |
| **Occupancy & revenue stats** | Aggregate over Reservation (+ bundles) for owner dashboard. |
| **Average rating on bar card** | `AVG(Review.rating)` when reviews are live; until then UI may use static text. |

---

## MVP vs schema (app scope)

| In schema (v1) | In MVP UI (likely) |
|----------------|---------------------|
| User, BeachBar, SunbedCategory, Sunbed, Reservation | Yes |
| Amenity, BeachBarAmenity | Search/filter if implemented |
| Bundle, ReservationBundle | Tables only; screens later |
| Review | Table only; static stars in prototype |
| Multi-bar per owner | Schema yes; “add second bar” UI optional |

---

## Next artifacts

1. IE logical model in MySQL Workbench (this document → diagram).
2. Generated `CREATE` script.
3. **Specifikacija baze** per `SpecifikacijaBaze.pdf` (ER + IE image + relational schema + table catalog).
