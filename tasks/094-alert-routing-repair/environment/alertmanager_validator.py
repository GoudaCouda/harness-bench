#!/usr/bin/python3
"""Pinned, offline validator for the task-094 Alertmanager profile.

This intentionally validates a bounded Alertmanager 0.32-compatible profile:
route inheritance and continuation, UTF-8 matcher syntax, inhibition matchers,
receiver references, local webhook shapes, and duration fields.  It is a
validator, not a repair planner, and contains no incident-specific answer.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml


VERSION = "hb-amconfig-validator 0.32.1-profile.1"
_DURATION_RE = re.compile(r"^(?:0|[0-9]+(?:\.[0-9]+)?(?:ms|s|m|h|d|w|y))$")
_MATCHER_RE = re.compile(
    r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*(=~|!~|!=|=)\s*"
    r'(?:((?:"(?:[^"\\]|\\.)*"))|([^\s]+))\s*$'
)
_ROUTE_KEYS = {
    "receiver",
    "group_by",
    "group_wait",
    "group_interval",
    "repeat_interval",
    "matchers",
    "match",
    "match_re",
    "continue",
    "routes",
}


class ValidationError(ValueError):
    """A deterministic configuration validation failure."""


class _UniqueSafeLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects ambiguous duplicate mapping keys."""


def _unique_mapping(loader: _UniqueSafeLoader, node: yaml.nodes.MappingNode) -> dict:
    result: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=False)
        try:
            duplicate = key in result
        except TypeError as exc:
            raise ValidationError("mapping keys must be scalar") from exc
        if duplicate:
            raise ValidationError(f"duplicate YAML mapping key: {key!r}")
        result[key] = loader.construct_object(value_node, deep=False)
    return result


_UniqueSafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _unique_mapping,
)


def _matcher_value(token: str) -> str:
    if not token.startswith('"'):
        if any(character in token for character in "{}[],"):
            raise ValidationError("UTF-8 strict matcher values with punctuation must be quoted")
        return token
    try:
        value = json.loads(token)
    except json.JSONDecodeError as exc:
        raise ValidationError("matcher contains an invalid quoted UTF-8 value") from exc
    if not isinstance(value, str):
        raise ValidationError("matcher value must be text")
    return value


def parse_matcher(expression: object) -> tuple[str, str, str]:
    if not isinstance(expression, str):
        raise ValidationError("matcher entries must be strings")
    match = _MATCHER_RE.fullmatch(expression)
    if match is None:
        raise ValidationError(f"invalid UTF-8 matcher syntax: {expression!r}")
    token = match.group(3) if match.group(3) is not None else match.group(4)
    value = _matcher_value(token)
    operator = match.group(2)
    if operator in {"=~", "!~"}:
        # Go regexp/RE2 deliberately excludes look-around and backreferences.
        if "(?" in value or re.search(r"\\[1-9]", value):
            raise ValidationError("matcher regex is not supported by RE2")
        try:
            re.compile(value)
        except re.error as exc:
            raise ValidationError("matcher regex is invalid") from exc
    return match.group(1), operator, value


def _legacy_matchers(node: dict[str, Any], key: str, operator: str) -> list[tuple[str, str, str]]:
    value = node.get(key, {})
    if not isinstance(value, dict):
        raise ValidationError(f"{key} must be a mapping")
    result: list[tuple[str, str, str]] = []
    for name, expected in value.items():
        if not isinstance(name, str) or not isinstance(expected, str):
            raise ValidationError(f"{key} names and values must be strings")
        if operator == "=~":
            if "(?" in expected or re.search(r"\\[1-9]", expected):
                raise ValidationError("matcher regex is not supported by RE2")
            try:
                re.compile(expected)
            except re.error as exc:
                raise ValidationError("matcher regex is invalid") from exc
        result.append((name, operator, expected))
    return result


def node_matchers(node: dict[str, Any]) -> list[tuple[str, str, str]]:
    expressions = node.get("matchers", [])
    if not isinstance(expressions, list):
        raise ValidationError("matchers must be a list")
    result = [parse_matcher(expression) for expression in expressions]
    result.extend(_legacy_matchers(node, "match", "="))
    result.extend(_legacy_matchers(node, "match_re", "=~"))
    return result


def _duration(value: object, field: str) -> None:
    if not isinstance(value, str) or _DURATION_RE.fullmatch(value) is None:
        raise ValidationError(f"{field} must be a Prometheus duration")


def _route(node: object, receivers: set[str], *, root: bool) -> None:
    if not isinstance(node, dict):
        raise ValidationError("route entries must be mappings")
    unknown = set(node) - _ROUTE_KEYS
    if unknown:
        raise ValidationError(f"unsupported route fields: {sorted(unknown)}")
    receiver = node.get("receiver")
    if receiver is not None and (not isinstance(receiver, str) or receiver not in receivers):
        raise ValidationError("route references an unknown receiver")
    if root and not receiver:
        raise ValidationError("root route must name a receiver")
    if root and any(key in node for key in ("matchers", "match", "match_re")):
        raise ValidationError("root route must not contain matchers")
    node_matchers(node)
    if "continue" in node and not isinstance(node["continue"], bool):
        raise ValidationError("continue must be boolean")
    if "group_by" in node:
        group_by = node["group_by"]
        if not isinstance(group_by, list) or not all(isinstance(item, str) for item in group_by):
            raise ValidationError("group_by must be a string list")
    for key in ("group_wait", "group_interval", "repeat_interval"):
        if key in node:
            _duration(node[key], key)
    children = node.get("routes", [])
    if not isinstance(children, list):
        raise ValidationError("routes must be a list")
    for child in children:
        _route(child, receivers, root=False)


