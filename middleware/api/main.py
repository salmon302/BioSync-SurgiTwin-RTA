# SPDX-License-Identifier: MIT
from fastapi import FastAPI

app = FastAPI(title="SurgiTwin-RTA Middleware")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
