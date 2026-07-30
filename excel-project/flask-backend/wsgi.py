"""Gunicorn entry point for production deployments."""

from app import app

__all__ = ['app']
