"""Shared core: strategy signals, instruments, broker cost profiles, data ingest.

Strategy- and venue-neutral building blocks used by all three worlds (research, live,
monitoring). The current instance trades one strategy on one venue, but nothing here is
hard-wired to that -- new strategies/venues plug in alongside.
"""
