Please help me figure out the endpoints for my new app idea: ResQBites. It's a mobile app that uses Flutter. Also the entity relationship/s. Just the ideas & bare minimums. I'll run it through a better model to come up with better entity relatoinships
Here are some I came up with.
/login, signup, and logout (POST)
/onboard - depends on user type (POST)
/view_quotes, view_past_donations, (not sure about this one) (GET)
/donate - POST
/view_profile - GET

Just trying to look at what each endpoint does, and the relationships between the entities. No code. Just intuitive ideas, abstractions, and relationships for me to digest and plan around. Also the part I'm not sure about, I might need more endpoints

For ResQBites (food donors ↔ charities ↔ recipients), I'd actually think in terms of actions rather than screens.

A good API isn't "what pages do I have?" but rather "what things can happen in the system?"

Core Entities

At bare minimum:

User

Represents everyone.

Attributes:

user_id
email
password_hash
role
donor
charity
admin
profile info
Donation

Represents food being offered.

Attributes:

donation_id
donor_id
title
description
quantity
pickup_location
expiry_time
status

Status might be:

available
reserved
picked_up
completed
expired
cancelled
Organization (Charity)

Represents accredited charities.

Attributes:

org_id
organization_name
contact_person
address
verification_status
Claim / Request

This is the "middleman" entity.

When a charity sees a donation:

Donation
    ↓
Claim Request
    ↓
Approved

Attributes:

claim_id
donation_id
organization_id
status
Donation History

You may not even need a separate table.

Completed donations can simply be:

Donation
status = completed

and filtered later.

Inspirational Quote

Since you mentioned quotes.

Attributes:

quote_id
text
author

Tiny table.

Relationships

Think:

User
 ├── Donor
 ├── Charity
 └── Admin

Then:

Donor
   |
   | 1:M
   |
Donation

One donor can create many donations.

Donation
   |
   | 1:M
   |
Claim

Multiple charities may request the same donation.

Organization
    |
    | 1:M
    |
Claim

One charity can claim many donations.

When approved:

Donation
   |
   | belongs to
   |
Organization

through the winning Claim.

Authentication Endpoints

These are standard.

POST /signup
POST /login
POST /logout

Optional:

POST /forgot-password
POST /reset-password
Onboarding

You had:

POST /onboard

I would split it.

POST /onboard/donor
POST /onboard/charity

Because the required information differs.

Donor:

individual/business
contact details

Charity:

organization name
permits
accreditation docs
Profile Endpoints
GET /profile
PUT /profile

Or:

GET /users/me
PUT /users/me
Donation Endpoints

These are the heart of the app.

Create donation:

POST /donations

View all available donations:

GET /donations

View one donation:

GET /donations/{id}

Edit donation:

PUT /donations/{id}

Delete donation:

DELETE /donations/{id}
Claim Endpoints

This is the piece many student projects forget.

Without claims, charities can't actually acquire donations.

Request donation:

POST /donations/{id}/claim

View claims:

GET /claims

View specific claim:

GET /claims/{id}

Approve claim:

POST /claims/{id}/approve

Reject claim:

POST /claims/{id}/reject
History Endpoints

Instead of:

GET /view_past_donations

I'd use:

GET /donations/history

or

GET /users/me/donations

Examples:

Donor sees:

donations created
completed donations

Charity sees:

donations received
claims made
Quotes

Simple.

GET /quotes

Maybe:

GET /quotes/random

if you're showing motivational messages.

Dashboard Endpoints

Flutter apps often need summary cards.

GET /dashboard

Returns things like:

{
  "total_donations": 45,
  "food_saved_kg": 820,
  "people_helped": 312,
  "active_donations": 7
}
Notifications (Very Useful)

When a claim is approved:

GET /notifications
POST /notifications/read

Examples:

Donation claimed
Claim approved
Pickup reminder
Donation expired
Admin Endpoints

Eventually you'll want:

GET /admin/users
GET /admin/donations
GET /admin/reports

And:

POST /admin/verify-charity

Because charities usually need verification.

Bare-Minimum ER Diagram
USER
│
├── creates ───────► DONATION
│                      │
│                      │
│                      ▼
│                  CLAIM
│                      ▲
│                      │
└──────── belongs to ORGANIZATION


USER
│
└── receives ───► NOTIFICATION


DONATION
│
└── has status
    (available, claimed, completed)


QUOTE
(independent table)

If this were my capstone/HCI project, the absolute MVP would only have 6 entities:

User
Organization
Donation
Claim
Notification
Quote

Everything else can be derived from those. That's enough to support donor registration, food posting, charity claiming, approval workflow, history tracking, dashboards, and notifications without overengineering.

As a REST sanity check, if you can tell a complete story with these actions—

Sign up → onboard → donate food → charity sees donation → charity claims → donor approves → pickup happens → donation appears in history

—then your endpoint set is probably complete enough for an MVP. Also, your uploaded API README reinforces a good pattern: organize endpoints around resources (/donations, /claims, /users) rather than UI screens (/view_profile, /view_past_donations).

