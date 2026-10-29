import httpx
from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.auth import (
    RedirectToLogin,
    get_session_access_token,
    get_session_claims,
    get_session_refresh_token,
    handle_callback,
    refresh_access_token,
    require_login,
    start_login,
)
from app.config import settings
from app.data import (
    get_catalog_mcp_tools,
    get_catalog_models,
    get_dashboard_data,
    get_display_name,
    get_integration_tools,
)
from app.token_panel import build_token_panel_response

app = FastAPI(title="AI Developer Portal")
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


@app.exception_handler(RedirectToLogin)
def _redirect_to_login(request: Request, exc: RedirectToLogin) -> RedirectResponse:
    # Goes to the landing page, not straight to /login: the IDP redirect
    # should only fire when the user clicks "Sign in," not automatically
    # whenever a protected page is visited without a session.
    return RedirectResponse(url="/")


@app.get("/")
def root(request: Request):
    if get_session_claims(request) is not None:
        return RedirectResponse(url="/dashboard")
    return templates.TemplateResponse(request, "landing.html", {})


@app.get("/login")
async def login(request: Request):
    return await start_login(request)


@app.get("/callback")
async def auth_callback(request: Request) -> RedirectResponse:
    claims, access_token, refresh_token = await handle_callback(request)
    request.session["claims"] = claims
    request.session["access_token"] = access_token
    request.session["refresh_token"] = refresh_token
    return RedirectResponse(url="/dashboard")


@app.get("/dashboard")
def dashboard(request: Request, claims: dict = Depends(require_login)):
    data = get_dashboard_data(claims)
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {"active_nav": "dashboard", "username": data.username, "data": data},
    )


@app.get("/catalog")
def catalog(request: Request, tab: str = "models", claims: dict = Depends(require_login)):
    active_tab = tab if tab in {"models", "mcp-tools"} else "models"
    tab_data = get_catalog_models(claims) if active_tab == "models" else get_catalog_mcp_tools(claims)
    return templates.TemplateResponse(
        request,
        "catalog.html",
        {
            "active_nav": "catalog",
            "username": get_display_name(claims),
            "active_tab": active_tab,
            "tab_data": tab_data,
        },
    )


@app.get("/integrations")
def integrations(request: Request, tool: str = "claude-code", claims: dict = Depends(require_login)):
    tools = get_integration_tools()
    valid_slugs = {t["slug"] for t in tools}
    active_tool = tool if tool in valid_slugs else tools[0]["slug"]
    return templates.TemplateResponse(
        request,
        "integrations.html",
        {
            "active_nav": "integrations",
            "username": get_display_name(claims),
            "tools": tools,
            "active_tool": active_tool,
        },
    )


@app.get("/help")
def help_page(request: Request, claims: dict = Depends(require_login)):
    return templates.TemplateResponse(
        request,
        "help.html",
        {"active_nav": "help", "username": get_display_name(claims)},
    )


@app.get("/ui/token.json")
def ui_token(request: Request, claims: dict = Depends(require_login)):
    return build_token_panel_response(get_session_access_token(request))


@app.post("/ui/token/refresh")
async def ui_token_refresh(request: Request, claims: dict = Depends(require_login)):
    """Get a genuinely new access token from the IDP, not just re-read the old one."""
    refresh_token = get_session_refresh_token(request)
    if not refresh_token:
        return JSONResponse(
            status_code=400,
            content={
                "error": "No refresh token in this session. Sign out and sign back in "
                "— this session may predate the offline_access scope being added."
            },
        )

    try:
        new_claims, new_access_token, new_refresh_token = await refresh_access_token(refresh_token)
    except httpx.HTTPError as exc:
        return JSONResponse(status_code=400, content={"error": f"Refresh failed: {exc}"})

    request.session["claims"] = new_claims
    request.session["access_token"] = new_access_token
    request.session["refresh_token"] = new_refresh_token
    return build_token_panel_response(new_access_token)


@app.get("/signout")
def signout(request: Request) -> RedirectResponse:
    # Clears this app's session only — the IDP's own SSO session stays
    # active. Goes to the landing page, not straight back into /login:
    # an automatic re-authorize right after sign-out can hit the IDP's
    # own assignment/session checks in ways a user-initiated one doesn't.
    request.session.clear()
    return RedirectResponse(url="/")
