"""Structural validation of tool descriptors returned by tools/list.

These checks look for malformed or suspicious schemas. A schema that
passes every check is *structurally* well formed -- it says nothing
about whether the server behind it behaves safely.
"""

_PROPERTY_KEYS = ("type", "$ref", "anyOf", "oneOf", "allOf", "enum", "const")


def validate_tools(tools):
    """Return a list of issue strings (empty means no problems found)."""
    issues = []
    if not isinstance(tools, list):
        return ["tools/list result is not a list"]
    seen_names = set()
    for index, tool in enumerate(tools):
        label = f"tools[{index}]"
        if not isinstance(tool, dict):
            issues.append(f"{label}: not an object")
            continue
        name = tool.get("name")
        if not isinstance(name, str) or not name:
            issues.append(f"{label}: missing or invalid 'name'")
            label = f"tools[{index}]"
        else:
            label = f"tool {name!r}"
            if name in seen_names:
                issues.append(f"{label}: duplicate tool name")
            seen_names.add(name)
        issues.extend(_validate_input_schema(tool.get("inputSchema"), label))
    return issues


def _validate_input_schema(schema, label):
    issues = []
    if schema is None:
        return [f"{label}: missing 'inputSchema'"]
    if not isinstance(schema, dict):
        return [f"{label}: 'inputSchema' is not an object"]
    if schema.get("type") != "object":
        issues.append(
            f"{label}: inputSchema.type is {schema.get('type')!r}, "
            "expected 'object'")
    properties = schema.get("properties")
    if properties is None:
        properties = {}
    if not isinstance(properties, dict):
        issues.append(f"{label}: inputSchema.properties is not an object")
        properties = {}
    required = schema.get("required", [])
    if not isinstance(required, list) or not all(
            isinstance(r, str) for r in required):
        issues.append(f"{label}: inputSchema.required is not a string array")
        required = []
    for field in required:
        if field not in properties:
            issues.append(
                f"{label}: required field {field!r} is not declared "
                "in properties")
    for prop_name, prop_schema in properties.items():
        if not isinstance(prop_schema, dict):
            issues.append(
                f"{label}: property {prop_name!r} is not a schema object")
            continue
        if not any(key in prop_schema for key in _PROPERTY_KEYS):
            issues.append(
                f"{label}: property {prop_name!r} has no type, $ref, "
                "anyOf/oneOf/allOf or enum")
    return issues
