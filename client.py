from __future__ import annotations

import argparse
import json

import httpx


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Client for the Financial Agent server")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="Base URL for the FastAPI server")
    parser.add_argument("--portfolio-id", default="sector_heavy", help="Portfolio ID or alias to analyze")
    parser.add_argument("--timeout", type=float, default=20.0, help="Request timeout in seconds")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    with httpx.Client(base_url=args.base_url, timeout=args.timeout) as client:
        response = client.post("/analyze", json={"portfolio_id": args.portfolio_id})
        response.raise_for_status()
        print(json.dumps(response.json(), indent=2))


if __name__ == "__main__":
    main()

