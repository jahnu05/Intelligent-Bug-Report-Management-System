
"""MongoDB Atlas connection helpers.

The service uses this module as the single place that knows how to create a
MongoDB client, ping the server, and return a database handle.

Set the following environment variables before running the app:

- MONGODB_URI
- MONGODB_DB_NAME
"""

from __future__ import annotations

import os
from functools import lru_cache

from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi


DEFAULT_DB_NAME = os.getenv("MONGODB_DB_NAME", "intelligent_bug_management")


def _resolve_mongodb_uri() -> str:
    uri = os.getenv("MONGODB_URI")
    if not uri:
        raise RuntimeError(
            "MONGODB_URI is not configured. Set it to your MongoDB Atlas connection string."
        )
    return uri


@lru_cache(maxsize=1)
def get_mongo_client() -> MongoClient:
    """Create a cached MongoDB client and verify connectivity."""

    client = MongoClient(
        _resolve_mongodb_uri(),
        server_api=ServerApi("1"),
        serverSelectionTimeoutMS=5000,
    )
    client.admin.command("ping")
    return client


def get_mongo_database(db_name: str | None = None):
    """Return the configured MongoDB database handle."""

    return get_mongo_client()[db_name or DEFAULT_DB_NAME]


if __name__ == "__main__":
    try:
        client = get_mongo_client()
        print("Pinged your deployment. You successfully connected to MongoDB!")
        print(f"Available databases: {client.list_database_names()}")
    except Exception as exc:
        print(exc)