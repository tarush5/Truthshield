from backend.factcheck.claim_extractor import ClaimExtractor
from pydantic import BaseModel
import logging

logging.basicConfig(level=logging.INFO)

extractor = ClaimExtractor()
claims = extractor.extract("The Earth is definitively flat and NASA admits it.", lang="en")
print(f"Extracted claims: {[c.text for c in claims]}")
