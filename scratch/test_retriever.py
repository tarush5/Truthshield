import sys
import os
import asyncio

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.factcheck.evidence_retriever import EvidenceRetriever
from backend.models.schemas import Claim

async def main():
    retriever = EvidenceRetriever()
    claim = Claim(text="New study claims drinking coffee cures COVID-19 within 24 hours.", entity="coffee")
    
    print("Testing EvidenceRetriever.retrieve()...")
    evidence = await retriever.retrieve(claim)
    
    print(f"\nRetrieved {len(evidence)} evidence items:")
    for i, ev in enumerate(evidence):
        print(f"\n[{i+1}] Title: {ev.title}")
        print(f"    URL: {ev.url}")
        print(f"    Snippet: {ev.snippet[:120]}...")
        print(f"    Source Score: {ev.source_score}")

if __name__ == "__main__":
    asyncio.run(main())
