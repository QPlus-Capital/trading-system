"""Deterministic property-test settings shared by local and CI runs."""

from hypothesis import settings

settings.register_profile(
    "qplus",
    derandomize=True,
    database=None,
    deadline=None,
    max_examples=75,
    print_blob=True,
)
settings.load_profile("qplus")
