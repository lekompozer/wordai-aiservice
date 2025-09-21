#!/usr/bin/env python3
"""
Start worker in development environment
"""
import os
import sys
import asyncio

# Force development environment
os.environ['ENVIRONMENT'] = 'development'
os.environ['ENV'] = 'development'

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import and run worker
from src.workers.ingestion_worker import main

if __name__ == "__main__":
    asyncio.run(main())
