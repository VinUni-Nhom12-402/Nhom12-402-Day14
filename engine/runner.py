import asyncio
import time
import logging
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
import random

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class BenchmarkConfig:
    """Configuration for benchmark runner"""
    batch_size: int = 5
    max_retries: int = 3
    timeout_seconds: int = 60
    rate_limit_delay: float = 0.1
    max_concurrent_requests: int = 10
    enable_progress_tracking: bool = True

@dataclass
class BenchmarkResult:
    """Result of a single benchmark test"""
    test_case: str
    agent_response: str
    latency: float
    ragas: Dict[str, Any]
    judge: Dict[str, Any]
    status: str
    error_message: Optional[str] = None
    retry_count: int = 0
    execution_time: float = 0.0

class BenchmarkRunner:
    def __init__(self, agent, evaluator, judge, config: Optional[BenchmarkConfig] = None):
        self.agent = agent
        self.evaluator = evaluator
        self.judge = judge
        self.config = config or BenchmarkConfig()
        self.semaphore = asyncio.Semaphore(self.config.max_concurrent_requests)
        self.executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="benchmark")
        self.stats = {
            "total_tests": 0,
            "successful_tests": 0,
            "failed_tests": 0,
            "total_retries": 0,
            "total_time": 0.0,
            "memory_peak": 0.0,
            "avg_batch_time": 0.0
        }
        self._shutdown = False
        self._active_tasks = set()

    async def _execute_with_timeout(self, coro, timeout: Optional[float] = None):
        """Execute coroutine with timeout"""
        timeout = timeout or self.config.timeout_seconds
        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except asyncio.TimeoutError:
            raise TimeoutError(f"Operation timed out after {timeout} seconds")

    async def _retry_with_backoff(self, func, *args, max_retries: Optional[int] = None, **kwargs):
        """Retry function with exponential backoff"""
        max_retries = max_retries or self.config.max_retries
        base_delay = 0.1
        
        for attempt in range(max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                if attempt == max_retries:
                    raise e
                
                delay = base_delay * (2 ** attempt) + random.uniform(0, 0.1)
                logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay:.2f}s")
                await asyncio.sleep(delay)
                self.stats["total_retries"] += 1

    async def run_single_test(self, test_case: Dict) -> BenchmarkResult:
        """Run a single test case with comprehensive error handling"""
        start_time = time.perf_counter()
        retry_count = 0
        
        async def _run_test():
            # 1. Gọi Agent với timeout
            agent_start = time.perf_counter()
            response = await self._execute_with_timeout(
                self.agent.query(test_case["question"])
            )
            agent_latency = time.perf_counter() - agent_start
            
            # 2. Chạy RAGAS metrics
            ragas_scores = await self._execute_with_timeout(
                self.evaluator.score(test_case, response)
            )
            
            # 3. Chạy Multi-Judge
            judge_result = await self._execute_with_timeout(
                self.judge.evaluate_multi_judge(
                    test_case["question"], 
                    response["answer"], 
                    test_case.get("expected_answer", "")
                )
            )
            
            return {
                "agent_response": response["answer"],
                "latency": agent_latency,
                "ragas": ragas_scores,
                "judge": judge_result,
                "status": "fail" if judge_result["final_score"] < 3 else "pass"
            }
        
        try:
            # Execute with retry mechanism
            result_data = await self._retry_with_backoff(_run_test)
            
            execution_time = time.perf_counter() - start_time
            
            result = BenchmarkResult(
                test_case=test_case["question"],
                agent_response=result_data["agent_response"],
                latency=result_data["latency"],
                ragas=result_data["ragas"],
                judge=result_data["judge"],
                status=result_data["status"],
                retry_count=retry_count,
                execution_time=execution_time
            )
            
            self.stats["successful_tests"] += 1
            return result
            
        except Exception as e:
            execution_time = time.perf_counter() - start_time
            error_msg = f"Test failed: {str(e)}"
            logger.error(f"Test case failed: {test_case.get('question', 'Unknown')[:50]}... - {error_msg}")
            
            result = BenchmarkResult(
                test_case=test_case["question"],
                agent_response="",
                latency=0.0,
                ragas={"faithfulness": 0.0, "relevancy": 0.0, "retrieval": {"hit_rate": 0.0, "mrr": 0.0}},
                judge={"final_score": 0.0, "agreement_rate": 0.0, "reasoning": error_msg},
                status="error",
                error_message=error_msg,
                retry_count=retry_count,
                execution_time=execution_time
            )
            
            self.stats["failed_tests"] += 1
            return result

    async def _process_batch_with_semaphore(self, batch: List[Dict], batch_idx: int) -> List[BenchmarkResult]:
        """Process a batch with semaphore for concurrency control"""
        async def _process_single_with_semaphore(test_case: Dict):
            async with self.semaphore:
                # Add rate limiting delay
                await asyncio.sleep(self.config.rate_limit_delay)
                return await self.run_single_test(test_case)
        
        tasks = [_process_single_with_semaphore(case) for case in batch]
        
        try:
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Handle exceptions in gather results
            processed_results = []
            for i, result in enumerate(batch_results):
                if isinstance(result, Exception):
                    logger.error(f"Unexpected error in batch {batch_idx}, item {i}: {result}")
                    # Create error result
                    error_result = BenchmarkResult(
                        test_case=batch[i]["question"],
                        agent_response="",
                        latency=0.0,
                        ragas={"faithfulness": 0.0, "relevancy": 0.0, "retrieval": {"hit_rate": 0.0, "mrr": 0.0}},
                        judge={"final_score": 0.0, "agreement_rate": 0.0, "reasoning": f"System error: {str(result)}"},
                        status="error",
                        error_message=f"System error: {str(result)}"
                    )
                    processed_results.append(error_result)
                    self.stats["failed_tests"] += 1
                else:
                    processed_results.append(result)
            
            return processed_results
            
        except Exception as e:
            logger.error(f"Batch {batch_idx} processing failed: {e}")
            # Return error results for entire batch
            error_results = []
            for case in batch:
                error_result = BenchmarkResult(
                    test_case=case["question"],
                    agent_response="",
                    latency=0.0,
                    ragas={"faithfulness": 0.0, "relevancy": 0.0, "retrieval": {"hit_rate": 0.0, "mrr": 0.0}},
                    judge={"final_score": 0.0, "agreement_rate": 0.0, "reasoning": f"Batch error: {str(e)}"},
                    status="error",
                    error_message=f"Batch error: {str(e)}"
                )
                error_results.append(error_result)
                self.stats["failed_tests"] += 1
            return error_results

    async def run_all(self, dataset: List[Dict], batch_size: Optional[int] = None) -> List[Dict]:
        """
        Run all tests with optimized async processing, error handling, and resource management.
        """
        if self._shutdown:
            raise RuntimeError("BenchmarkRunner has been shutdown")
            
        batch_size = batch_size or self.config.batch_size
        self.stats["total_tests"] = len(dataset)
        start_time = time.perf_counter()
        
        # Suppress logging during execution to avoid mixed output
        original_level = logger.level
        if self.config.enable_progress_tracking:
            logger.setLevel(logging.WARNING)  # Only show warnings/errors during execution
        
        print(f"🚀 Starting benchmark with {len(dataset)} test cases, batch size: {batch_size}")
        
        results = []
        batch_times = []
        
        # Process in batches with progress tracking
        total_batches = (len(dataset) + batch_size - 1) // batch_size
        for batch_idx, i in enumerate(range(0, len(dataset), batch_size)):
            if self._shutdown:
                break
                
            batch = dataset[i:i + batch_size]
            batch_start = time.perf_counter()
            
            # Progress tracking with clean output
            completed = min(i + batch_size, len(dataset))
            progress = (completed / len(dataset)) * 100
            print(f"\r📊 Batch {batch_idx + 1}/{total_batches} ({len(batch)} items) - Progress: {completed}/{len(dataset)} ({progress:.1f}%)", end="", flush=True)
            
            batch_results = await self._process_batch_with_semaphore(batch, batch_idx)
            results.extend(batch_results)
            
            batch_time = time.perf_counter() - batch_start
            batch_times.append(batch_time)
            
            # Clean progress line
            print(f"\r{' ' * 100}\r", end="", flush=True)
        
        total_time = time.perf_counter() - start_time
        self.stats["total_time"] = total_time
        self.stats["avg_batch_time"] = sum(batch_times) / len(batch_times) if batch_times else 0
        
        # Restore logging level
        logger.setLevel(original_level)
        
        # Final statistics output
        print(f"\n✅ Benchmark completed in {total_time:.2f}s")
        print(f"📈 Success: {self.stats['successful_tests']}, Failed: {self.stats['failed_tests']}, Total retries: {self.stats['total_retries']}")
        
        # Convert BenchmarkResult objects to dicts for compatibility
        dict_results = []
        for result in results:
            result_dict = {
                "test_case": result.test_case,
                "agent_response": result.agent_response,
                "latency": result.latency,
                "ragas": result.ragas,
                "judge": result.judge,
                "status": result.status,
                "execution_time": result.execution_time
            }
            if result.error_message:
                result_dict["error_message"] = result.error_message
            if result.retry_count > 0:
                result_dict["retry_count"] = result.retry_count
            dict_results.append(result_dict)
        
        return dict_results

    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive execution statistics"""
        return {
            **self.stats,
            "success_rate": self.stats["successful_tests"] / max(self.stats["total_tests"], 1),
            "average_test_time": self.stats["total_time"] / max(self.stats["total_tests"], 1),
            "retry_rate": self.stats["total_retries"] / max(self.stats["total_tests"], 1)
        }

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - cleanup resources"""
        await self._cleanup()
    
    async def _cleanup(self):
        """Cleanup resources properly"""
        self._shutdown = True
        
        # Cancel all active tasks
        if self._active_tasks:
            for task in self._active_tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*self._active_tasks, return_exceptions=True)
            self._active_tasks.clear()
        
        # Shutdown thread pool
        if self.executor:
            self.executor.shutdown(wait=True)
    
    def __del__(self):
        """Destructor - ensure cleanup"""
        if hasattr(self, 'executor') and self.executor:
            try:
                self.executor.shutdown(wait=False)
            except:
                pass
