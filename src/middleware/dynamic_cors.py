"""
Dynamic CORS middleware for chat-plugin support
Handles CORS dynamically based on pluginId-domain mapping from Backend
"""

import httpx
import asyncio
from typing import Set, Dict, Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from src.core.config import APP_CONFIG
import logging

logger = logging.getLogger(__name__)


class DynamicCORSMiddleware(BaseHTTPMiddleware):
    """
    Dynamic CORS middleware that allows origins based on plugin domain mappings
    """

    def __init__(self, app, backend_url: str):
        super().__init__(app)
        self.backend_url = backend_url
        self.domain_cache: Dict[str, Set[str]] = {}
        self.cache_ttl = 300  # 5 minutes cache
        self.last_cache_update: Dict[str, float] = {}

        # Register with internal API
        self._register_with_internal_api()

    async def dispatch(self, request: Request, call_next) -> Response:
        """Main CORS handling logic"""
        try:
            # Only handle chat-plugin streaming requests - let CORSMiddleware handle others
            if not self.is_chat_plugin_streaming_request(request):
                return await call_next(request)

            # Handle preflight (OPTIONS) requests for streaming routes
            if request.method == "OPTIONS":
                return await self.handle_preflight(request)

            # Handle actual streaming requests
            response = await call_next(request)
            await self.add_cors_headers(request, response)
            return response

        except Exception as e:
            logger.error(f"CORS middleware error: {e}")
            # Pass through to regular middleware chain on error
            return await call_next(request)

    async def handle_preflight(self, request: Request) -> Response:
        """Handle CORS preflight requests"""
        origin = request.headers.get("origin")

        if origin and await self.is_origin_allowed(request, origin):
            response = Response()
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Methods"] = (
                "GET, POST, PUT, DELETE, OPTIONS"
            )
            response.headers["Access-Control-Allow-Headers"] = "*"
            response.headers["Access-Control-Max-Age"] = "86400"  # 24 hours
            return response

        # Return 204 No Content for disallowed origins
        return Response(status_code=204)

    async def add_cors_headers(self, request: Request, response: Response):
        """Add CORS headers to actual responses"""
        origin = request.headers.get("origin")

        if origin and await self.is_origin_allowed(request, origin):
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Vary"] = "Origin"

    async def is_origin_allowed(self, request: Request, origin: str) -> bool:
        """Check if origin is allowed based on plugin configuration"""

        # Always allow configured origins from APP_CONFIG
        if origin in APP_CONFIG.get("cors_origins", []):
            return True

        # For chat-plugin requests, check dynamic CORS
        if self.is_chat_plugin_request(request):
            plugin_id = await self.extract_plugin_id(request)
            if plugin_id:
                allowed_domains = await self.get_allowed_domains(plugin_id)
                return origin in allowed_domains

        return False

    def is_chat_plugin_streaming_request(self, request: Request) -> bool:
        """Check if this is a chat-plugin streaming request that needs dynamic CORS"""
        path = request.url.path

        # Only streaming routes need dynamic CORS for chat-plugin support
        streaming_routes = [
            "/api/unified/chat-stream",  # Main streaming route for chat-plugin
        ]

        return any(path.startswith(route) for route in streaming_routes)

    def is_chat_plugin_request(self, request: Request) -> bool:
        """Check if this is a chat-plugin related request (legacy method)"""
        # Use the new streaming-specific method
        return self.is_chat_plugin_streaming_request(request)

    async def extract_plugin_id(self, request: Request) -> Optional[str]:
        """Extract pluginId from request headers, query params, or path"""
        try:
            # Try custom header first (recommended approach)
            plugin_id = request.headers.get("X-Plugin-Id")
            if plugin_id:
                return plugin_id

            # Try query params
            plugin_id = request.query_params.get(
                "pluginId"
            ) or request.query_params.get("plugin_id")
            if plugin_id:
                return plugin_id

            # Try to extract from URL path (if URL contains plugin info)
            path = request.url.path
            if "/plugin/" in path:
                # Extract from path like /api/unified/chat-stream/plugin/plugin_123
                parts = path.split("/plugin/")
                if len(parts) > 1:
                    return parts[1].split("/")[0]  # Get first part after /plugin/

        except Exception as e:
            logger.warning(f"Error extracting pluginId: {e}")

        return None

    async def get_allowed_domains(self, plugin_id: str) -> Set[str]:
        """Get allowed domains for a plugin from backend cache"""
        current_time = asyncio.get_event_loop().time()

        # Check cache first
        if (
            plugin_id in self.domain_cache
            and plugin_id in self.last_cache_update
            and current_time - self.last_cache_update[plugin_id] < self.cache_ttl
        ):
            return self.domain_cache[plugin_id]

        # Fetch from backend
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    f"{self.backend_url}/api/cors/plugin-domains",
                    params={"pluginId": plugin_id},
                )

                if response.status_code == 200:
                    data = response.json()
                    allowed_domains = set(data.get("allowedDomains", []))

                    # Update cache
                    self.domain_cache[plugin_id] = allowed_domains
                    self.last_cache_update[plugin_id] = current_time

                    logger.info(
                        f"Updated CORS cache for plugin {plugin_id}: {allowed_domains}"
                    )
                    return allowed_domains

        except Exception as e:
            logger.error(f"Error fetching allowed domains for plugin {plugin_id}: {e}")

        # Return empty set if fetch fails
        return set()

    async def update_plugin_domains(self, plugin_id: str, domains: list):
        """Update domain cache for a specific plugin"""
        self.domain_cache[plugin_id] = set(domains)
        self.last_cache_update[plugin_id] = asyncio.get_event_loop().time()
        logger.info(f"Cache updated for plugin {plugin_id}: {domains}")

    def clear_cache(self, plugin_id: Optional[str] = None):
        """Clear domain cache for specific plugin or all plugins"""
        if plugin_id:
            self.domain_cache.pop(plugin_id, None)
            self.last_cache_update.pop(plugin_id, None)
        else:
            self.domain_cache.clear()
            self.last_cache_update.clear()

        logger.info(f"Cleared CORS cache for plugin: {plugin_id or 'ALL'}")

    def _register_with_internal_api(self):
        """Register this middleware instance with internal API"""
        try:
            # Import here to avoid circular import
            from src.api.internal_cors_routes import set_cors_middleware

            set_cors_middleware(self)
            logger.info("✅ Dynamic CORS middleware registered with internal API")
        except Exception as e:
            logger.error(f"❌ Failed to register with internal API: {e}")
