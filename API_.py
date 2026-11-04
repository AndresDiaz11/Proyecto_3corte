import os
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pymongo import MongoClient

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass