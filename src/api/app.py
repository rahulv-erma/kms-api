from fastapi.middleware.cors import CORSMiddleware
from fastapi import Request
from fastapi.responses import JSONResponse
import uvicorn
import asyncio

from src import log
from src.api import app, APP_VERSION
from src.api.routers import users, courses, data, forms, admin
from src.api.lib.base_responses import successful_response
from src.modules.training_connect import TrainingConnect

origins = [
    # "http://localhost:port",
    "*",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users.router)
app.include_router(courses.router)
app.include_router(data.router)
app.include_router(forms.router)
app.include_router(admin.router)


async def run_training_connect():
    training_connect_object = TrainingConnect()
    await training_connect_object.start_system()


@app.on_event("startup")
async def startup():
    log.info("Starting the API")
    # Start the TrainingConnect system in the background
    asyncio.create_task(run_training_connect())


@app.on_event("shutdown")
async def shutdown():
    log.info("Shutting down")


@app.get("/version")
async def version_info():
    return successful_response(payload={"version": APP_VERSION})


@app.api_route("/{path_name:path}")
async def catch_all(request: Request, path_name: str) -> JSONResponse:
    """Route to catch all routes that are not specified

    Args:
        request (Request): FastAPI request passed through a function
        path_name (str): Path to invalid api route

    Returns:
        JsonResponse: Returns a json response with 404 error as well as request details
    """
    return JSONResponse(
        content={
            "description": "Details not found",
            "request_method": request.method,
            "path_name": path_name
        },
        status_code=404
    )


@app.post("/health-status")
async def health_status():
    return successful_response()


if __name__ == '__main__':
    uvicorn.run("app:app", host="0.0.0.0", port=8000, log_level="debug")
