"""
license_generator.py — Developer Key Generator CLI Tool
Meat Products of India — Billing & Inventory Management App

Use this script to generate valid 12-digit activation codes for annual subscriptions.
Usage:
  python license_generator.py [--count N] [--note "Client Name / Outlet #1"]
"""

import sys
import random
import string
import hmac
import hashlib
import argparse

# Cryptographic Salt (Must match license_manager.py)
LICENSE_SECRET_SALT = "MPI_MEATSHOP_SUB_KEY_SALT_2025_SECRET_#99!"

# Allowed character set for 12-digit keys (omitting confusing 0/O, 1/I if desired, or full set)
CHARSET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

def generate_key():
    """Generate a valid 12-character cryptographic activation key."""
    payload = "".join(random.choices(CHARSET, k=8))
    checksum = hmac.new(
        LICENSE_SECRET_SALT.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()[:4].upper()
    
    full_key = payload + checksum
    formatted = f"{full_key[:4]}-{full_key[4:8]}-{full_key[8:]}"
    return full_key, formatted

def main():
    parser = argparse.ArgumentParser(description="Generate 12-digit activation keys for subscription.")
    parser.add_argument("-c", "--count", type=int, default=1, help="Number of keys to generate (default: 1)")
    parser.add_argument("-n", "--note", type=str, default="", help="Optional note or customer outlet name")
    args = parser.parse_args()

    print("=================================================================")
    print(" [KEY GENERATOR] MPI BILLING SOFTWARE - 12-DIGIT ACTIVATION KEY")
    print(" Subscription Duration: 365 Days + 10 Days Grace Period")
    print(" Yearly Price: Rs 12,000 / Outlet (Custom developer discounts may apply)")
    if args.note:
        print(f" Outlet / Client: {args.note}")
    print("=================================================================")

    for i in range(args.count):
        raw_key, formatted_key = generate_key()
        print(f" Key #{i+1}:  {formatted_key}   (Raw: {raw_key})")

    print("=" * 65)
    print(" Send the 12-digit code (e.g. XXXX-XXXX-XXXX) to the customer after UPI payment confirmation.")
    print("=" * 65)

if __name__ == "__main__":
    main()
