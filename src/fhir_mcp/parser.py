"""FHIR R5 StructureDefinition parser — no MCP dependency."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# JSON field-name constants
# ---------------------------------------------------------------------------
KEY_RESOURCE_TYPE = "resourceType"
KEY_SNAPSHOT = "snapshot"
KEY_ELEMENT = "element"
KEY_PATH = "path"
KEY_MIN = "min"
KEY_MAX = "max"
KEY_TYPE = "type"
KEY_CODE = "code"
KEY_SHORT = "short"
KEY_DEFINITION = "definition"
KEY_BINDING = "binding"
KEY_STRENGTH = "strength"
KEY_VALUE_SET = "valueSet"
KEY_TARGET_PROFILE = "targetProfile"
KEY_ENTRY = "entry"
KEY_RESOURCE = "resource"
KEY_NAME = "name"
KEY_KIND = "kind"

# ---------------------------------------------------------------------------
# Type / URL constants
# ---------------------------------------------------------------------------
RESOURCE_TYPE_STRUCTURE_DEFINITION = "StructureDefinition"
KIND_RESOURCE = "resource"
TYPE_BACKBONE_ELEMENT = "BackboneElement"
TYPE_REFERENCE = "Reference"
POLYMORPHIC_MARKER = "[x]"
FHIR_STRUCTURE_URL_PREFIX = "http://hl7.org/fhir/StructureDefinition/"

# ---------------------------------------------------------------------------
# Filter / default constants
# ---------------------------------------------------------------------------
INFRASTRUCTURE_ELEMENT_NAMES: frozenset[str] = frozenset(
    {
        "id",
        "extension",
        "modifierExtension",
        "meta",
        "implicitRules",
        "language",
        "text",
        "contained",
    }
)

DEFAULT_SEARCH_LIMIT = 30

DEFINITIONS_REL_PATH = Path("definitions/definitions.json/profiles-resources.json")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class ElementInfo:
    path: str
    min: int
    max: str  # "1" or "*"
    type_display: str  # e.g. "Reference(Organization | Practitioner)"
    short: str
    is_backbone: bool
    is_polymorphic: bool
    binding_strength: str | None  # "required", "extensible", …
    binding_value_set: str | None


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _extract_target_names(target_profiles: list[str]) -> list[str]:
    """Strip the FHIR StructureDefinition URL prefix from target profiles."""
    return [
        url.removeprefix(FHIR_STRUCTURE_URL_PREFIX)
        for url in target_profiles
    ]


def _format_type(type_list: list[dict]) -> str:
    """Format a FHIR element *type* array into a human-readable string."""
    if not type_list:
        return ""

    parts: list[str] = []
    for t in type_list:
        code = t.get(KEY_CODE, "")
        if code == TYPE_REFERENCE:
            targets = _extract_target_names(t.get(KEY_TARGET_PROFILE, []))
            if targets:
                parts.append(f"Reference({' | '.join(targets)})")
            else:
                parts.append(TYPE_REFERENCE)
        else:
            parts.append(code)

    return " | ".join(parts)


def _make_element_info(raw: dict) -> ElementInfo:
    """Convert a raw FHIR element dict into an `ElementInfo`."""
    path: str = raw.get(KEY_PATH, "")
    type_list: list[dict] = raw.get(KEY_TYPE, [])
    binding = raw.get(KEY_BINDING, {})

    is_backbone = any(
        t.get(KEY_CODE) == TYPE_BACKBONE_ELEMENT for t in type_list
    )
    is_polymorphic = POLYMORPHIC_MARKER in path

    return ElementInfo(
        path=path,
        min=raw.get(KEY_MIN, 0),
        max=raw.get(KEY_MAX, "0"),
        type_display=_format_type(type_list),
        short=raw.get(KEY_SHORT, ""),
        is_backbone=is_backbone,
        is_polymorphic=is_polymorphic,
        binding_strength=binding.get(KEY_STRENGTH),
        binding_value_set=binding.get(KEY_VALUE_SET),
    )


def _get_direct_children(
    elements: list[dict], parent_path: str
) -> list[dict]:
    """Return elements exactly one dot-level deeper than *parent_path*."""
    prefix = parent_path + "."
    depth = prefix.count(".")
    return [
        el
        for el in elements
        if el.get(KEY_PATH, "").startswith(prefix)
        and el[KEY_PATH].count(".") == depth
    ]


def _leaf_name(path: str) -> str:
    """Return the last segment of a dotted path."""
    return path.rsplit(".", maxsplit=1)[-1]


# ---------------------------------------------------------------------------
# FHIRIndex
# ---------------------------------------------------------------------------
class FHIRIndex:
    """In-memory index over FHIR R5 StructureDefinitions."""

    def __init__(self, bundle: dict) -> None:
        self._resources: dict[str, dict] = {}
        self._resource_names: dict[str, str] = {}

        for entry in bundle.get(KEY_ENTRY, []):
            resource = entry.get(KEY_RESOURCE, {})
            if (
                resource.get(KEY_RESOURCE_TYPE) == RESOURCE_TYPE_STRUCTURE_DEFINITION
                and resource.get(KEY_KIND) == KIND_RESOURCE
                and resource.get(KEY_SNAPSHOT)
            ):
                name: str = resource[KEY_NAME]
                key = name.lower()
                self._resources[key] = resource
                self._resource_names[key] = name

    # -- public API --------------------------------------------------------

    def list_resources(self) -> list[str]:
        """Return sorted list of canonical resource names."""
        return sorted(self._resource_names.values())

    def get_resource_summary(
        self, resource_type: str
    ) -> tuple[str, str, list[ElementInfo]]:
        """Return *(canonical_name, root_definition, top_level_elements)*.

        Top-level elements are depth-1 only; infrastructure elements are
        filtered out.  Raises ``KeyError`` if *resource_type* is unknown.
        """
        key = resource_type.lower()
        if key not in self._resources:
            raise KeyError(resource_type)

        sd = self._resources[key]
        canonical = self._resource_names[key]
        elements = sd[KEY_SNAPSHOT][KEY_ELEMENT]

        root_def = elements[0].get(KEY_SHORT, "") if elements else ""

        children = _get_direct_children(elements, canonical)
        infos = [
            _make_element_info(el)
            for el in children
            if _leaf_name(el[KEY_PATH]) not in INFRASTRUCTURE_ELEMENT_NAMES
        ]
        return canonical, root_def, infos

    def get_backbone_children(
        self, resource_type: str, path: str
    ) -> tuple[str, list[ElementInfo]]:
        """Return *(parent_short_desc, direct_children)* for a BackboneElement.

        Raises ``KeyError`` if the resource is unknown or ``ValueError`` if
        the path is not a BackboneElement inside that resource.
        """
        key = resource_type.lower()
        if key not in self._resources:
            raise KeyError(resource_type)

        sd = self._resources[key]
        elements = sd[KEY_SNAPSHOT][KEY_ELEMENT]

        # Find the parent element
        parent_raw = None
        for el in elements:
            if el.get(KEY_PATH) == path:
                parent_raw = el
                break

        if parent_raw is None:
            raise ValueError(f"Path '{path}' not found in {resource_type}")

        parent_types = parent_raw.get(KEY_TYPE, [])
        is_backbone = any(
            t.get(KEY_CODE) == TYPE_BACKBONE_ELEMENT for t in parent_types
        )
        if not is_backbone:
            raise ValueError(f"Path '{path}' is not a BackboneElement")

        parent_short = parent_raw.get(KEY_SHORT, "")
        children = _get_direct_children(elements, path)
        infos = [
            _make_element_info(el)
            for el in children
            if _leaf_name(el[KEY_PATH]) not in INFRASTRUCTURE_ELEMENT_NAMES
        ]
        return parent_short, infos

    def search_elements(
        self, keyword: str, limit: int = DEFAULT_SEARCH_LIMIT
    ) -> list[ElementInfo]:
        """Case-insensitive substring search across *short* and *definition*."""
        kw = keyword.lower()
        results: list[ElementInfo] = []

        for sd in self._resources.values():
            for el in sd[KEY_SNAPSHOT][KEY_ELEMENT]:
                short = el.get(KEY_SHORT, "")
                definition = el.get(KEY_DEFINITION, "")
                if kw in short.lower() or kw in definition.lower():
                    results.append(_make_element_info(el))
                    if len(results) >= limit:
                        return results
        return results


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def load_index(base_dir: Path | None = None) -> FHIRIndex:
    """Load the FHIR R5 profiles-resources bundle and return a `FHIRIndex`.

    *base_dir* defaults to the project root (two levels up from this file's
    package directory).
    """
    if base_dir is None:
        # src/fhir_mcp/parser.py -> src/fhir_mcp -> src -> project root
        base_dir = Path(__file__).resolve().parent.parent.parent

    path = base_dir / DEFINITIONS_REL_PATH
    with path.open() as f:
        bundle = json.load(f)
    return FHIRIndex(bundle)
