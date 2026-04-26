#!/usr/bin/env python3
"""
Performance Monitoring and Architecture Analysis Tool
Measures non-functional requirements for the Intelligent Bug Report Management System
"""

import asyncio
import time
import statistics
import json
import os
import requests
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any
import psutil
import platform
import pymongo
from datetime import datetime

class PerformanceMonitor:
    def __init__(self, api_base: str = "http://localhost:8000"):
        self.api_base = api_base
        self.results = {}
        
    async def measure_response_time(self, endpoint: str, method: str = "GET", data: Dict = None, iterations: int = 10) -> Dict[str, Any]:
        """Measure response time for API endpoints"""
        print(f"🔍 Measuring response time for {method} {endpoint}")
        
        response_times = []
        error_count = 0
        
        for i in range(iterations):
            try:
                start_time = time.time()
                
                if method == "GET":
                    response = requests.get(f"{self.api_base}{endpoint}", timeout=30)
                elif method == "POST":
                    response = requests.post(f"{self.api_base}{endpoint}", json=data, timeout=30)
                
                end_time = time.time()
                
                if response.status_code == 200:
                    response_times.append((end_time - start_time) * 1000)  # Convert to ms
                else:
                    error_count += 1
                    
                # Small delay between requests
                await asyncio.sleep(0.1)
                
            except Exception as e:
                error_count += 1
                print(f"  ❌ Request {i+1} failed: {e}")
        
        if response_times:
            return {
                "endpoint": endpoint,
                "method": method,
                "iterations": iterations,
                "errors": error_count,
                "avg_response_time_ms": statistics.mean(response_times),
                "min_response_time_ms": min(response_times),
                "max_response_time_ms": max(response_times),
                "median_response_time_ms": statistics.median(response_times),
                "p95_response_time_ms": sorted(response_times)[int(len(response_times) * 0.95)],
                "p99_response_time_ms": sorted(response_times)[int(len(response_times) * 0.99)],
                "success_rate": ((iterations - error_count) / iterations) * 100
            }
        else:
            return {"endpoint": endpoint, "error": "All requests failed"}
    
    async def measure_throughput(self, endpoint: str, method: str = "GET", data: Dict = None, duration_seconds: int = 30) -> Dict[str, Any]:
        """Measure throughput (requests per second)"""
        print(f"🚀 Measuring throughput for {method} {endpoint} over {duration_seconds}s")
        
        start_time = time.time()
        end_time = start_time + duration_seconds
        request_count = 0
        error_count = 0
        
        async def make_request():
            nonlocal request_count, error_count
            try:
                if method == "GET":
                    response = requests.get(f"{self.api_base}{endpoint}", timeout=10)
                elif method == "POST":
                    response = requests.post(f"{self.api_base}{endpoint}", json=data, timeout=10)
                
                if response.status_code == 200:
                    request_count += 1
                else:
                    error_count += 1
            except:
                error_count += 1
        
        # Concurrent requests
        tasks = []
        while time.time() < end_time:
            tasks.append(make_request())
            if len(tasks) >= 10:  # Batch of 10 concurrent requests
                await asyncio.gather(*tasks)
                tasks = []
                await asyncio.sleep(0.01)  # Small delay
        
        # Remaining tasks
        if tasks:
            await asyncio.gather(*tasks)
        
        actual_duration = time.time() - start_time
        throughput = request_count / actual_duration if actual_duration > 0 else 0
        
        return {
            "endpoint": endpoint,
            "method": method,
            "duration_seconds": actual_duration,
            "total_requests": request_count + error_count,
            "successful_requests": request_count,
            "failed_requests": error_count,
            "throughput_rps": throughput,
            "success_rate": (request_count / (request_count + error_count)) * 100 if (request_count + error_count) > 0 else 0
        }
    
    def measure_system_resources(self) -> Dict[str, Any]:
        """Measure system resource usage"""
        print("💻 Measuring system resources")
        
        # CPU and Memory
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Network
        network = psutil.net_io_counters()
        
        return {
            "cpu_percent": cpu_percent,
            "memory_total_gb": memory.total / (1024**3),
            "memory_available_gb": memory.available / (1024**3),
            "memory_used_gb": memory.used / (1024**3),
            "memory_percent": memory.percent,
            "disk_total_gb": disk.total / (1024**3),
            "disk_used_gb": disk.used / (1024**3),
            "disk_free_gb": disk.free / (1024**3),
            "network_bytes_sent": network.bytes_sent,
            "network_bytes_recv": network.bytes_recv
        }
    
    def measure_database_performance(self, mongo_uri: str) -> Dict[str, Any]:
        """Measure database performance"""
        print("🗄️ Measuring database performance")
        
        client = None
        try:
            client = pymongo.MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
            db = client.bug_management_contributor_intel
            
            # Test connection first
            client.admin.command('ping')
            
            # Test query performance
            start_time = time.time()
            issues = list(db.issues.find().limit(100))
            query_time = (time.time() - start_time) * 1000
            
            start_time = time.time()
            assignments = list(db.assignments.find().limit(100))
            assignment_query_time = (time.time() - start_time) * 1000
            
            # Collection stats - get all data before closing
            db_stats = db.command("dbStats")
            collection_names = db.list_collection_names()
            
            return {
                "database_connected": True,
                "issues_query_time_ms": query_time,
                "assignments_query_time_ms": assignment_query_time,
                "database_size_mb": db_stats.get("dataSize", 0) / (1024**2),
                "collections_count": len(collection_names),
                "issues_count": len(issues),
                "assignments_count": len(assignments)
            }
            
        except Exception as e:
            return {
                "database_connected": False,
                "error": str(e)
            }
        finally:
            if client:
                client.close()
    
    async def run_comprehensive_analysis(self) -> Dict[str, Any]:
        """Run complete performance analysis"""
        print("🎯 Starting Comprehensive Architecture Analysis\n")
        
        # Load environment variables
        from dotenv import load_dotenv
        load_dotenv()
        
        mongo_uri = os.getenv("MONGODB_URI", "")
        
        results = {
            "analysis_timestamp": datetime.now().isoformat(),
            "system_info": {
                "platform": platform.platform(),
                "python_version": platform.python_version(),
                "cpu_count": psutil.cpu_count(),
                "memory_total_gb": psutil.virtual_memory().total / (1024**3)
            }
        }
        
        # 1. Response Time Analysis
        print("\n📊 RESPONSE TIME ANALYSIS")
        print("=" * 50)
        
        response_time_tests = [
            ("/health", "GET"),
            ("/repositories/pandas-dev/pandas/issues?limit=20", "GET"),
            ("/repositories/pandas-dev/pandas/assignments?limit=20", "GET"),
        ]
        
        response_results = []
        for endpoint, method in response_time_tests:
            result = await self.measure_response_time(endpoint, method)
            response_results.append(result)
            print(f"  ✅ {endpoint}: {result.get('avg_response_time_ms', 'N/A'):.2f}ms avg")
        
        results["response_time_analysis"] = response_results
        
        # 2. Throughput Analysis
        print("\n🚀 THROUGHPUT ANALYSIS")
        print("=" * 50)
        
        throughput_tests = [
            ("/health", "GET"),
            ("/repositories/pandas-dev/pandas/issues?limit=20", "GET"),
        ]
        
        throughput_results = []
        for endpoint, method in throughput_tests:
            result = await self.measure_throughput(endpoint, method, duration_seconds=15)
            throughput_results.append(result)
            print(f"  ✅ {endpoint}: {result.get('throughput_rps', 'N/A'):.2f} RPS")
        
        results["throughput_analysis"] = throughput_results
        
        # 3. System Resources
        print("\n💻 SYSTEM RESOURCE ANALYSIS")
        print("=" * 50)
        
        system_resources = self.measure_system_resources()
        results["system_resources"] = system_resources
        print(f"  ✅ CPU: {system_resources['cpu_percent']:.1f}%")
        print(f"  ✅ Memory: {system_resources['memory_used_gb']:.1f}GB / {system_resources['memory_total_gb']:.1f}GB")
        
        # 4. Database Performance
        print("\n🗄️ DATABASE PERFORMANCE ANALYSIS")
        print("=" * 50)
        
        if mongo_uri:
            db_performance = self.measure_database_performance(mongo_uri)
            results["database_performance"] = db_performance
            if db_performance.get("database_connected"):
                print(f"  ✅ Issues Query: {db_performance.get('issues_query_time_ms', 'N/A'):.2f}ms")
                print(f"  ✅ Assignments Query: {db_performance.get('assignments_query_time_ms', 'N/A'):.2f}ms")
            else:
                print(f"  ❌ Database connection failed: {db_performance.get('error')}")
        else:
            print("  ⚠️ No MongoDB URI provided")
            results["database_performance"] = {"error": "No MongoDB URI provided"}
        
        # 5. Complex Operation Analysis (Duplicate Detection)
        print("\n🔍 COMPLEX OPERATION ANALYSIS")
        print("=" * 50)
        
        duplicate_detection_data = {
            "similarity_threshold": 0.7,
            "max_results": 10
        }
        
        complex_result = await self.measure_response_time(
            "/repositories/pandas-dev/pandas/issues/65320/detect-duplicates", 
            "POST", 
            duplicate_detection_data, 
            iterations=5
        )
        results["complex_operation_analysis"] = complex_result
        print(f"  ✅ Duplicate Detection: {complex_result.get('avg_response_time_ms', 'N/A'):.2f}ms avg")
        
        return results

async def main():
    """Main execution function"""
    monitor = PerformanceMonitor()
    
    try:
        results = await monitor.run_comprehensive_analysis()
        
        # Save results
        with open("performance_results.json", "w") as f:
            json.dump(results, f, indent=2)
        
        print(f"\n✅ Analysis complete! Results saved to performance_results.json")
        return results
        
    except Exception as e:
        print(f"❌ Analysis failed: {e}")
        return None

if __name__ == "__main__":
    asyncio.run(main())
