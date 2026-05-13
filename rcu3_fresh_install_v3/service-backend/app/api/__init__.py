"""
API Router Configuration
"""
from fastapi import APIRouter
from app.api.urls import routes

api_router = APIRouter()

for route in routes:
    api_router.add_api_route(
        path=route["path"],
        endpoint=route["endpoint"],
        methods=route["methods"]
    )