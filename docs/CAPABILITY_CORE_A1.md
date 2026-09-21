# Akane Bot v4 — Capability Core A1

A1 introduces the **runtime vocabulary only** for the future capability layer.

## Components

`services/capability_core.py` provides:

- `CapabilityRisk`
- `CapabilitySpec`
- `CapabilityContext`
- `CapabilityRequest`
- `CapabilityResult`
- `CapabilityRegistry`
- `CapabilityDispatcher`

## Boundary

A1 deliberately does not:

- register production capabilities;
- modify slash callbacks;
- call Jev;
- perform natural-language discovery;
- add Discord buttons/select menus;
- change database/schema;
- change AI model routing;
- change permissions;
- deploy.

## Confirmation contract

The initial risk vocabulary is:

```text
READ_ONLY
WRITE_CONFIRM
MODERATION
ADMIN
```

Every non-`READ_ONLY` `CapabilitySpec` must declare `requires_confirmation=True`.

This is a structural fail-closed rule. It does **not** replace Discord authorization. Future moderation/admin adapters must satisfy both:

```text
Discord authorization
AND
capability confirmation policy
```

## Dispatcher contract

`CapabilityDispatcher` executes only when:

1. the capability exists in the registry;
2. a handler has been explicitly registered;
3. required confirmation is present.

It does not infer intent and does not choose models.

## Router separation

The future Capability Router answers:

> Which bot action might the user want?

The existing AI Model Router answers:

> Which AI model should answer this request?

These remain separate control planes.

## Next phase

B1 should register a small progression pilot (for example level/profile/achievements/weekly/rankings) and route existing slash callbacks through shared handlers before any natural-language execution is enabled.
