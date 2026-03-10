from __future__ import annotations

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from pr_review_agent.app_context import AppContext
from pr_review_agent.webhook_handler import WebhookHandler

app = FastAPI(title="GitHub PR Review Agent", version="2.0.0")
context = AppContext()
handler = WebhookHandler(context)


@app.on_event("startup")
async def on_startup() -> None:
    context.settings.validate_runtime()
    context.logger.info("Starting Python PR review agent")
    context.logger.info("Environment: %s", context.settings.environment)
    context.logger.info("LLM provider: %s", context.settings.llm_provider)
    context.logger.info("Review model: %s", context.settings.review_model)


@app.on_event("shutdown")
async def on_shutdown() -> None:
    await context.close()


@app.get("/")
async def root() -> JSONResponse:
    return handler.root_response()


@app.get("/health")
async def health() -> JSONResponse:
    return handler.health_response()


@app.post("/webhook")
async def webhook(request: Request) -> JSONResponse:
    return await handler.handle_webhook(request)


def run() -> None:
    uvicorn.run("pr_review_agent.main:app", host="0.0.0.0", port=context.settings.port)


if __name__ == "__main__":
    run()
