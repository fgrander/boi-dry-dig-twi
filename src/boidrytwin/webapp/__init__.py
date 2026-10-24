"""Local web app for the plant twin (feature 003, specs/003-web-frontend).

A thin layer over the twin's public functions: it lists and plots run folders, edits and
starts scenarios, runs operator what-if cases and comparisons. It never changes the models;
every run goes through :mod:`boidrytwin.records`, like on the command line.

Requires the optional extra ``web`` (``uv sync --extra web``).
"""
