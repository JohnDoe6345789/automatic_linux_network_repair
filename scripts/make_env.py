#!/usr/bin/env python3
"""Simple tool to write a .env file.
Usage:
  python make_env.py --out .env KEY=VALUE FOO=BAR
"""

import argparse
from pathlib import Path

def parse_kv(pairs):
    result = []
    for pair in pairs:
        if "=" not in pair:
            raise ValueError(f"Invalid pair: {pair}")
        k, v = pair.split("=", 1)
        result.append((k, v))
    return result

def main():
    parser = argparse.ArgumentParser(description="Create .env file from key=value pairs.")
    parser.add_argument("--github-pat", dest="github_pat", help="GitHub Personal Access Token.")(description="Create .env file from key=value pairs.")
    parser.add_argument("--out", default=".env", help="Output env file path.")
    parser.add_argument("pairs", nargs="+", help="KEY=VALUE entries.")
    args = parser.parse_args()

    kvs = parse_kv(args.pairs)
    if args.github_pat:
        kvs.append(("GITHUB_PERSONAL_ACCESS_TOKEN", args.github_pat))(args.pairs)
    out = Path(args.out)

    lines = [f"{k}={v}" for k, v in kvs]
    out.write_text("".join(lines) + "", encoding="utf-8")
    ensure_gitignore(out)("\n".join(lines) + "\n", encoding="utf-8")

def ensure_gitignore(out_path: Path) -> None:
    gi = Path('.gitignore')
    if not gi.exists():
        return
    content = gi.read_text().splitlines()
    rel = str(out_path)
    if rel not in content:
        content.append(rel)
        gi.write_text("".join(content) + "")


if __name__ == "__main__":
    main()