def load_and_validate(path: Path) -> dict[str, Any]:
    try:
        if not path.is_file() or path.is_symlink() or path.stat().st_size > 200_000:
            raise ValidationError("configuration is absent, linked, or oversized")
        config = yaml.load(path.read_text(encoding="utf-8"), Loader=_UniqueSafeLoader)
    except (OSError, UnicodeError, yaml.YAMLError, RecursionError) as exc:
        raise ValidationError(f"configuration cannot be parsed: {type(exc).__name__}") from exc
    if not isinstance(config, dict):
        raise ValidationError("configuration root must be a mapping")
    unknown = set(config) - {"global", "route", "receivers", "inhibit_rules"}
    if unknown:
        raise ValidationError(f"unsupported top-level fields: {sorted(unknown)}")
    global_config = config.get("global", {})
    if not isinstance(global_config, dict) or set(global_config) - {"resolve_timeout"}:
        raise ValidationError("global contains unsupported fields")
    if "resolve_timeout" in global_config:
        _duration(global_config["resolve_timeout"], "resolve_timeout")
    receiver_rows = config.get("receivers")
    if not isinstance(receiver_rows, list) or not receiver_rows:
        raise ValidationError("receivers must be a non-empty list")
    receiver_names: list[str] = []
    for receiver in receiver_rows:
        if not isinstance(receiver, dict) or set(receiver) - {"name", "webhook_configs"}:
            raise ValidationError("receiver contains unsupported integration fields")
        name = receiver.get("name")
        webhooks = receiver.get("webhook_configs")
        if not isinstance(name, str) or not name or not isinstance(webhooks, list) or not webhooks:
            raise ValidationError("receiver name and webhook_configs are required")
        for webhook in webhooks:
            if not isinstance(webhook, dict) or set(webhook) - {"url", "send_resolved"}:
                raise ValidationError("webhook configuration is malformed")
            if not isinstance(webhook.get("url"), str):
                raise ValidationError("webhook URL must be text")
            if "send_resolved" in webhook and not isinstance(webhook["send_resolved"], bool):
                raise ValidationError("send_resolved must be boolean")
        receiver_names.append(name)
    if len(receiver_names) != len(set(receiver_names)):
        raise ValidationError("receiver names must be unique")
    _route(config.get("route"), set(receiver_names), root=True)
    rules = config.get("inhibit_rules", [])
    if not isinstance(rules, list):
        raise ValidationError("inhibit_rules must be a list")
    allowed_rule = {"source_matchers", "target_matchers", "source_match", "source_match_re", "target_match", "target_match_re", "equal"}
    for rule in rules:
        if not isinstance(rule, dict) or set(rule) - allowed_rule:
            raise ValidationError("inhibition rule is malformed")
        for prefix in ("source", "target"):
            node_matchers(
                {
                    "matchers": rule.get(f"{prefix}_matchers", []),
                    "match": rule.get(f"{prefix}_match", {}),
                    "match_re": rule.get(f"{prefix}_match_re", {}),
                }
            )
        equal = rule.get("equal", [])
        if not isinstance(equal, list) or not all(isinstance(item, str) for item in equal):
            raise ValidationError("inhibition equal must be a string list")
    return config


def _matches(matchers: list[tuple[str, str, str]], labels: dict[str, str]) -> bool:
    for name, operator, expected in matchers:
        actual = labels.get(name, "")
        if operator == "=" and actual != expected:
            return False
        if operator == "!=" and actual == expected:
            return False
        if operator == "=~" and re.fullmatch(expected, actual) is None:
            return False
        if operator == "!~" and re.fullmatch(expected, actual) is not None:
            return False
    return True


def route_receivers(config: dict[str, Any], labels: dict[str, str]) -> list[str]:
    def descend(node: dict[str, Any], inherited: str | None) -> list[str]:
        receiver = node.get("receiver", inherited)
        selected: list[str] = []
        for child in node.get("routes", []):
            if not _matches(node_matchers(child), labels):
                continue
            selected.extend(descend(child, receiver))
            if not child.get("continue", False):
                break
        return selected or ([receiver] if isinstance(receiver, str) else [])

    return descend(config["route"], None)


def check_routes(path: Path, labels: dict[str, str], expected: list[str]) -> None:
    config = load_and_validate(path)
    actual = route_receivers(config, labels)
    if actual != expected:
        raise ValidationError(f"receiver mismatch: expected={expected}; actual={actual}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hb-amconfig")
    parser.add_argument("--version", action="store_true")
    subcommands = parser.add_subparsers(dest="command")
    check = subcommands.add_parser("check-config")
    check.add_argument("config", type=Path)
    check.add_argument("--utf8-strict", action="store_true")
    routes = subcommands.add_parser("routes-test")
    routes.add_argument("config", type=Path)
    routes.add_argument("--expect", required=True)
    routes.add_argument("labels", nargs="*")
    args = parser.parse_args(argv)
    try:
        if args.version:
            print(VERSION)
            return 0
        if args.command == "check-config":
            if not args.utf8_strict:
                raise ValidationError("--utf8-strict is required")
            load_and_validate(args.config)
            print(f"SUCCESS: {args.config} is valid ({VERSION})")
            return 0
        if args.command == "routes-test":
            labels: dict[str, str] = {}
            for item in args.labels:
                if "=" not in item:
                    raise ValidationError(f"invalid label assignment: {item!r}")
                key, value = item.split("=", 1)
                if not key or key in labels:
                    raise ValidationError(f"invalid label assignment: {item!r}")
                labels[key] = value
            expected = [item for item in args.expect.split(",") if item]
            check_routes(args.config, labels, expected)
            print(f"SUCCESS: receivers={expected}")
            return 0
        parser.error("a command or --version is required")
    except ValidationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
