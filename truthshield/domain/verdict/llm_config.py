"""
Model identifiers for the optional LLM verdict paths.

Kept separate from settings because these are code-level constants (which
model this version of the engine was written and calibrated against), not
deployment configuration. The API keys that enable them are in settings.
"""

CLAUDE_MODEL = "claude-sonnet-5"
CLAUDE_MAX_TOKENS = 1024

# flash-lite stays primary: gemini-2.5-flash returned 404 on this project's
# key. The fallbacks are all real model names — an earlier chain listed
# gemini-3.5-flash and gemini-3.1-flash-lite, which do not exist, so every
# call burned the full retry budget before giving up.
GEMINI_MODEL = "gemini-2.5-flash-lite"
GEMINI_FALLBACK_MODELS = ["gemini-2.5-flash-lite", "gemini-2.0-flash", "gemini-2.5-flash"]
GEMINI_MAX_TOKENS = 1024
