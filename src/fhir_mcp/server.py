"""FHIR R5 MCP server — exposes StructureDefinition look-up tools."""

from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastmcp import FastMCP, Context

from fhir_mcp.parser import (
    ElementInfo,
    FHIRIndex,
    load_index,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SERVER_NAME = "fhir-r5"
CTX_KEY_INDEX = "fhir_index"

TOOL_DESC_RESOURCE = (
    "Return the top-level element list for a FHIR R5 resource type "
    "(e.g. 'Patient', 'Observation'). BackboneElement fields can be "
    "expanded with get_backbone_element."
)
TOOL_DESC_BACKBONE = (
    "Expand a BackboneElement within a FHIR R5 resource. "
    "Provide the resource type and the full dotted path "
    "(e.g. resource_type='Patient', path='Patient.contact')."
)
TOOL_DESC_SEARCH = (
    "Search across all FHIR R5 resource elements by keyword. "
    "Matches against the short description and definition fields."
)

BACKBONE_HINT = "  \u2192 use get_backbone_element to expand"
TRUNCATION_NOTE = "\n(Results capped at {limit} — refine your keyword for more specific results.)"

HEADER_SEP = "=" * 60
SECTION_SEP = "-" * 40


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _format_element_line(el: ElementInfo) -> str:
    """Format a single element as a compact text line."""
    leaf = el.path.rsplit(".", maxsplit=1)[-1]
    cardinality = f"{el.min}..{el.max}"
    line = f"  {leaf} ({cardinality}) : {el.type_display}"
    if el.short:
        line += f"\n      {el.short}"
    if el.binding_strength:
        line += f"\n      binding: {el.binding_strength}"
        if el.binding_value_set:
            line += f" ({el.binding_value_set})"
    if el.is_backbone:
        line += f"\n     {BACKBONE_HINT}"
    return line


def _format_resource_summary(
    name: str, description: str, elements: list[ElementInfo]
) -> str:
    """Format full resource summary as text."""
    lines = [
        HEADER_SEP,
        f"  {name}",
        HEADER_SEP,
        "",
        description,
        "",
        SECTION_SEP,
        "  Elements",
        SECTION_SEP,
        "",
    ]
    for el in elements:
        lines.append(_format_element_line(el))
        lines.append("")
    return "\n".join(lines)


def _format_backbone_summary(
    resource_type: str,
    path: str,
    parent_short: str,
    children: list[ElementInfo],
) -> str:
    """Format backbone element children as text."""
    lines = [
        HEADER_SEP,
        f"  {resource_type}  \u2014  {path}",
        HEADER_SEP,
        "",
        parent_short,
        "",
        SECTION_SEP,
        "  Child elements",
        SECTION_SEP,
        "",
    ]
    for el in children:
        lines.append(_format_element_line(el))
        lines.append("")
    return "\n".join(lines)


def _format_search_results(
    keyword: str, results: list[ElementInfo], limit: int
) -> str:
    """Format search results as text."""
    if not results:
        return f"No elements matched '{keyword}'."

    lines = [f"Search results for '{keyword}' ({len(results)} matches):", ""]
    for el in results:
        cardinality = f"{el.min}..{el.max}"
        line = f"  {el.path} ({cardinality}) : {el.type_display}"
        if el.short:
            line += f"\n      {el.short}"
        lines.append(line)
        lines.append("")

    if len(results) >= limit:
        lines.append(TRUNCATION_NOTE.format(limit=limit))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Lifespan — load FHIR data once at startup
# ---------------------------------------------------------------------------

@asynccontextmanager
async def fhir_lifespan(server: FastMCP) -> AsyncIterator[dict]:
    index = load_index()
    yield {CTX_KEY_INDEX: index}


# ---------------------------------------------------------------------------
# MCP server instance
# ---------------------------------------------------------------------------
mcp = FastMCP(SERVER_NAME, lifespan=fhir_lifespan)


def _get_index(ctx: Context) -> FHIRIndex:
    return ctx.request_context.lifespan_context[CTX_KEY_INDEX]


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool(description=TOOL_DESC_RESOURCE)
def get_resource_definition(resource_type: str, ctx: Context) -> str:
    """Return the top-level structure of a FHIR R5 resource."""
    index = _get_index(ctx)
    try:
        name, description, elements = index.get_resource_summary(resource_type)
    except KeyError:
        available = index.list_resources()
        return (
            f"Unknown resource type '{resource_type}'.\n"
            f"Available resources ({len(available)}):\n"
            + ", ".join(available)
        )
    return _format_resource_summary(name, description, elements)


@mcp.tool(description=TOOL_DESC_BACKBONE)
def get_backbone_element(resource_type: str, path: str, ctx: Context) -> str:
    """Expand a BackboneElement to show its child elements."""
    index = _get_index(ctx)
    try:
        parent_short, children = index.get_backbone_children(resource_type, path)
    except KeyError:
        available = index.list_resources()
        return (
            f"Unknown resource type '{resource_type}'.\n"
            f"Available resources ({len(available)}):\n"
            + ", ".join(available)
        )
    except ValueError as exc:
        return str(exc)
    return _format_backbone_summary(resource_type, path, parent_short, children)


@mcp.tool(description=TOOL_DESC_SEARCH)
def search_fhir_elements(keyword: str, ctx: Context) -> str:
    """Search for FHIR elements by keyword across all resources."""
    index = _get_index(ctx)
    from fhir_mcp.parser import DEFAULT_SEARCH_LIMIT

    results = index.search_elements(keyword, limit=DEFAULT_SEARCH_LIMIT)
    return _format_search_results(keyword, results, DEFAULT_SEARCH_LIMIT)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    mcp.run(transport="stdio")
