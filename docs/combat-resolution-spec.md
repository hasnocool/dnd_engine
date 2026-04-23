# Combat Resolution Spec

## Scope

This document defines the first-pass combat engine behavior.

This version intentionally supports:
- initiative
- turns
- attacks
- damage
- simple conditions
- win/draw detection

## Encounter input

An encounter contains:
- name
- seed
- round_limit
- combatants

Each combatant contains:
- id
- name
- team
- armor class
- current/max hp
- initiative bonus
- actions
- conditions

## Initiative

Each combatant rolls:
