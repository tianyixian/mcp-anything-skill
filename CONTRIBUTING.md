# Contributing

Keep each adapter's software interface explicit. A new adapter needs its own upstream provenance, typed tool contract, real minimal example, failure behavior and protocol test. Generated scaffolds are unfinished until their intended operation succeeds against the real upstream software.

Use `python -m pytest skills/mcp-anything/tests adapters/lammps/tests examples scripts/tests` for the available suite. Record which tests use a real engine and which use fixtures. Do not replace an unavailable scientific engine with a fixture and report the result as a real simulation.

Keep progress/diagnostic logs on stderr; stdout belongs to MCP. Document environment variables and version changes. Do not add automatic repository execution or general shell tools to the generic skill.
