#!/usr/bin/env python3
"""Check an api-surface.md file against the format in references/output-format.md.

Usage: check_api_surface.py <api-surface.md> [--repo <sut-root>]

With --repo, also checks that every file in Code locations exists.
Prints one line per problem and exits 1 if any are found.
"""

import argparse
import os
import re
import sys

FIELDS = [
    "ID", "Tier", "Feature group", "Kind", "How to call", "Requires",
    "Enabled by", "Changes state", "Reads state", "Related",
    "Code locations", "Confidence",
]
TIER_HEADINGS = {
    "Tier 0: Core": 0,
    "Tier 1: Core variants": 1,
    "Tier 2: Features": 2,
    "Tier 3: Specialized": 3,
}
NONE = {"—", "-", ""}
LIFECYCLE_WORDS = ("shutdown", "restart", "reboot", "crash")


def parse_table(lines, start):
    """Parse a markdown table beginning at lines[start]. Returns (rows, next_index)."""
    rows = []
    i = start
    while i < len(lines) and lines[i].lstrip().startswith("|"):
        cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
        if not all(re.fullmatch(r":?-+:?", c) for c in cells):
            rows.append(cells)
        i += 1
    return rows, i


def tables_in(lines):
    tables = []
    i = 0
    while i < len(lines):
        if lines[i].lstrip().startswith("|"):
            rows, i = parse_table(lines, i)
            tables.append(rows)
        else:
            i += 1
    return tables


def ids_in(value):
    return re.findall(r"`([^`]+)`", value)


