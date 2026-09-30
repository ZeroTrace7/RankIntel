"""
Benchmark score snapshot tool.
Re-captures fixture JSON for a given site after an approved scoring change.

Usage:
    python benchmarks/score_snapshot_tool.py --site python.org --confirm

Requires --confirm to prevent accidental fixture overwrites.
After running, commit benchmarks/fixtures/<site>-<date>.json to lock the new baseline.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path


def capture_site(url: str, fixtures_dir: Path) -> int:
    print(f"Capturing benchmark for: {url}")
    print(f"Output directory: {fixtures_dir}")

    result = subprocess.run(
        [sys.executable, "-m", "rankintel.cli", "audit", url, "--format", "json", "--output-dir", str(fixtures_dir)],
        capture_output=False,
    )
    if result.returncode != 0:
        print(f"\nWARNING: rankintel exited with code {result.returncode} for {url}")
    return result.returncode


def main():
    parser = argparse.ArgumentParser(
        description="Re-capture benchmark fixture(s) for sites defined in benchmarks/sites.json.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python benchmarks/score_snapshot_tool.py --all --confirm
  python benchmarks/score_snapshot_tool.py --site alephindia.in --confirm
  python benchmarks/score_snapshot_tool.py --site sunrisetesting.vercel.app --confirm

After running, commit the updated fixture:
  git add benchmarks/fixtures/
  git commit -m "chore: update benchmark fixture for <site> after <change>"
        """
    )
    parser.add_argument("--site", required=False,
                        help="Domain or URL to audit (e.g. alephindia.in)")
    parser.add_argument("--all", action="store_true",
                        help="Re-capture all 11 sites from benchmarks/sites.json")
    parser.add_argument("--confirm", action="store_true",
                        help="Required: acknowledge you are overwriting the regression baseline")
    args = parser.parse_args()

    if not args.confirm:
        print("ERROR: Pass --confirm to overwrite fixtures.")
        print("       This changes the regression baseline — do it only after an approved change.")
        sys.exit(1)

    if not args.all and not args.site:
        print("ERROR: Pass either --site <domain> or --all.")
        sys.exit(1)

    base_dir = Path(__file__).parent
    fixtures_dir = base_dir / "fixtures"
    fixtures_dir.mkdir(exist_ok=True)
    sites_file = base_dir / "sites.json"

    urls = []
    if args.all:
        config = json.loads(sites_file.read_text(encoding="utf-8"))
        urls = [s["url"] for s in config["sites"]]
    else:
        url = args.site
        if sites_file.exists():
            config = json.loads(sites_file.read_text(encoding="utf-8"))
            for s in config["sites"]:
                if s["domain"] == args.site or s["url"] == args.site:
                    url = s["url"]
                    break
        if not url.startswith("http"):
            url = f"https://{url}"
        urls = [url]

    failed = 0
    for u in urls:
        rc = capture_site(u, fixtures_dir)
        if rc != 0:
            failed += 1

    if failed:
        print(f"\nWARNING: {failed}/{len(urls)} captures exited with non-zero code.")
        sys.exit(1)

    print("\nDone. Commit benchmarks/fixtures/ to lock new baseline.")


if __name__ == "__main__":
    main()
