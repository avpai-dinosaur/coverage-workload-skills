#!/usr/bin/env python3
"""Turn coverage from Antithesis or local runs into one simple format, and compare.

Commands:
  normalize  Convert raw coverage into a snapshot JSON file.
  merge      Combine several snapshots (e.g. local runs with different seeds).
  summary    Totals and the files with the most reached lines.
  diff       What one snapshot reached that another did not, both ways.
  by-op      Coverage for each operation in api-surface.md, via its code locations.

Input formats for `normalize`:
  antithesis  `snouty --json runs show <run-id>` output (or just its .results.coverage)
  lcov        LCOV tracefile (llvm-cov export -format=lcov, coverage.py `coverage lcov`, c8, ...)
  gocover     Go text profile (`go tool covdata textfmt -i=<dir> -o=<file>`)
  jacoco      JaCoCo XML report

Snapshot format:
  {"source": "...", "label": "...",
   "files": {"<repo-relative path>": {"lines": [reached line numbers],
                                      "functions": {"<name>": <edges or hits>},
                                      "missed_functions": [names never reached]}}}

Antithesis coverage only lists code that was reached, so its snapshots have no
missed_functions. Local formats list everything that was instrumented.
"""

import argparse
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict

# Toolchain, dependency, and test code. Dropped before matching paths to the repo.
DEFAULT_EXCLUDES = [
    r"^/rustc/", r"/\.?cargo/", r"/rust/deps/", r"^/usr/(lib|lib64|include|share)/",
    r"^/usr/local/(lib|include)/", r"^/build/target/",
    r"site-packages/", r"dist-packages/", r"node_modules/", r"(^|/)vendor/",
    r"_test\.go$", r"(^|/)tests?/", r"^<",
]


# ---------- reading raw formats ----------

def read_antithesis(path, keep_function=None):
    with open(path) as f:
        data = json.load(f)
    cov = data.get("results", {}).get("coverage", data) if isinstance(data, dict) else data
    if "files" not in cov:
        sys.exit("no coverage found (expected .results.coverage.files)")
    files = {}
    for fname, entry in cov["files"].items():
        rec = new_file()
        named = [(fn, spans) for fn, spans in entry.get("functions", {}).items()]
        for cls, methods in entry.get("classes", {}).items():
            named += [(f"{cls}.{m}", spans) for m, spans in methods.items()]
        for name, spans in named:
            if keep_function and not re.search(keep_function, name):
                continue
            base = re.sub(r" \([^)]*\)$", "", name)  # "parse_args (branch jump)" -> "parse_args"
            for s in spans:
                span = s["span"]
                lo, hi = (span[0], span[2]) if len(span) == 4 else (span[0], span[0])
                rec["lines"].update(range(lo, hi + 1))
                rec["functions"][base] = rec["functions"].get(base, 0) + s.get("edges", 1)
        if rec["functions"]:
            files[fname] = rec
    return files


