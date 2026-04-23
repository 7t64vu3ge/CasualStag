from __future__ import annotations

import uvicorn

from financial_agent.config import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "financial_agent.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
    )


if __name__ == "__main__":
    main()

