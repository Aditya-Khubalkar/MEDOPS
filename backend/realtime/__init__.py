from fastapi import APIRouter
router = APIRouter()
# This file can be used to export the router
from .sockets import router
