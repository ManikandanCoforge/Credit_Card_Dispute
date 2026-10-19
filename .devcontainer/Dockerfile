FROM mcr.microsoft.com/devcontainers/python:3.12-bookworm

USER root
COPY --from=ghcr.io/astral-sh/uv:0.12.20 /uv /uvx /usr/local/bin/
RUN chmod 755 /usr/local/bin/uv /usr/local/bin/uvx
USER vscode