"""A tiny JSON-schema-like validator, so a bad spec is refused with a sentence instead of a KeyError.

No external jsonschema dependency: the schemas in this package use a handful of keywords, all
implemented here. Supported: type (string, number, integer, boolean, array, object, null, build,
and a list of those for a union), enum, required, properties, additionalProperties (bool or a
schema), items, minItems, maxItems, minimum, maximum, minLength, anyOf.

`build` is this package's own type: a time window `{"at": s, "dur": s}` or `[at, dur]`, local
seconds from 0.
"""
from __future__ import annotations


def _is_number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _is_build(v):
    if isinstance(v, dict):
        return (set(v) <= {"at", "dur"} and "at" in v and "dur" in v
                and _is_number(v["at"]) and _is_number(v["dur"]) and v["at"] >= 0 and v["dur"] >= 0)
    if isinstance(v, (list, tuple)):
        return len(v) == 2 and all(_is_number(x) for x in v) and v[0] >= 0 and v[1] >= 0
    return False


_CHECKS = {
    "string": lambda v: isinstance(v, str),
    "number": _is_number,
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "array": lambda v: isinstance(v, (list, tuple)),
    "object": lambda v: isinstance(v, dict),
    "null": lambda v: v is None,
    "build": _is_build,
}


def validate(spec, schema, path="spec"):
    """Raise ValueError naming the path and the problem; return the spec when it is fine."""
    if "anyOf" in schema:
        errors = []
        for option in schema["anyOf"]:
            try:
                validate(spec, option, path)
                break
            except ValueError as err:
                errors.append(str(err))
        else:
            raise ValueError(f"{path}: matches none of the allowed shapes ({'; '.join(errors)})")
    kinds = schema.get("type")
    if kinds is not None:
        kinds = kinds if isinstance(kinds, (list, tuple)) else [kinds]
        for k in kinds:
            if k not in _CHECKS:
                raise ValueError(f"{path}: schema names unknown type {k!r}")
        if not any(_CHECKS[k](spec) for k in kinds):
            hint = " (a build is a dict with at and dur, or a pair [at, dur])" if "build" in kinds else ""
            raise ValueError(f"{path}: expected {'/'.join(kinds)}, got {type(spec).__name__}{hint}")
    if "enum" in schema and spec not in schema["enum"]:
        raise ValueError(f"{path}: {spec!r} is not one of {list(schema['enum'])}")
    if _is_number(spec):
        if "minimum" in schema and spec < schema["minimum"]:
            raise ValueError(f"{path}: {spec} is below the minimum {schema['minimum']}")
        if "maximum" in schema and spec > schema["maximum"]:
            raise ValueError(f"{path}: {spec} is above the maximum {schema['maximum']}")
    if isinstance(spec, str) and "minLength" in schema and len(spec) < schema["minLength"]:
        raise ValueError(f"{path}: text is shorter than {schema['minLength']}")
    if isinstance(spec, dict) and (kinds is None or "object" in kinds):
        for key in schema.get("required", []):
            if key not in spec:
                raise ValueError(f"{path}: missing required field {key!r}")
        props = schema.get("properties", {})
        extra = schema.get("additionalProperties", True)
        for key, value in spec.items():
            if key in props:
                validate(value, props[key], f"{path}.{key}")
            elif extra is False:
                raise ValueError(f"{path}: unknown field {key!r} (allowed: {sorted(props)})")
            elif isinstance(extra, dict):
                validate(value, extra, f"{path}.{key}")
    if isinstance(spec, (list, tuple)) and (kinds is None or "array" in kinds):
        if "minItems" in schema and len(spec) < schema["minItems"]:
            raise ValueError(f"{path}: needs at least {schema['minItems']} items, has {len(spec)}")
        if "maxItems" in schema and len(spec) > schema["maxItems"]:
            raise ValueError(f"{path}: allows at most {schema['maxItems']} items, has {len(spec)}")
        if "items" in schema:
            for i, item in enumerate(spec):
                validate(item, schema["items"], f"{path}[{i}]")
    return spec


def build_window(b, default=(0.0, 0.0)):
    """(at, dur) floats from a build, or the default when it is absent."""
    if b is None:
        return float(default[0]), float(default[1])
    if isinstance(b, dict):
        return float(b["at"]), float(b["dur"])
    return float(b[0]), float(b[1])


# Shared schema fragments ------------------------------------------------------------------------
NUM = {"type": "number"}
BUILD = {"type": "build"}
STR = {"type": "string"}
BOOL = {"type": "boolean"}
POINT = {"type": "array", "minItems": 2, "maxItems": 2, "items": NUM}
RECT = {"type": "array", "minItems": 4, "maxItems": 4, "items": NUM}
TYPE_OVERRIDE = {"type": "object", "additionalProperties": False,
                 "properties": {"display": NUM, "number": NUM, "label": NUM, "caption": NUM}}


def obj(properties, required=()):
    """An object schema that refuses unknown fields and always allows the `type` size override."""
    props = {"type": TYPE_OVERRIDE}
    props.update(properties)
    return {"type": "object", "additionalProperties": False, "required": list(required),
            "properties": props}
