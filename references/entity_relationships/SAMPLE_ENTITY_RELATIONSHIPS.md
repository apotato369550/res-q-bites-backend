For ResQ Bites, I would recommend 8 core entities. This keeps the ERD normalized, scalable, and not overly complex for a SAD/Capstone project.

ResQ Bites ERD
1. USERS

Represents all system accounts (Admin, LGU, Donor).

Users

user_id (PK)
first_name
last_name
email
password
phone_number
role
created_at
status
2. LGUS

Stores participating LGUs and barangays.

LGUs

lgu_id (PK)
lgu_name
barangay
address
contact_number
user_id (FK)
3. DONORS

Additional information for donors.

Donors

donor_id (PK)
user_id (FK)
donor_type
organization_name
points
registration_date
4. DONATIONS

Main donation records.

Donations

donation_id (PK)
donor_id (FK)
lgu_id (FK)
food_name
category
quantity
expiration_date
pickup_address
donation_status
created_at
5. FOOD_INVENTORY

Food received and managed by LGUs.

Food_Inventory

inventory_id (PK)
donation_id (FK)
lgu_id (FK)
food_name
category
quantity_available
expiration_date
inventory_status
6. BENEFICIARIES

Recipients managed by LGUs.

Beneficiaries

beneficiary_id (PK)
lgu_id (FK)
beneficiary_name
family_size
contact_number
eligibility_status
7. DISTRIBUTIONS

Records food distributions.

Distributions

distribution_id (PK)
inventory_id (FK)
beneficiary_id (FK)
quantity_distributed
distribution_date
distribution_status
8. REWARDS

Gamification system.

Rewards

reward_id (PK)
donor_id (FK)
points_earned
badge_name
achievement_date
Relationships
USERS
│
├── 1 : 1 ── DONORS
│
└── 1 : M ── LGUS

DONORS
│
└── 1 : M ── DONATIONS

LGUS
│
├── 1 : M ── DONATIONS
│
├── 1 : M ── FOOD_INVENTORY
│
└── 1 : M ── BENEFICIARIES

DONATIONS
│
└── 1 : 1 ── FOOD_INVENTORY

FOOD_INVENTORY
│
└── 1 : M ── DISTRIBUTIONS

BENEFICIARIES
│
└── 1 : M ── DISTRIBUTIONS

DONORS
│
└── 1 : M ── REWARDS
Visual Layout (Similar to Your Reference)
USERS ---------------- DONORS ---------------- REWARDS
  │                        │
  │                        │
  │                        │
  └------ LGUS ---------- DONATIONS
             │                │
             │                │
             │                │
             ├--------- FOOD_INVENTORY
             │                  │
             │                  │
             └------ BENEFICIARIES
                              │
                              │
                       DISTRIBUTIONS

This structure is clean because:

Users acts as the parent table for authentication.
LGUs are the food banks.
Donors submit donations.
Donations → Inventory → Distributions follows the actual food flow.
Rewards handles gamification separately.
It is normalized up to 3NF, making it suitable for database design presentations and ERD diagrams.
generate an image of it
Edit
give me a table form of the erd with columns, "column name, type, size, pk (yes, no), fk (yes, no), nullable, UNIQUE (yes, no), default, Notes

Below is a database dictionary / table specification for the ResQ Bites ERD. The data types are designed for MySQL but can easily be adapted to PostgreSQL or SQL Server.

