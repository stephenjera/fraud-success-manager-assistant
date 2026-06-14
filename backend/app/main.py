from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import execute, explore, rules

app = FastAPI(title="Fraud Success Manager Assistant API Server")

app.add_middleware(
    middleware_class=CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(explore.router, prefix="/api")
app.include_router(execute.router, prefix="/api")
app.include_router(rules.router, prefix="/api/rules")

