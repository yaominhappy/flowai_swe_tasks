from fastapi import FastAPI

app = FastAPI(title="FlowAI Task Workspace")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