USERS
Column Name	Type	Size	PK	FK	Nullable	Unique	Default	Notes
user_id	INT	11	Yes	No	No	Yes	Auto Increment	Unique user identifier
first_name	VARCHAR	50	No	No	No	No	-	User first name
last_name	VARCHAR	50	No	No	No	No	-	User last name
email	VARCHAR	100	No	No	No	Yes	-	Login email
password	VARCHAR	255	No	No	No	No	-	Hashed password
phone_number	VARCHAR	15	No	No	No	No	-	Contact number
role	ENUM	-	No	No	No	No	donor	admin, lgu, donor
created_at	DATETIME	-	No	No	No	No	CURRENT_TIMESTAMP	Account creation date
status	ENUM	-	No	No	No	No	active	active, inactive
DONORS
Column Name	Type	Size	PK	FK	Nullable	Unique	Default	Notes
donor_id	INT	11	Yes	No	No	Yes	Auto Increment	Donor identifier
user_id	INT	11	No	Yes	No	Yes	-	References Users
donor_type	ENUM	-	No	No	No	No	individual	individual, restaurant, hotel, supermarket, establishment
organization_name	VARCHAR	150	No	No	Yes	No	NULL	Business name if applicable
points	INT	11	No	No	No	No	0	Accumulated reward points
registration_date	DATETIME	-	No	No	No	No	CURRENT_TIMESTAMP	Registration date
LGUS
Column Name	Type	Size	PK	FK	Nullable	Unique	Default	Notes
lgu_id	INT	11	Yes	No	No	Yes	Auto Increment	LGU identifier
lgu_name	VARCHAR	150	No	No	No	No	-	LGU office name
barangay	VARCHAR	100	No	No	No	No	-	Assigned barangay
address	VARCHAR	255	No	No	No	No	-	Office address
contact_number	VARCHAR	15	No	No	No	No	-	Contact information
user_id	INT	11	No	Yes	No	No	-	LGU account head
created_at	DATETIME	-	No	No	No	No	CURRENT_TIMESTAMP	Registration date
status	ENUM	-	No	No	No	No	active	active, inactive
DONATIONS
Column Name	Type	Size	PK	FK	Nullable	Unique	Default	Notes
donation_id	INT	11	Yes	No	No	Yes	Auto Increment	Donation identifier
donor_id	INT	11	No	Yes	No	No	-	References Donors
lgu_id	INT	11	No	Yes	No	No	-	Assigned LGU
food_name	VARCHAR	100	No	No	No	No	-	Donated food
category	VARCHAR	50	No	No	No	No	-	Food category
quantity	DECIMAL	10,2	No	No	No	No	0	Quantity donated
expiration_date	DATE	-	No	No	No	No	-	Expiry date
pickup_address	VARCHAR	255	No	No	No	No	-	Pickup location
donation_status	ENUM	-	No	No	No	No	pending	pending, accepted, scheduled, collected, distributed, completed, rejected
created_at	DATETIME	-	No	No	No	No	CURRENT_TIMESTAMP	Donation date
FOOD_INVENTORY
Column Name	Type	Size	PK	FK	Nullable	Unique	Default	Notes
inventory_id	INT	11	Yes	No	No	Yes	Auto Increment	Inventory identifier
donation_id	INT	11	No	Yes	No	No	-	Source donation
lgu_id	INT	11	No	Yes	No	No	-	Managing LGU
food_name	VARCHAR	100	No	No	No	No	-	Food item
category	VARCHAR	50	No	No	No	No	-	Food category
quantity_available	DECIMAL	10,2	No	No	No	No	0	Available quantity
expiration_date	DATE	-	No	No	No	No	-	Expiration date
inventory_status	ENUM	-	No	No	No	No	available	available, low_stock, expired, consumed
date_received	DATETIME	-	No	No	No	No	CURRENT_TIMESTAMP	Received date
BENEFICIARIES
Column Name	Type	Size	PK	FK	Nullable	Unique	Default	Notes
beneficiary_id	INT	11	Yes	No	No	Yes	Auto Increment	Beneficiary identifier
lgu_id	INT	11	No	Yes	No	No	-	Managing LGU
beneficiary_name	VARCHAR	100	No	No	No	No	-	Full name
family_size	INT	3	No	No	No	No	1	Household size
contact_number	VARCHAR	15	No	No	Yes	No	NULL	Contact number
eligibility_status	ENUM	-	No	No	No	No	eligible	eligible, not_eligible
registered_at	DATETIME	-	No	No	No	No	CURRENT_TIMESTAMP	Registration date
DISTRIBUTIONS
Column Name	Type	Size	PK	FK	Nullable	Unique	Default	Notes
distribution_id	INT	11	Yes	No	No	Yes	Auto Increment	Distribution identifier
inventory_id	INT	11	No	Yes	No	No	-	References Inventory
beneficiary_id	INT	11	No	Yes	No	No	-	Recipient
quantity_distributed	DECIMAL	10,2	No	No	No	No	0	Quantity distributed
distribution_date	DATETIME	-	No	No	No	No	CURRENT_TIMESTAMP	Date distributed
distribution_status	ENUM	-	No	No	No	No	distributed	scheduled, distributed, cancelled
recorded_by	INT	11	No	Yes	No	No	-	LGU user who recorded transaction
REWARDS
Column Name	Type	Size	PK	FK	Nullable	Unique	Default	Notes
reward_id	INT	11	Yes	No	No	Yes	Auto Increment	Reward identifier
donor_id	INT	11	No	Yes	No	No	-	References Donor
points_earned	INT	11	No	No	No	No	0	Points awarded
badge_name	VARCHAR	100	No	No	Yes	No	NULL	Achievement badge
achievement_date	DATETIME	-	No	No	No	No	CURRENT_TIMESTAMP	Date earned
description	TEXT	-	No	No	Yes	No	NULL	Reward description
Foreign Key Relationships Summary
Child Table	Foreign Key	Parent Table
Donors	user_id	Users
LGUs	user_id	Users
Donations	donor_id	Donors
Donations	lgu_id	LGUs
Food_Inventory	donation_id	Donations
Food_Inventory	lgu_id	LGUs
Beneficiaries	lgu_id	LGUs
Distributions	inventory_id	Food_Inventory
Distributions	beneficiary_id	Beneficiaries
Distributions	recorded_by	LGUs.user_id
Rewards	donor_id	Donors