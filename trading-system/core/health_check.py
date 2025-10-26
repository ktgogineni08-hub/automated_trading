#!/usr/bin/env python3
"""
Health Check System for Trading Platform
Provides comprehensive health and readiness endpoints for container orchestration
"""

import time
import psutil
from typing import Dict, Any, List, Tuple
from datetime import datetime, timedelta
from enum import Enum

class HealthStatus(Enum):
    """Health status levels"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"

class ComponentHealth:
    """Individual component health tracking"""
    
    def __init__(self, name: str):
        self.name = name
        self.status = HealthStatus.HEALTHY
        self.message = ""
        self.last_check = None
        self.check_duration_ms = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "last_check": self.last_check.isoformat() if self.last_check else None,
            "check_duration_ms": self.check_duration_ms
        }

class HealthCheckSystem:
    """
    Comprehensive health check system for the trading platform
    
    Provides:
    - Liveness probe: Is the application running?
    - Readiness probe: Can the application serve traffic?
    - Detailed health status for all components
    """
    
    def __init__(self):
        self.startup_time = datetime.utcnow()
        self.component_checks: Dict[str, ComponentHealth] = {}
        self.dependencies = {}  # Will be set by main application
        
    def register_dependency(self, name: str, check_func):
        """Register a dependency with its health check function"""
        self.dependencies[name] = check_func
        self.component_checks[name] = ComponentHealth(name)
    
    def liveness_probe(self) -> Tuple[bool, Dict[str, Any]]:
        """
        Liveness probe - indicates if the application is alive
        
        This should only fail if the application is deadlocked or crashed
        Returns False only in catastrophic failures
        
        Returns:
            Tuple of (is_alive, details)
        """
        try:
            # Basic checks that application is responsive
            response_time_start = time.time()
            
            # Check 1: Can we access system resources?
            try:
                cpu_percent = psutil.cpu_percent(interval=0.1)
                memory_info = psutil.virtual_memory()
            except Exception as e:
                return False, {
                    "status": "unhealthy",
                    "reason": "Cannot access system resources",
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat()
                }
            
            # Check 2: Is memory critically low?
            if memory_info.percent > 95:
                return False, {
                    "status": "unhealthy",
                    "reason": "Critical memory shortage",
                    "memory_percent": memory_info.percent,
                    "timestamp": datetime.utcnow().isoformat()
                }
            
            response_time_ms = (time.time() - response_time_start) * 1000
            
            # Application is alive
            return True, {
                "status": "alive",
                "uptime_seconds": (datetime.utcnow() - self.startup_time).total_seconds(),
                "memory_percent": memory_info.percent,
                "cpu_percent": cpu_percent,
                "response_time_ms": round(response_time_ms, 2),
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            # If we can't even run this check, we're in trouble
            return False, {
                "status": "unhealthy",
                "reason": "Liveness check failed",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def readiness_probe(self) -> Tuple[bool, Dict[str, Any]]:
        """
        Readiness probe - indicates if the application can serve traffic
        
        Checks all critical dependencies:
        - Database connectivity
        - Redis connectivity
        - API availability
        - System resources
        
        Returns:
            Tuple of (is_ready, details)
        """
        start_time = time.time()
        
        try:
            all_ready = True
            component_status = {}
            
            # Check all registered dependencies
            for name, check_func in self.dependencies.items():
                component = self.component_checks[name]
                component.last_check = datetime.utcnow()
                check_start = time.time()
                
                try:
                    is_healthy, message = check_func()
                    component.check_duration_ms = round((time.time() - check_start) * 1000, 2)
                    
                    if is_healthy:
                        component.status = HealthStatus.HEALTHY
                        component.message = message or "OK"
                    else:
                        component.status = HealthStatus.UNHEALTHY
                        component.message = message or "Check failed"
                        all_ready = False
                        
                except Exception as e:
                    component.status = HealthStatus.UNHEALTHY
                    component.message = f"Check error: {str(e)}"
                    component.check_duration_ms = round((time.time() - check_start) * 1000, 2)
                    all_ready = False
                
                component_status[name] = component.to_dict()
            
            # System resource checks
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Consider not ready if resources are critically low
            if memory.percent > 90:
                all_ready = False
                component_status['memory'] = {
                    "status": "unhealthy",
                    "message": f"Memory usage critical: {memory.percent}%"
                }
            
            if disk.percent > 90:
                all_ready = False
                component_status['disk'] = {
                    "status": "unhealthy",
                    "message": f"Disk usage critical: {disk.percent}%"
                }
            
            total_time_ms = round((time.time() - start_time) * 1000, 2)
            
            return all_ready, {
                "status": "ready" if all_ready else "not_ready",
                "components": component_status,
                "system": {
                    "memory_percent": memory.percent,
                    "disk_percent": disk.percent,
                    "cpu_percent": psutil.cpu_percent(interval=0.1)
                },
                "check_duration_ms": total_time_ms,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return False, {
                "status": "not_ready",
                "reason": "Readiness check failed",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def detailed_health(self) -> Dict[str, Any]:
        """
        Detailed health check with full diagnostics
        
        Returns comprehensive health information including:
        - All component statuses
        - System metrics
        - Performance indicators
        - Warnings and recommendations
        """
        is_alive, liveness = self.liveness_probe()
        is_ready, readiness = self.readiness_probe()
        
        # Determine overall health
        if not is_alive:
            overall_status = HealthStatus.UNHEALTHY
        elif not is_ready:
            overall_status = HealthStatus.DEGRADED
        else:
            overall_status = HealthStatus.HEALTHY
        
        # Collect warnings
        warnings = []
        memory = psutil.virtual_memory()
        if memory.percent > 80:
            warnings.append(f"High memory usage: {memory.percent}%")
        
        disk = psutil.disk_usage('/')
        if disk.percent > 80:
            warnings.append(f"High disk usage: {disk.percent}%")
        
        uptime_seconds = (datetime.utcnow() - self.startup_time).total_seconds()
        
        return {
            "status": overall_status.value,
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": round(uptime_seconds, 2),
            "uptime_human": str(timedelta(seconds=int(uptime_seconds))),
            "liveness": liveness,
            "readiness": readiness,
            "warnings": warnings,
            "version": "1.0.0",  # Should be read from version file
            "environment": "production"  # Should be read from config
        }

# Global health check system instance
health_check_system = HealthCheckSystem()

# Example dependency check functions
def check_database_connection() -> Tuple[bool, str]:
    """Check if database is accessible"""
    try:
        # This should be implemented with actual database connection
        # For now, return True as placeholder
        return True, "Database connection OK"
    except Exception as e:
        return False, f"Database error: {str(e)}"

def check_redis_connection() -> Tuple[bool, str]:
    """Check if Redis is accessible"""
    try:
        # This should be implemented with actual Redis connection
        return True, "Redis connection OK"
    except Exception as e:
        return False, f"Redis error: {str(e)}"

def check_zerodha_api() -> Tuple[bool, str]:
    """Check if Zerodha API is accessible"""
    try:
        # This should check actual API connectivity
        return True, "Zerodha API accessible"
    except Exception as e:
        return False, f"Zerodha API error: {str(e)}"

# Register dependencies
health_check_system.register_dependency("database", check_database_connection)
health_check_system.register_dependency("redis", check_redis_connection)
health_check_system.register_dependency("zerodha_api", check_zerodha_api)

if __name__ == "__main__":
    # Test health checks
    print("Testing Health Check System")
    print("="*60)
    
    print("\n1. Liveness Probe:")
    is_alive, liveness_data = health_check_system.liveness_probe()
    print(f"   Status: {'✓ ALIVE' if is_alive else '✗ DEAD'}")
    print(f"   Details: {liveness_data}")
    
    print("\n2. Readiness Probe:")
    is_ready, readiness_data = health_check_system.readiness_probe()
    print(f"   Status: {'✓ READY' if is_ready else '✗ NOT READY'}")
    print(f"   Details: {readiness_data}")
    
    print("\n3. Detailed Health:")
    health_data = health_check_system.detailed_health()
    print(f"   Overall Status: {health_data['status'].upper()}")
    print(f"   Uptime: {health_data['uptime_human']}")
    if health_data['warnings']:
        print(f"   Warnings: {health_data['warnings']}")
