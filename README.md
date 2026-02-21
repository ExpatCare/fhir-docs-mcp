# fhir-docs-mcp

An MCP server that gives LLMs accurate access to **FHIR R5 (5.0.0)** resource definitions — so they stop guessing schemas and start looking them up.

Built on the official HL7 StructureDefinition JSON bundle. Ships all 162 R5 resources, no network calls needed.

## Why

LLMs frequently hallucinate FHIR field names, cardinalities, and data types. This server lets Claude (or any MCP client) look up the real structure of any FHIR resource on demand — mandatory fields, types, value set bindings, and all.

## Tools

| Tool | What it does |
|------|-------------|
| `get_resource_definition` | Top-level elements of a resource (e.g. Patient, Observation) |
| `get_backbone_element` | Drill into nested BackboneElements (e.g. Patient.contact) |
| `search_fhir_elements` | Keyword search across all 162 resources |

### Example output

**`get_resource_definition("Patient")`**

```
============================================================
  Patient
============================================================

Information about an individual or animal receiving health care services

----------------------------------------
  Elements
----------------------------------------

  identifier (0..*) : Identifier
      An identifier for this patient

  active (0..1) : boolean
      Whether this patient's record is in active use

  name (0..*) : HumanName
      A name associated with the patient

  gender (0..1) : code
      male | female | other | unknown
      binding: required (http://hl7.org/fhir/ValueSet/administrative-gender|5.0.0)

  deceased[x] (0..1) : boolean | dateTime
      Indicates if the individual is deceased or not

  contact (0..*) : BackboneElement
      A contact party (e.g. guardian, partner, friend) for the patient
       → use get_backbone_element to expand
  ...
```

**`get_backbone_element("Patient", "Patient.contact")`**

```
============================================================
  Patient  —  Patient.contact
============================================================

A contact party (e.g. guardian, partner, friend) for the patient

----------------------------------------
  Child elements
----------------------------------------

  relationship (0..*) : CodeableConcept
      The kind of relationship
      binding: extensible (http://hl7.org/fhir/ValueSet/patient-contactrelationship)

  name (0..1) : HumanName
      A name associated with the contact person

  organization (0..1) : Reference(Organization)
      Organization that is associated with the contact
  ...
```

## Setup

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/maximecharriere/fhir-docs-mcp.git
cd fhir-docs-mcp
uv sync
```

### Add to Claude Code

```bash
claude mcp add fhir-r5 -- uv run --directory /path/to/fhir-docs-mcp fhir-mcp
```

### Add to Claude Desktop

Add this to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "fhir-r5": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/fhir-docs-mcp", "fhir-mcp"]
    }
  }
}
```

### Development

Run the MCP Inspector to test tools interactively:

```bash
uv run fastmcp dev inspector src/fhir_mcp/server.py:mcp
```

## Project structure

```
fhir-docs-mcp/
├── definitions/
│   └── definitions.json/
│       └── profiles-resources.json   # Official HL7 FHIR R5 bundle
├── src/
│   └── fhir_mcp/
│       ├── __init__.py
│       ├── parser.py                 # FHIR JSON parsing (no MCP dependency)
│       └── server.py                 # MCP server, tools, formatting
└── pyproject.toml
```

## License

MIT
