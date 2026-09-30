"""
Detector plugins.

Importing this package registers every detector. Adding a fraud category
means adding a module here and one import line -- the router, the scoring
and the API are untouched, which is the property the plugin layer exists to
provide.
"""

from truthshield.fraud.detectors import email, message, url  # noqa: F401

__all__ = ["email", "message", "url"]
