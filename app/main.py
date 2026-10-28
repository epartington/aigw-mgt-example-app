from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.data import get_current_user, get_dashboard_data, get_integration_tools

app = FastAPI(title="AI Gateway Portal")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


@app.get("/")
def root() -> RedirectResponse:
    return RedirectResponse(url="/dashboard")


@app.get("/dashboard")
def dashboard(request: Request):
    user = get_current_user()
    data = get_dashboard_data()
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {"active_nav": "dashboard", "username": user["name"], "data": data},
    )


@app.get("/integrations")
def integrations(request: Request, tool: str = "claude-code"):
    user = get_current_user()
    tools = get_integration_tools()
    valid_slugs = {t["slug"] for t in tools}
    active_tool = tool if tool in valid_slugs else tools[0]["slug"]
    return templates.TemplateResponse(
        request,
        "integrations.html",
        {
            "active_nav": "integrations",
            "username": user["name"],
            "tools": tools,
            "active_tool": active_tool,
        },
    )


@app.get("/help")
def help_page(request: Request):
    user = get_current_user()
    return templates.TemplateResponse(
        request,
        "help.html",
        {"active_nav": "help", "username": user["name"]},
    )


@app.get("/signout")
def signout() -> RedirectResponse:
    # Stub: no real session exists yet. Wire this up once the auth model
    # (service key / pass-through / hybrid, JWT vs. API key login) is decided.
    return RedirectResponse(url="/dashboard")
