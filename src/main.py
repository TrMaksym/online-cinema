import traceback

from fastapi import FastAPI, Request
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.params import Depends
from starlette.responses import JSONResponse

from src.config.dependencies import get_current_user
from src.router.movies import router as router_movies
from src.router.accounts import router as accounts_router
from src.router.orders import router as orders_router
from src.router.payments import router as payments_router
from src.router.shopping_cart import router as shopping_cart_router

app = FastAPI()

api_version_prefix = "/api/v1"

app.include_router(
    router_movies, prefix=f"{api_version_prefix}/movies", tags=["movies"]
)
app.include_router(
    accounts_router, prefix=f"{api_version_prefix}/accounts", tags=["accounts"]
)
app.include_router(
    orders_router, prefix=f"{api_version_prefix}/orders", tags=["orders"]
)
app.include_router(
    payments_router, prefix=f"{api_version_prefix}/payments", tags=["payments"]
)
app.include_router(
    shopping_cart_router,
    prefix=f"{api_version_prefix}/shopping-cart",
    tags=["shopping_cart"],
)


@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui(current_user=Depends(get_current_user)):
    return get_swagger_ui_html(openapi_url="/openapi.json", title="API docs")


@app.get("/openapi.json", include_in_schema=False)
async def openapi(current_user=Depends(get_current_user)):
    return get_openapi(
        title="Online Cinema API",
        version="1.0.0",
        description="API documentation",
        routes=app.routes,
    )

@app.middleware("http")
async def catch_exceptions_middleware(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as e:
        print("Global catch Errors:", e)
        traceback.print_exc()
        return JSONResponse(
            {"detail": "Internal Server Error"},
            status_code=500
        )

@app.exception_handler(Exception)
async def exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": "Internal Server Error", "message": str(exc)},
    )

