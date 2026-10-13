# SPDX-License-Identifier: MIT
from fastapi import Depends, FastAPI

from api.auth import User, get_current_user
from api.loop_policy import configure_uvloop
from api.routes import audit, auth, fhir

# R3 event-loop policy (Gateway open item, see docs/migration-map.md). Skipped under pytest.
configure_uvloop()

app = FastAPI(title="SurgiTwin-RTA Middleware")

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(audit.router, prefix="/api/audit", tags=["audit"])
app.include_router(fhir.router, prefix="/api/fhir", tags=["fhir"])


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/protected")
async def protected_endpoint(current_user: User = Depends(get_current_user)):
    """Example endpoint requiring a valid JWT (SRS NFR-SEC-001)."""
    return {
        "message": "Access granted",
        "user": current_user.username,
        "role": current_user.role,
        "scope": current_user.scopes,
        "scopes": current_user.scopes,
    }
