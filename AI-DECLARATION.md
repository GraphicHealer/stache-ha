---
version: "0.1.2"
level: pair
processes:
  design: pair
  implementation: pair
  testing: pair
  documentation: pair
  review: pair
  deployment: pair
---

This format is based on [AI-DECLARATION.md](https://ai-declaration.md/en/0.1.2).

## Notes

- Stache for Home Assistant is built by a human (product direction,
  requirements, testing on a live HA instance, review) pairing with an AI
  agent (Devin, Cognition) that writes most of the code. The human
  understands the internals and reviews every change; nothing ships without
  the human verifying it in Home Assistant.
