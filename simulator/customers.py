"""Synthetic customer generator."""

import random
from typing import List
from core.entities import Customer

FIRST_NAMES = [
    "Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh", "Ayaan",
    "Krishna", "Ishaan", "Diya", "Saanvi", "Ananya", "Aadhya", "Pari", "Chiara",
    "Myra", "Riya", "Anushka", "Isha", "Neha", "Pooja", "Vikram", "Rahul", "Kavya"
]

LAST_NAMES = [
    "Sharma", "Verma", "Patel", "Reddy", "Nair", "Iyer", "Rao", "Mehta",
    "Deshmukh", "Choudhury", "Bose", "Gupta", "Singh", "Das", "Joshi", "Kulkarni"
]


def generate_customer(customer_id: str, rng: random.Random) -> Customer:
    """Generate a realistic synthetic customer with behavioral characteristics."""
    first = rng.choice(FIRST_NAMES)
    last = rng.choice(LAST_NAMES)
    name = f"{first} {last}"
    phone_digits = "".join(str(rng.randint(0, 9)) for _ in range(10))
    phone = f"+919{phone_digits[1:]}"
    email = f"{first.lower()}.{last.lower()}{rng.randint(10, 99)}@example.in"

    # Risk score distribution: skewed towards low-to-medium risk
    risk_score = round(rng.betavariate(2, 5), 3)

    # 5% of simulated customers have opted out / DND active
    opted_out = rng.random() < 0.05

    return Customer(
        id=customer_id,
        name=name,
        phone=phone,
        email=email,
        risk_score=risk_score,
        opted_out=opted_out,
        contact_count=0,
        timezone="Asia/Kolkata"
    )