def read_lcov(path, keep_function=None):
    files, rec, fn_names = {}, None, {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("SF:"):
                rec, fn_names = new_file(), {}
                files[line[3:]] = rec
            elif rec is None:
                continue
            elif line.startswith("DA:"):
                num, hits = line[3:].split(",")[:2]
                if int(float(hits)) > 0:
                    rec["lines"].add(int(num))
            elif line.startswith("FNDA:"):
                hits, name = line[5:].split(",", 1)
                if keep_function and not re.search(keep_function, name):
                    continue
                if int(float(hits)) > 0:
                    rec["functions"][name] = int(float(hits))
                else:
                    rec["missed"].add(name)
            elif line == "end_of_record":
                rec["missed"] -= set(rec["functions"])
                rec = None
    return files


def read_gocover(path, keep_function=None):
    files = defaultdict(new_file)
    with open(path) as f:
        for line in f:
            m = re.match(r"(.+):(\d+)\.\d+,(\d+)\.\d+ \d+ (\d+)$", line.strip())
            if m and int(m.group(4)) > 0:
                files[m.group(1)]["lines"].update(range(int(m.group(2)), int(m.group(3)) + 1))
            elif m:
                files[m.group(1)]  # instrumented but not reached
    return dict(files)


def read_jacoco(path, keep_function=None):
    files = {}
    root = ET.parse(path).getroot()
    for pkg in root.iter("package"):
        pdir = pkg.get("name", "")
        for sf in pkg.iter("sourcefile"):
            rec = new_file()
            for ln in sf.iter("line"):
                if int(ln.get("ci", 0)) > 0:
                    rec["lines"].add(int(ln.get("nr")))
            files[f"{pdir}/{sf.get('name')}"] = rec
        for cls in pkg.iter("class"):
            src = f"{pdir}/{cls.get('sourcefilename')}"
            rec = files.setdefault(src, new_file())
            cname = cls.get("name", "").split("/")[-1]
            for meth in cls.iter("method"):
                name = f"{cname}.{meth.get('name')}"
                covered = any(int(c.get("covered", 0)) > 0
                              for c in meth.iter("counter") if c.get("type") == "METHOD")
                if covered:
                    rec["functions"][name] = 1
                else:
                    rec["missed"].add(name)
    return files


READERS = {"antithesis": read_antithesis, "lcov": read_lcov,
           "gocover": read_gocover, "jacoco": read_jacoco}


def new_file():
    return {"lines": set(), "functions": {}, "missed": set()}


# ---------- path cleanup ----------

def repo_index(repo):
    paths = set()
    for d, dirs, fs in os.walk(repo):
        dirs[:] = [x for x in dirs if not x.startswith(".") and x not in ("node_modules", "target")]
        for f in fs:
            paths.add(os.path.relpath(os.path.join(d, f), repo))
    return paths


def to_repo_path(path, index):
    """Find the repo file this coverage path refers to, by longest matching suffix."""
    parts = path.strip("/").split("/")
    for i in range(len(parts)):
        cand = "/".join(parts[i:])
        # A one-part suffix of a longer path (e.g. "mod.rs") is too ambiguous.
        if cand in index and (i == 0 or len(parts) - i >= 2):
            return cand
    return None


def clean_paths(files, repo, strip, excludes):
    index = repo_index(repo)
    out = {}
    for path, rec in files.items():
        for p in strip:
            if path.startswith(p):
                path = path[len(p):].lstrip("/")
        if any(re.search(rx, path) for rx in excludes):
            continue
        path = to_repo_path(path, index)
        if path is None:
            continue
        dst = out.setdefault(path, new_file())
        dst["lines"] |= rec["lines"]
        dst["missed"] |= rec["missed"]
        for k, v in rec["functions"].items():
            dst["functions"][k] = dst["functions"].get(k, 0) + v
    return out


# ---------- snapshots ----------

def to_json(files, source, label):
    return {"source": source, "label": label, "files": {
        p: {"lines": sorted(r["lines"]), "functions": r["functions"],
            "missed_functions": sorted(r["missed"] - set(r["functions"]))}
        for p, r in sorted(files.items())}}


def load(path):
    with open(path) as f:
        snap = json.load(f)
    for r in snap["files"].values():
        r["lines"] = set(r["lines"])
        r["missed_functions"] = set(r.get("missed_functions", []))
    return snap


def write(snap, out):
    text = json.dumps(snap, indent=1, default=sorted)
    if out:
        with open(out, "w") as f:
            f.write(text)
    else:
        print(text)


# ---------- function name matching ----------

def plain_name(name):
    """Reduce a function name to dotted form, keeping the type it belongs to.

    Rust:  <mycrate::store::Store as Trait>::put::<T>  -> mycrate.store.Store.put
    Go:    example.com/kv/store.(*Store).Put            -> example.com/kv/store.Store.Put
    """
    prev = None
    while prev != name:  # drop generic arguments, innermost first
        prev, name = name, re.sub(r"::<[^<>]*>|(?<=\w)<[^<>]*>", "", name)
    name = re.sub(r"<([^<>]*?)(?: as [^<>]*)?>", r"\1", name)  # <X as Trait> / <X> -> X
    name = name.replace("(*", "").replace(")", "").replace("(", "")
    return name.replace("::", ".").strip(". ").lower()


def name_matches(func, wanted):
    f, w = plain_name(func), plain_name(wanted)
    return f == w or f.endswith("." + w)


# ---------- commands ----------

def cmd_normalize(a):
    files = READERS[a.format](a.input, a.keep_function)
    files = clean_paths(files, a.repo, a.strip_prefix, DEFAULT_EXCLUDES + a.exclude)
    write(to_json(files, a.format, a.label or os.path.basename(a.input)), a.output)


def cmd_merge(a):
    merged = {}
    snaps = [load(p) for p in a.inputs]
    for s in snaps:
        for p, r in s["files"].items():
            d = merged.setdefault(p, new_file())
            d["lines"] |= r["lines"]
            d["missed"] |= r["missed_functions"]
            for k, v in r["functions"].items():
                d["functions"][k] = d["functions"].get(k, 0) + v
    sources = sorted({s["source"] for s in snaps})
    write(to_json(merged, "+".join(sources), a.label or "merged"), a.output)


def totals(snap):
    files = snap["files"]
    return (len(files), sum(len(r["functions"]) for r in files.values()),
            sum(len(r["lines"]) for r in files.values()))


def cmd_summary(a):
    snap = load(a.snapshot)
    nf, nfn, nl = totals(snap)
    print(f"{snap['label']} ({snap['source']}): {nf} files, {nfn} functions, {nl} lines reached")
    if snap["source"] == "antithesis":
        edges = sum(sum(r["functions"].values()) for r in snap["files"].values())
        print(f"{edges} edges reached (distinct instrumented points in SUT code)")
    print(f"\nTop {a.top} files by lines reached:")
    for p, r in sorted(snap["files"].items(), key=lambda x: -len(x[1]["lines"]))[:a.top]:
        missed = f", {len(r['missed_functions'])} functions never reached" if r["missed_functions"] else ""
        print(f"  {len(r['lines']):6}  {p}{missed}")


def one_way(a, b):
    """Lines and functions in snapshot a that b does not have, per file."""
    rows = []
    for p, r in a["files"].items():
        other = b["files"].get(p, {"lines": set(), "functions": {}})
        lines = r["lines"] - other["lines"]
        funcs = sorted(set(r["functions"]) - set(other["functions"]))
        if lines or funcs:
            rows.append((p, len(lines), funcs, p not in b["files"]))
    return sorted(rows, key=lambda x: -x[1])


def cmd_diff(a):
    old, new = load(a.old), load(a.new)
    for title, x, y in [(f"Reached in {new['label']} but not {old['label']}", new, old),
                        (f"Reached in {old['label']} but not {new['label']}", old, new)]:
        rows = one_way(x, y)
        nl = sum(r[1] for r in rows)
        nfn = sum(len(r[2]) for r in rows)
        print(f"\n## {title}: {nl} lines, {nfn} functions, {len(rows)} files")
        for p, lines, funcs, is_new in rows[:a.top]:
            tag = " (new file)" if is_new else ""
            print(f"  {lines:6} lines  {p}{tag}")
            for fn in funcs[:a.functions]:
                print(f"           + {fn}")
            if len(funcs) > a.functions:
                print(f"           + ... {len(funcs) - a.functions} more")


def parse_api_surface(path):
    ops, cur = [], None
    with open(path) as f:
        for line in f:
            m = re.match(r"### `([^`]+)`", line)
            if m:
                cur = {"id": m.group(1), "tier": "?", "locs": []}
                ops.append(cur)
            elif cur and line.startswith("| Tier |"):
                cur["tier"] = line.split("|")[2].strip().strip("`")
            elif cur and line.startswith("| Code locations |"):
                cur["locs"] = re.findall(r"`([^`]+)`", line.split("|", 2)[2])
    return ops


def cmd_by_op(a):
    snap = load(a.snapshot)
    files = snap["files"]
    print(f"Coverage by operation ({snap['label']}, {snap['source']})\n")
    print("| Operation | Tier | Functions reached | Lines reached in its files | Never reached |")
    print("|---|---|---|---|---|")
    for op in parse_api_surface(a.api_surface):
        reached, total, op_files, missed = 0, 0, set(), []
        for loc in op["locs"]:
            path, _, func = loc.partition(":")
            path = path.rstrip("/")
            matched = [p for p in files if p == path or p.endswith("/" + path)
                       or p.startswith(path + "/")]
            op_files.update(matched)
            if not func:
                continue
            total += 1
            hit = any(name_matches(fn, func) for p in matched for fn in files[p]["functions"])
            if hit:
                reached += 1
            elif any(name_matches(fn, func) for p in matched for fn in files[p]["missed_functions"]):
                missed.append(func)
            else:
                missed.append(f"{func}?")
        lines = sum(len(files[p]["lines"]) for p in op_files)
        never = ", ".join(missed) if missed else "—"
        print(f"| `{op['id']}` | {op['tier']} | {reached}/{total} | {lines} | {never} |")
    print("\n`name?` = not found in this coverage at all. Either never reached, or the"
          " code location in api-surface.md does not match the name in the coverage data.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("normalize")
    p.add_argument("--format", required=True, choices=READERS)
    p.add_argument("input")
    p.add_argument("-o", "--output")
    p.add_argument("--label")
    p.add_argument("--repo", required=True,
                   help="SUT repo root; keeps only files in it and makes paths repo-relative")
    p.add_argument("--keep-function", metavar="REGEX",
                   help="keep only functions whose full name matches, e.g. '^<?mycrate::' for Rust. "
                        "Use when dependencies have files with the same relative paths as the SUT")
    p.add_argument("--strip-prefix", action="append", default=[], help="prefix to remove from paths")
    p.add_argument("--exclude", action="append", default=[], help="extra path regex to drop")
    p.set_defaults(fn=cmd_normalize)

    p = sub.add_parser("merge")
    p.add_argument("inputs", nargs="+")
    p.add_argument("-o", "--output")
    p.add_argument("--label")
    p.set_defaults(fn=cmd_merge)

    p = sub.add_parser("summary")
    p.add_argument("snapshot")
    p.add_argument("--top", type=int, default=15)
    p.set_defaults(fn=cmd_summary)

    p = sub.add_parser("diff")
    p.add_argument("old")
    p.add_argument("new")
    p.add_argument("--top", type=int, default=15)
    p.add_argument("--functions", type=int, default=5, help="functions to list per file")
    p.set_defaults(fn=cmd_diff)

    p = sub.add_parser("by-op")
    p.add_argument("snapshot")
    p.add_argument("api_surface")
    p.set_defaults(fn=cmd_by_op)

    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
