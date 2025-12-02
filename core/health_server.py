#!/usr/bin/env python3
"""
Health Check HTTP Server
Provides HTTP endpoints for Kubernetes probes and monitoring
"""

import json
import http.server
import socketserver
from urllib.parse import urlparse, parse_qs
from core.health_check import health_check_system

class HealthCheckHandler(http.server.BaseHTTPRequestHandler):
    """HTTP handler for health check endpoints"""
    
    def log_message(self, format, *args):
        """Suppress default logging (use structured logger instead)"""
        pass
    
    def send_json_response(self, status_code: int, data: dict):
        """Send JSON response"""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())
    
    def do_GET(self):
        """Handle GET requests"""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        
        # Health endpoint - detailed health information
        if path == '/health':
            health_data = health_check_system.detailed_health()
            status_code = 200 if health_data['status'] in ['healthy', 'degraded'] else 503
            self.send_json_response(status_code, health_data)
        
        # Liveness endpoint - for Kubernetes liveness probe
        elif path == '/health/live' or path == '/live':
            is_alive, data = health_check_system.liveness_probe()
            status_code = 200 if is_alive else 503
            self.send_json_response(status_code, data)
        
        # Readiness endpoint - for Kubernetes readiness probe
        elif path == '/health/ready' or path == '/ready':
            is_ready, data = health_check_system.readiness_probe()
            status_code = 200 if is_ready else 503
            self.send_json_response(status_code, data)
        
        # Ping endpoint - simple alive check
        elif path == '/ping':
            self.send_json_response(200, {"status": "pong"})
        
        # Version endpoint
        elif path == '/version':
            self.send_json_response(200, {
                "version": "1.0.0",
                "build": "production",
                "timestamp": health_check_system.startup_time.isoformat()
            })
        
        # 404 for unknown paths
        else:
            self.send_json_response(404, {
                "error": "Not found",
                "available_endpoints": [
                    "/health",
                    "/health/live",
                    "/health/ready",
                    "/ping",
                    "/version"
                ]
            })

def start_health_server(port: int = 9090):
    """
    Start health check HTTP server
    
    Args:
        port: Port to listen on (default 9090 for metrics/health)
    """
    try:
        with socketserver.TCPServer(("", port), HealthCheckHandler) as httpd:
            print(f"✓ Health check server running on port {port}")
            print(f"  Endpoints:")
            print(f"    http://localhost:{port}/health       - Detailed health")
            print(f"    http://localhost:{port}/health/live  - Liveness probe")
            print(f"    http://localhost:{port}/health/ready - Readiness probe")
            print(f"    http://localhost:{port}/ping         - Simple ping")
            print(f"    http://localhost:{port}/version      - Version info")
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nHealth server stopped")
    except Exception as e:
        print(f"Error starting health server: {e}")
        raise

if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9090
    start_health_server(port)
