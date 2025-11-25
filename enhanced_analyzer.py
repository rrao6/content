#!/usr/bin/env python3
"""Enhanced analyzer with timeout protection and better error handling."""
import signal
import threading
from functools import wraps
import time

class TimeoutError(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutError("Analysis timeout")

def with_timeout(seconds=30):
    """Decorator to add timeout to functions."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Use threading for timeout on systems where signal doesn't work well
            result = [None]
            exception = [None]
            
            def target():
                try:
                    result[0] = func(*args, **kwargs)
                except Exception as e:
                    exception[0] = e
            
            thread = threading.Thread(target=target)
            thread.daemon = True
            thread.start()
            thread.join(seconds)
            
            if thread.is_alive():
                # Thread is still running after timeout
                raise TimeoutError(f"Function {func.__name__} timed out after {seconds} seconds")
            
            if exception[0]:
                raise exception[0]
                
            return result[0]
        return wrapper
    return decorator

# Patch this into the analysis module
def patch_analysis_timeout():
    """Patches timeout protection into the analysis pipeline."""
    try:
        import sot_pipeline_parallel
        
        # Wrap the process_single_poster method with timeout
        original_method = sot_pipeline_parallel.ParallelSOTAnalysisPipeline._process_single_poster
        
        @with_timeout(seconds=30)  # 30 second timeout per poster
        def wrapped_process_single_poster(self, *args, **kwargs):
            return original_method(self, *args, **kwargs)
        
        sot_pipeline_parallel.ParallelSOTAnalysisPipeline._process_single_poster = wrapped_process_single_poster
        print("✅ Timeout protection patched")
        
    except Exception as e:
        print(f"❌ Could not patch timeout: {e}")

if __name__ == "__main__":
    patch_analysis_timeout()
