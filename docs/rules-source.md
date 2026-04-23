# Rules Source

## Canonical source

The simulator should use **SRD 5.2.1** as the canonical public rules source.

That gives the project a clean legal boundary for:
- combat procedures
- creatures and stat blocks
- actions
- equipment
- spells that are actually present in the SRD subset
- conditions and other openly reusable mechanics

## Project rule-ingestion policy

The simulator must distinguish between:

1. **Open mechanical content**
   - numeric stats
   - turn structure
   - action economy
   - attack, damage, save, and condition logic
   - openly available monsters, items, spells, and rules text that are part of the SRD subset

2. **Non-open product content**
   - non-SRD story text
   - non-SRD subclasses, monsters, spells, lore, adventures, settings, and book prose
   - copyrighted text copied from non-open books or webpages

## Safe implementation boundary

The codebase should primarily store:
- normalized mechanics
- structured data
- derived machine-readable content
- short field labels
- internal engine comments written by us

The codebase should avoid:
- copying long prose passages from non-open books
- bundling non-open rulebook text into JSON fixtures
- mixing open and non-open data sources without provenance

## Source registry model

Every imported rules dataset should have provenance metadata:
