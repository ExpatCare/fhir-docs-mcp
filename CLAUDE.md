# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

MCP server exposing FHIR R5 (5.0.0) resource definitions from the official HL7 JSON bundle. Three tools: `get_resource_definition`, `get_backbone_element`, `search_fhir_elements`.

## Commands

```bash
uv sync                                                       # install deps
uv run fhir-mcp                                               # run server (stdio)
uv run fastmcp dev inspector src/fhir_mcp/server.py:mcp       # interactive inspector
```

No test suite yet.

## Architecture

Two modules with a strict dependency boundary — `parser.py` has zero MCP knowledge, `server.py` has zero JSON-parsing knowledge.

- **`parser.py`** — Loads the FHIR bundle (44MB, Git LFS) into `FHIRIndex`. Elements built on-demand from raw StructureDefinition dicts. Factory: `load_index()`.
- **`server.py`** — FastMCP server with lifespan loading the index once at startup. Tool functions call parser methods, format as plain text.

## Conventions

- All JSON field names and FHIR constants are module-level `KEY_*` / `TYPE_*` / `FHIR_*` constants — never inline raw strings for these.
- Infrastructure elements are filtered from output via `INFRASTRUCTURE_ELEMENT_NAMES` frozenset in `parser.py`.
- Tool descriptions and formatting strings are module-level constants in `server.py`.
- `ElementInfo` is a frozen dataclass — treat as immutable.
