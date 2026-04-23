# Rules Data Architecture

## Goal

Move canonical rules content out of encounter files and into a versioned rules registry.

Encounters should describe:
- who is in the fight
- what action they choose
- caster-specific runtime values

Encounters should not duplicate:
- spell school
- spell level
- default damage expressions
- default damage types
- default save ability
- default spell metadata

## Core idea

A spell action in an encounter should look like this:
