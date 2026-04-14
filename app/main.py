from fastapi import FastAPI
from app.routers import user as user_router

app = FastAPI(
    title="User Management Service",
    description="Production-ready FastAPI microservice for user management",
    version="1.0.0",
)

app.include_router(user_router.router, prefix="/users", tags=["Users"])


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok"}
