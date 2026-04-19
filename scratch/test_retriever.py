import asyncio
import os
import sys

# Add project root to sys path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.factcheck.evidence_retriever import EvidenceRetriever
from backend.models.schemas import Claim

def main():
    retriever = EvidenceRetriever()
    claim = Claim(
        text="The Earth is flat",
        entity="Earth"
    )
    
    print(f"Retrieving evidence for: '{claim.text}'")
    evidence = retriever.retrieve(claim)
    
    print(f"Found {len(evidence)} pieces of evidence:")
    for e in evidence:
        print(f"- {e.title} ({e.url})")

if __name__ == "__main__":
    main()
