"""
Benchmark score snapshot tool.
Re-captures fixture JSON for a given site after an approved scoring change.

Usage:
    python benchmarks/score_snapshot_tool.py --site python.org --confirm

Requires --confirm to prevent accidental fixture overwrites.
After running, commit benchmarks/fixtures/<site>-<date>.json to lock the new baseline.
"""
import argparse
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="Re-capture benchmark fixture for a site.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python benchmarks/score_snapshot_tool.py --site python.org --confirm
  python benchmarks/score_snapshot_tool.py --site sunrisetesting.vercel.app --confirm

After running, commit the updated fixture:
  git add benchmarks/fixtures/
  git commit -m "chore: update benchmark fixture for <site> after <change>"
        """
    )
    parser.add_argument("--site", required=True,
                        help="Domain to audit (e.g. python.org)")
    parser.add_argument("--confirm", action="store_true",
                        help="Required: acknowledge you are overwriting the regression baseline")
    args = parser.parse_args()

    if not args.confirm:
        print("ERROR: Pass --confirm to overwrite fixtures.")
        print("       This changes the regression baseline — do it only after an approved change.")
        sys.exit(1)

    fixtures_dir = Path(__file__).parent / "fixtures"
    fixtures_dir.mkdir(exist_ok=True)

    url = f"https://{args.site}" if not args.site.startswith("http") else args.site
    print(f"Capturing benchmark for: {url}")
    print(f"Output directory: {fixtures_dir}")

    result = subprocess.run(
        ["rankintel", "audit", url, "--format", "json", "--output-dir", str(fixtures_dir)],
        capture_output=False,
    )

    if result.returncode != 0:
        print(f"\nWARNING: rankintel exited with code {result.returncode}")
        print("Check the output above for errors.")
        sys.exit(result.returncode)

    print(f"\nDone. Commit benchmarks/fixtures/ to lock new baseline.")


if __name__ == "__main__":
    main()