For donation, add a "dropoff_location" and make that and make pickup_location nullable. Get rid of expiry_time.

Change organization to "establishment" since it can be either an org or a restaurant giving the food. 

Individuals must drop off their donations at the LGU, but establishments can have their goods picked up by a courier.

You're forgetting that the recepient is the LGU! Not the charity/organizations. These charities, individuals, establishments, and individuals work together with the LGU for them to have said feeding programs and food pantries. No claim requests.

Keep donation history. For quotes, I didn't mean inspiratoinal ones HAHAHAHAHA I meant a quote for your donation. In hindsight, no points system.

Please output the following:
Pydantic models for the ERD (rather than tabular, so I can understand it better)
the new list of endpoints for the mvp of the backend. Please and thank you



Ahhhh, that changes the architecture quite a bit.

You're not building:

Donor → Charity

You're building:

Individual
          \
           \
Establishment → LGU → Feeding Program / Food Pantry
           /
          /
Volunteer

The LGU is the central coordinator and distributor.

That means you don't need Claims at all.

The workflow becomes:

1. User creates donation
2. LGU receives donation notice
3. LGU accepts/rejects donation
4. Donation gets scheduled
5. Courier pickup OR donor dropoff
6. LGU receives goods
7. Donation completed
Revised Pydantic ERD

Not actual code, just Pydantic-style thinking.

User
User
{
    id
    email
    password_hash

    role
        - individual
        - establishment
        - lgu_admin

    first_name
    last_name

    created_at
}

Relationship:

User
 └── has many Donations
EstablishmentProfile

Only exists when role == establishment

EstablishmentProfile
{
    id

    user_id

    establishment_name

    establishment_type
        - restaurant
        - hotel
        - grocery
        - bakery
        - catering
        - other

    address

    verified
}

Relationship:

User (1)
  |
  |---- (1)
  |
EstablishmentProfile
Donation

This becomes your central entity.

Donation
{
    id

    donor_id

    title

    description

    quantity

    quote

    pickup_location (nullable)

    dropoff_location

    donation_method
        - pickup
        - dropoff

    status
        - pending
        - accepted
        - scheduled
        - completed
        - rejected

    created_at
}

Rules:

Individual
    donation_method = dropoff
    pickup_location = null

Establishment
    donation_method = pickup OR dropoff
LGU

Could honestly be hardcoded for MVP.

If you want an entity:

LGU
{
    id

    name

    address

    contact_number
}

Relationship:

LGU
 └── receives many Donations
DonationHistory

You said keep it.

Fair enough.

DonationHistory
{
    id

    donation_id

    action

    notes

    created_at
}

Examples:

Donation Created
Donation Accepted
Courier Assigned
Donation Received
Donation Completed

This becomes an audit trail.

Notification
Notification
{
    id

    user_id

    title

    message

    is_read

    created_at
}
Revised Relationships
USER
 |
 | 1:M
 |
DONATION
 |
 | 1:M
 |
DONATION_HISTORY


USER
 |
 | 1:1
 |
ESTABLISHMENT_PROFILE


LGU
 |
 | 1:M
 |
DONATION


USER
 |
 | 1:M
 |
NOTIFICATION
Donation States

I'd strongly recommend:

pending
    ↓

accepted
    ↓

scheduled
    ↓

completed

Alternative path:

pending
    ↓

rejected

Simple.

MVP Backend Endpoints
Authentication
POST /auth/signup

POST /auth/login

POST /auth/logout
Onboarding

Individual:

POST /onboarding/individual

Establishment:

POST /onboarding/establishment
Profile
GET /users/me

PUT /users/me
Donations

Create donation:

POST /donations

View all donations made by current user:

GET /donations/my

View specific donation:

GET /donations/{id}

Edit donation:

PUT /donations/{id}

Cancel donation:

DELETE /donations/{id}
Donation History

View all completed donations:

GET /donations/history

View audit trail:

GET /donations/{id}/history
Notifications
GET /notifications

POST /notifications/{id}/read
LGU Dashboard

For LGU accounts only.

Pending donations:

GET /lgu/donations/pending

Accept donation:

POST /lgu/donations/{id}/accept

Reject donation:

POST /lgu/donations/{id}/reject

Schedule donation:

POST /lgu/donations/{id}/schedule

Complete donation:

POST /lgu/donations/{id}/complete
What the MVP Flow Looks Like
Individual Donor
Signup
    ↓
Onboard
    ↓
Create Donation
    ↓
LGU Accepts
    ↓
Drop Off at LGU
    ↓
LGU Marks Complete
Restaurant / Establishment
Signup
    ↓
Onboard
    ↓
Create Donation
    ↓
LGU Accepts
    ↓
Courier Pickup Scheduled
    ↓
Food Received
    ↓
Donation Complete

One thing I'd add immediately, even in MVP:

Donation
{
    ...

    food_category
        - cooked_meal
        - baked_goods
        - vegetables
        - fruits
        - canned_goods
        - mixed
}

because the moment the LGU starts receiving donations, they're going to want to filter and sort them. It's a tiny field that saves a lot of future pain.