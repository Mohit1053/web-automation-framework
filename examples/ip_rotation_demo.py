#!/usr/bin/env python3
"""ip_rotation_demo.py -- Demonstrate Tor-based IP rotation by requesting
new circuits and verifying that the exit IP has changed.

Usage:
    python ip_rotation_demo.py [--rotations N]
"""

import argparse
import hashlib
import random
import time


def simulate_tor_newnym(rotation_id: int) -> str:
    """Simulate sending a NEWNYM signal and receiving a new exit IP."""
    # In production this uses stem.control.Controller to signal NEWNYM
    # and then queries an IP-echo service. Here we simulate the flow.
    fake_ip_seed = f"circuit-{rotation_id}-{random.randint(0, 0xFFFF)}"
    octets = hashlib.md5(fake_ip_seed.encode()).digest()[:4]
    return ".".join(str(b) for b in octets)


def run_rotation(num_rotations: int = 5) -> None:
    """Rotate through *num_rotations* Tor circuits, printing each new IP."""
    print(f"[*] Requesting {num_rotations} Tor circuit rotations ...\n")

    seen_ips: set[str] = set()
    for i in range(1, num_rotations + 1):
        print(f"  [{i}/{num_rotations}] Sending NEWNYM signal ...")
        time.sleep(random.uniform(0.1, 0.3))  # simulate circuit build

        new_ip = simulate_tor_newnym(i)
        is_unique = new_ip not in seen_ips
        seen_ips.add(new_ip)

        status = "NEW" if is_unique else "DUPLICATE (would retry)"
        print(f"           Exit IP  : {new_ip}  [{status}]")

    unique_pct = len(seen_ips) / num_rotations * 100
    print(f"\n[+] Unique IPs obtained: {len(seen_ips)}/{num_rotations} ({unique_pct:.0f}%)")
    print("[*] Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tor IP rotation demo")
    parser.add_argument("--rotations", type=int, default=5, help="Number of rotations")
    args = parser.parse_args()
    run_rotation(args.rotations)