def split_sections(lines, level):
    """Split lines into (heading, body_lines) at headings of the given level."""
    marker = "#" * level + " "
    sections, current, body = [], None, []
    for line in lines:
        if line.startswith(marker):
            if current is not None:
                sections.append((current, body))
            current, body = line[len(marker):].strip(), []
        elif current is not None:
            body.append(line)
    if current is not None:
        sections.append((current, body))
    return sections


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--repo")
    args = ap.parse_args()

    with open(args.path, encoding="utf-8") as f:
        lines = f.read().splitlines()

    errors = []
    err = errors.append

    if not lines or lines[0].strip() != "---":
        err("missing provenance frontmatter at top of file")

    top = dict(split_sections(lines, 2))
    for name in ["Summary", "Index", "Feature Groups", "Flagged"]:
        if name not in top:
            err(f"missing section: ## {name}")

    # Summary header table
    tier0_confirmed = None
    for rows in tables_in(top.get("Summary", [])):
        kv = {r[0]: r[1] for r in rows if len(r) >= 2}
        tier0_confirmed = kv.get("Tier 0 confirmed by user")
    if tier0_confirmed not in ("yes", "no", "`yes`", "`no`"):
        err("Summary: 'Tier 0 confirmed by user' must be yes or no")

    # Feature groups
    groups = set()
    for rows in tables_in(top.get("Feature Groups", [])):
        for r in rows[1:]:
            groups.update(ids_in(r[0]))

    # Operation sections
    ops = {}
    for heading, body in split_sections(lines, 2):
        if heading not in TIER_HEADINGS:
            continue
        section_tier = TIER_HEADINGS[heading]
        for op_heading, op_body in split_sections(body, 3):
            m = re.match(r"`([^`]+)`", op_heading)
            if not m:
                err(f"operation heading must start with `id`: {op_heading}")
                continue
            op_id = m.group(1)
            where = f"{op_id}:"
            if op_id in ops:
                err(f"{where} duplicate operation ID")
            tables = tables_in(op_body)
            fields_table = next((t for t in tables if t and t[0][:2] == ["Field", "Value"]), None)
            if fields_table is None:
                err(f"{where} missing fields table")
                continue
            names = [r[0] for r in fields_table[1:]]
            if names != FIELDS:
                err(f"{where} fields table rows must be exactly, in order: {', '.join(FIELDS)}")
            fields = {r[0]: (r[1] if len(r) > 1 else "") for r in fields_table[1:]}

            if ids_in(fields.get("ID", "")) != [op_id]:
                err(f"{where} ID field does not match heading")
            try:
                tier = int(fields.get("Tier", "").strip("`"))
                if tier not in (0, 1, 2, 3):
                    raise ValueError
            except ValueError:
                err(f"{where} Tier must be 0, 1, 2, or 3")
                tier = None
            if tier is not None and tier != section_tier:
                err(f"{where} Tier {tier} but listed under '{heading}'")

            group = fields.get("Feature group", "")
            group_ids = ids_in(group)
            if tier == 2 and not group_ids:
                err(f"{where} Tier 2 operations need a feature group")
            for g in group_ids:
                if g not in groups:
                    err(f"{where} feature group `{g}` not in Feature Groups table")

            kind = fields.get("Kind", "").strip("`")
            if kind not in ("data", "admin"):
                err(f"{where} Kind must be data or admin")

            conf = fields.get("Confidence", "").strip("`")
            if conf not in ("high", "low"):
                err(f"{where} Confidence must be high or low")
            body_text = "\n".join(op_body)
            if "**What it does:**" not in body_text:
                err(f"{where} missing 'What it does' bullet")
            if "**Tier reason:**" not in body_text:
                err(f"{where} missing 'Tier reason' bullet")
            if conf == "low" and "**Uncertain:**" not in body_text:
                err(f"{where} low confidence needs an 'Uncertain' bullet")

            locs = ids_in(fields.get("Code locations", ""))
            if not locs:
                err(f"{where} needs at least one code location")
            for loc in locs:
                if ":" not in loc:
                    err(f"{where} code location '{loc}' must be file:function")
                elif args.repo and not os.path.exists(os.path.join(args.repo, loc.split(":")[0])):
                    err(f"{where} code location file not found: {loc.split(':')[0]}")

            if not any(t and t[0][:1] == ["Input"] for t in tables) and "No inputs." not in body_text:
                err(f"{where} missing inputs table (or 'No inputs.')")

            if any(w in op_id.lower() or w in op_heading.lower() for w in LIFECYCLE_WORDS):
                err(f"{where} looks like a lifecycle action; these are left to fault injection")

            ops[op_id] = {
                "tier": tier,
                "group": group_ids[0] if group_ids else None,
                "kind": kind,
                "requires": ids_in(fields.get("Requires", "")),
                "related": ids_in(fields.get("Related", "")),
            }

    if not ops:
        err("no operation sections found under the Tier headings")

    # Cross-references
    for op_id, op in ops.items():
        for dep in op["requires"]:
            if dep not in ops:
                err(f"{op_id}: requires unknown operation `{dep}`")
            elif op["tier"] is not None and ops[dep]["tier"] is not None and ops[dep]["tier"] > op["tier"]:
                err(f"{op_id}: Tier {op['tier']} but requires `{dep}` which is Tier {ops[dep]['tier']}")
        for rel in op["related"]:
            if rel not in ops:
                err(f"{op_id}: related to unknown operation `{rel}`")

    # Index must match sections
    index_ids = set()
    for rows in tables_in(top.get("Index", [])):
        for r in rows[1:]:
            if len(r) < 5:
                err(f"Index: row has too few columns: {r}")
                continue
            ids = ids_in(r[0])
            if not ids:
                continue
            op_id = ids[0]
            index_ids.add(op_id)
            if op_id not in ops:
                err(f"Index: `{op_id}` has no operation section")
                continue
            op = ops[op_id]
            if r[2].strip("`") != str(op["tier"]):
                err(f"Index: `{op_id}` tier differs from its section")
            idx_group = ids_in(r[3])
            if (idx_group[0] if idx_group else None) != op["group"]:
                err(f"Index: `{op_id}` feature group differs from its section")
            if r[4].strip("`") != op["kind"]:
                err(f"Index: `{op_id}` kind differs from its section")
    for op_id in ops:
        if op_id not in index_ids:
            err(f"Index: missing `{op_id}`")

    tier0 = [o for o in ops.values() if o["tier"] == 0]
    if not tier0:
        err("no Tier 0 operations")

    for e in errors:
        print(e)
    if errors:
        print(f"\n{len(errors)} problem(s) found.")
        sys.exit(1)
    if len(tier0) > 8:
        print(f"warning: {len(tier0)} Tier 0 operations; Tier 0 is usually 2-6")
    print(f"OK: {len(ops)} operations ({len(tier0)} in Tier 0).")


if __name__ == "__main__":
    main()
