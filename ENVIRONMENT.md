# Task Environment

- Language: `python`
- Version: `3.12`
- Package manager: `pip`
- Runtime environment: `docker`

## Frameworks
- fastapi

## Dependencies
- fastapi
- sqlalchemy
- uvicorn
- pytest
- httpx

## Testing Frameworks
- pytest

## Setup Instructions
- Create an isolated virtual environment before installing dependencies.
- Install dependencies from requirements.txt and keep runtime/test dependencies reproducible.

## Provisioning Policies
- Prefer pinned dependencies for reproducible builds.
- Keep the generated workspace isolated from FlowAI service source code.
