"""
TruthShield 2.0 investigations.

An investigation is one submission taken through the universal pipeline
(`pipeline.py`) by pluggable engines (`engines/`), scored by the central risk
engine (`risk.py`) and explained deterministically (`explain.py`). Every
stage is recorded, every signal carries its provenance, and everything the
engines could not check is reported as uncertainty.
"""
