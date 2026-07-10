# Tool Execution Report 2

- Command: `python3 -m pip install -r requirements.txt`
- Status: `completed`
- Exit code: `0`
- Log path: `/Users/minyao/.flowai/sandboxes/1574a745-bfb5-4cbd-9ba7-647f54b7e888/2ad2ccee-1eb8-48b0-a906-c28f695d0740/_run_shared/_run_shared/logs/tool_2.log`

## Stdout
Collecting fastapi==0.111.0 (from -r requirements.txt (line 2))
  Using cached fastapi-0.111.0-py3-none-any.whl.metadata (25 kB)
Collecting uvicorn==0.29.0 (from -r requirements.txt (line 3))
  Using cached uvicorn-0.29.0-py3-none-any.whl.metadata (6.3 kB)
Collecting sqlalchemy==2.0.30 (from -r requirements.txt (line 4))
  Using cached SQLAlchemy-2.0.30-cp312-cp312-macosx_11_0_arm64.whl.metadata (9.6 kB)
Collecting aiosqlite==0.20.0 (from -r requirements.txt (line 5))
  Using cached aiosqlite-0.20.0-py3-none-any.whl.metadata (4.3 kB)
Collecting pydantic==2.7.1 (from -r requirements.txt (line 6))
  Using cached pydantic-2.7.1-py3-none-any.whl.metadata (107 kB)
Collecting python-jose==3.3.0 (from python-jose[cryptography]==3.3.0->-r requirements.txt (line 7))
  Using cached python_jose-3.3.0-py2.py3-none-any.whl.metadata (5.4 kB)
Collecting anyio==4.3.0 (from -r requirements.txt (line 8))
  Using cached anyio-4.3.0-py3-none-any.whl.metadata (4.6 kB)
Collecting httpx==0.27.0 (from -r requirements.txt (line 11))
  Using cached httpx-0.27.0-py3-none-any.whl.metadata (7.2 kB)
Collecting pytest==8.2.0 (from -r requirements.txt (line 12))
  Using cached pytest-8.2.0-py3-none-any.whl.metadata (7.5 kB)
Collecting pytest-asyncio==0.23.6 (from -r requirements.txt (line 13))
  Using cached pytest_asyncio-0.23.6-py3-none-any.whl.metadata (3.9 kB)
Collecting pytest-cov==5.0.0 (from -r requirements.txt (line 14))
  Using cached pytest_cov-5.0.0-py3-none-any.whl.metadata (27 kB)
Collecting starlette<0.38.0,>=0.37.2 (from fastapi==0.111.0->-r requirements.txt (line 2))
  Using cached starlette-0.37.2-py3-none-any.whl.metadata (5.9 kB)
Requirement already satisfied: typing-extensions>=4.8.0 in /Users/minyao/projects/flowai/flowai-backend/.venv/lib/python3.12/site-packages (from fastapi==0.111.0->-r requirements.txt (line 2)) (4.15.0)
Requirement already satisfied: fastapi-cli>=0.0.2 in /Users/minyao/projects/flowai/flowai-backend/.venv/lib/python3.12/site-packages (from fastapi==0.111...[truncated]

## Stderr
ERROR: pip's dependency resolver does not currently take into account all the packages that are installed. This behaviour is the source of the following dependency conflicts.
sse-starlette 3.3.4 requires anyio>=4.7.0, but you have anyio 4.3.0 which is incompatible.
sse-starlette 3.3.4 requires starlette>=0.49.1, but you have starlette 0.37.2 which is incompatible.
flowai-backend 0.1.0 requires aiosqlite<1.0.0,>=0.21.0, but you have aiosqlite 0.20.0 which is incompatible.
flowai-backend 0.1.0 requires fastapi<1.0.0,>=0.116.0, but you have fastapi 0.111.0 which is incompatible.
flowai-backend 0.1.0 requires httpx<1.0.0,>=0.28.1, but you have httpx 0.27.0 which is incompatible.
flowai-backend 0.1.0 requires sqlalchemy<3.0.0,>=2.0.40, but you have sqlalchemy 2.0.30 which is incompatible.
flowai-backend 0.1.0 requires uvicorn[standard]<1.0.0,>=0.35.0, but you have uvicorn 0.29.0 which is incompatible.
mcp 1.27.0 requires anyio>=4.5, but you have anyio 4.3.0 which is incompatible.
mcp 1.27.0 requires httpx>=0.27.1, but you have httpx 0.27.0 which is incompatible.
mcp 1.27.0 requires pydantic<3.0.0,>=2.11.0, but you have pydantic 2.7.1 which is incompatible.
mcp 1.27.0 requires uvicorn>=0.31.1; sys_platform != "emscripten", but you have uvicorn 0.29.0 which is incompatible.

[notice] A new release of pip is available: 25.2 -> 26.1
[notice] To update, run: /Users/minyao/projects/flowai/flowai-backend/.venv/bin/python3 -m pip install --upgrade pip
