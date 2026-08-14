"""End-to-end sample queries for the assistant (RAG + function calling)."""

from __future__ import annotations

import httpx

BASE = "http://localhost:8000"


def ask(message: str) -> None:
    data = httpx.post(f"{BASE}/chat", json={"message": message}, timeout=120).raise_for_status().json()
    print(f"\nQ: {message}\nintent={data['intent']} tools={data['tools_used']}\nA: {data['answer']}")


def main() -> None:
    for q in (
        "How much does a Velo'v subscription cost?",
        "How do I report a broken station?",
        "Is there a bike available near Part-Dieu station right now?",
        "Find the nearest bikes to 45.764, 4.836",
    ):
        ask(q)


if __name__ == "__main__":
    main()
