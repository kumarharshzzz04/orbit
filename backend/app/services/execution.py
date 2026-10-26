"""Safe ML sandbox execution service for ORBIT backend."""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
import uuid
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..db.config import session_scope
from ..db.models import (
    ExecutionStatus,
    ExperimentAttempt,
)
from ..schemas.ws import (
    WSMessagePayload,
)
from ..services.registry import (
    insert_experiment,
    record_attempt_completion,
    record_attempt_start,
)
from ..services.ws_manager import get_ws_manager

LOG = logging.getLogger("orbit.execution")


@dataclass
class ExecutionResult:
    """Result of an experiment execution."""

    success: bool
    experiment_id: str | None = None
    attempt_id: str = ""
    error_type: str | None = None
    error_message: str | None = None
    run_record: dict[str, Any] | None = None
    stdout_tail: str | None = None
    stderr_tail: str | None = None
    duration_seconds: float = 0.0


class MLExecutionService:
    """
    Service for safely executing ML sandbox training runs as subprocesses.

    Features:
    - Async execution without blocking FastAPI event loop
    - Proper subprocess lifecycle management (timeouts, cancellation, cleanup)
    - Progress event parsing and WebSocket broadcasting
    - Attempt persistence
    - Result validation and experiment registration
    """

    def __init__(
        self,
        repo_root: Path,
        max_concurrent: int = 1,
        default_timeout: float = 600.0,  # 10 minutes
    ):
        self.repo_root = Path(repo_root).resolve()
        self.backend_dir = self.repo_root / "backend"
        self.artifacts_dir = self.repo_root / "artifacts"
        self.max_concurrent = max_concurrent
        self.default_timeout = default_timeout
        self._semaphore: asyncio.Semaphore | None = None
        self._running_tasks: dict[str, asyncio.Task] = {}
        self._progress_callbacks: list[
            Callable[[str, WSMessagePayload], Awaitable[None]]
        ] = []

    async def start(self):
        """Initialize the service."""
        self._semaphore = asyncio.Semaphore(self.max_concurrent)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

    async def stop(self):
        """Stop the service and cancel running tasks."""
        for task in self._running_tasks.values():
            task.cancel()
        if self._running_tasks:
            await asyncio.gather(*self._running_tasks.values(), return_exceptions=True)
        self._running_tasks.clear()

    def register_progress_callback(
        self, callback: Callable[[str, WSMessagePayload], Awaitable[None]]
    ):
        """Register a callback for progress events."""
        self._progress_callbacks.append(callback)

    async def _broadcast_progress(self, mission_id: str, payload: dict[str, Any]):
        """Broadcast progress to registered callbacks and WebSocket manager."""
        # Call registered callbacks
        for callback in self._progress_callbacks:
            try:
                await callback(mission_id, payload)
            except Exception as e:
                LOG.warning("Progress callback failed: %s", e)

        # Also broadcast to WebSocket if mission_id provided
        if mission_id:
            ws_manager = get_ws_manager()
            try:
                stage = payload.get("stage", "")
                if stage in ("load", "loaded", "train", "calibration", "saved"):
                    await ws_manager.broadcast_run_progress(
                        mission_id=mission_id,
                        run_id=payload.get("config", "") or payload.get("run_id", ""),
                        stage=stage,
                        percent=payload.get("percent", 0.0),
                    )
                elif stage == "metrics":
                    await ws_manager.broadcast_run_metrics(
                        mission_id=mission_id,
                        run_id=payload.get("run_id", ""),
                        metrics=payload.get("metrics", {}),
                    )
                elif stage == "verdict":
                    await ws_manager.broadcast_verdict(
                        mission_id=mission_id,
                        run_id=payload.get("run_id", ""),
                        kept=payload.get("kept", False),
                        rationale=payload.get("rationale", ""),
                    )
            except Exception as e:
                LOG.warning("WebSocket broadcast failed: %s", e)

    @asynccontextmanager
    async def _execution_context(self, mission_id: str | None = None):
        """Context manager for execution concurrency control."""
        if self._semaphore is None:
            await self.start()
        async with self._semaphore:
            yield

    def _parse_orbit_progress(self, line: str) -> dict[str, Any] | None:
        """Parse ORBIT_PROGRESS line from stderr."""
        prefix = "ORBIT_PROGRESS "
        if line.startswith(prefix):
            try:
                return json.loads(line[len(prefix) :])
            except json.JSONDecodeError:
                return None
        return None

    async def _run_subprocess(
        self,
        cmd: list[str],
        cwd: Path,
        attempt_id: str,
        mission_id: str | None = None,
        timeout: float | None = None,
        cancellation_event: asyncio.Event | None = None,
    ) -> tuple[int, str, str]:
        """
        Run subprocess with proper async handling, timeout, and cancellation.

        Returns (returncode, stdout, stderr)
        """
        timeout = timeout or self.default_timeout
        stdout_chunks = []
        stderr_chunks = []

        LOG.info("Starting subprocess: %s", " ".join(cmd))

        try:
            # Use create_subprocess_exec for proper argument handling (no shell)
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(cwd),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                limit=1024 * 1024,  # 1MB buffer limit
            )

            # Track the process for cancellation
            self._running_tasks[attempt_id] = asyncio.current_task()

            async def read_stream(
                stream: asyncio.StreamReader, chunks: list, is_stderr: bool = False
            ):
                """Read stream and parse progress events."""
                while True:
                    line_bytes = await stream.readline()
                    if not line_bytes:
                        break
                    line = line_bytes.decode("utf-8", errors="replace").rstrip("\n")
                    chunks.append(line)

                    # Parse progress from stderr
                    if is_stderr and mission_id:
                        progress = self._parse_orbit_progress(line)
                        if progress:
                            await self._broadcast_progress(mission_id, progress)

            # Read both streams concurrently
            stdout_task = asyncio.create_task(
                read_stream(process.stdout, stdout_chunks, False)
            )
            stderr_task = asyncio.create_task(
                read_stream(process.stderr, stderr_chunks, True)
            )

            # Wait for completion with timeout and cancellation support
            try:
                if cancellation_event:
                    # Wait for either process completion or cancellation
                    done, pending = await asyncio.wait(
                        [
                            asyncio.create_task(process.wait()),
                            asyncio.create_task(cancellation_event.wait()),
                        ],
                        timeout=timeout,
                        return_when=asyncio.FIRST_COMPLETED,
                    )

                    if cancellation_event.is_set():
                        # Cancellation requested
                        LOG.warning(
                            "Execution %s cancelled, terminating process", attempt_id
                        )
                        process.terminate()
                        try:
                            await asyncio.wait_for(process.wait(), timeout=5.0)
                        except TimeoutError:
                            process.kill()
                            await process.wait()
                        raise asyncio.CancelledError(
                            f"Execution {attempt_id} cancelled"
                        )

                    # Process completed, get return code
                    for task in done:
                        if not task.cancelled():
                            returncode = task.result()
                            break
                    else:
                        returncode = await process.wait()
                else:
                    # Simple timeout wait
                    returncode = await asyncio.wait_for(process.wait(), timeout=timeout)

            except TimeoutError:
                LOG.warning(
                    "Execution %s timed out after %.1fs, terminating",
                    attempt_id,
                    timeout,
                )
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=5.0)
                except TimeoutError:
                    process.kill()
                    await process.wait()
                return (
                    -1,
                    "\n".join(stdout_chunks),
                    "\n".join(stderr_chunks) + f"\nTIMEOUT after {timeout}s",
                )

            # Wait for stream readers to complete
            await asyncio.gather(stdout_task, stderr_task, return_exceptions=True)

            return returncode, "\n".join(stdout_chunks), "\n".join(stderr_chunks)

        except asyncio.CancelledError:
            raise
        except Exception as e:
            LOG.error("Subprocess execution failed: %s", e)
            return (
                -1,
                "\n".join(stdout_chunks),
                "\n".join(stderr_chunks) + f"\nEXCEPTION: {e}",
            )
        finally:
            self._running_tasks.pop(attempt_id, None)

    async def execute_experiment(
        self,
        config_path: str,
        mission_id: str | None = None,
        hypothesis_id: str | None = None,
        attempt_id: str | None = None,
        run_id: str | None = None,
        force: bool = False,
        timeout: float | None = None,
        cancellation_event: asyncio.Event | None = None,
    ) -> ExecutionResult:
        """
        Execute an ML sandbox training run.

        Args:
            config_path: Path to the run config JSON (relative to repo root or absolute)
            mission_id: Optional mission ID for tracking
            hypothesis_id: Optional hypothesis ID for tracking
            attempt_id: Optional custom attempt ID (generated if not provided)
            run_id: Optional custom run ID for artifact directory (generated if not provided)
            force: Allow overwriting non-empty output directory
            timeout: Optional custom timeout in seconds
            cancellation_event: Optional event for cooperative cancellation

        Returns:
            ExecutionResult with outcome details
        """
        attempt_id = attempt_id or f"attempt_{uuid.uuid4().hex[:12]}"
        run_id = run_id or f"run_{uuid.uuid4().hex[:12]}"
        start_time = time.perf_counter()

        # Resolve paths
        config_path_obj = Path(config_path)
        if not config_path_obj.is_absolute():
            config_path_obj = (self.repo_root / config_path).resolve()

        if not config_path_obj.exists():
            return ExecutionResult(
                success=False,
                attempt_id=attempt_id,
                error_type="config_not_found",
                error_message=f"Config file not found: {config_path}",
                duration_seconds=time.perf_counter() - start_time,
            )

        out_dir = self.artifacts_dir / run_id

        # Build command
        cmd = [
            sys.executable,
            "-m",
            "ml_sandbox.train",
            "--config",
            str(config_path_obj),
            "--out",
            str(out_dir),
        ]
        if force:
            cmd.append("--force")

        LOG.info(
            "Executing experiment: attempt=%s, run=%s, config=%s",
            attempt_id,
            run_id,
            config_path,
        )

        # Record attempt start in database
        try:
            with session_scope() as session:
                record_attempt_start(
                    session,
                    attempt_id=attempt_id,
                    mission_id=mission_id,
                    hypothesis_id=hypothesis_id,
                    config_path=str(config_path_obj),
                )
        except Exception as e:
            LOG.error("Failed to record attempt start: %s", e)
            return ExecutionResult(
                success=False,
                attempt_id=attempt_id,
                error_type="db_error",
                error_message=f"Failed to record attempt start: {e}",
                duration_seconds=time.perf_counter() - start_time,
            )

        # Run subprocess
        try:
            returncode, stdout, stderr = await self._run_subprocess(
                cmd=cmd,
                cwd=self.backend_dir,
                attempt_id=attempt_id,
                mission_id=mission_id,
                timeout=timeout,
                cancellation_event=cancellation_event,
            )
        except asyncio.CancelledError:
            # Record cancellation in database
            duration = time.perf_counter() - start_time
            try:
                with session_scope() as session:
                    record_attempt_completion(
                        session,
                        attempt_id=attempt_id,
                        execution_status=ExecutionStatus.CANCELLED,
                        error_type="cancelled",
                        error_message="Execution was cancelled",
                        duration_seconds=duration,
                    )
            except Exception as e:
                LOG.error("Failed to record cancelled attempt: %s", e)
            raise

        duration = time.perf_counter() - start_time
        stdout_tail = stdout[-500:] if len(stdout) > 500 else stdout
        stderr_tail = stderr[-500:] if len(stderr) > 500 else stderr

        # Parse result
        if returncode != 0:
            # Execution failed
            error_type = "execution_failed"
            error_message = f"Process exited with code {returncode}"
            if "TIMEOUT" in stderr:
                error_type = "timeout"
                error_message = (
                    f"Execution timed out after {timeout or self.default_timeout}s"
                )
            elif (
                "CancelledError" in stderr
                or cancellation_event
                and cancellation_event.is_set()
            ):
                error_type = "cancelled"
                error_message = "Execution was cancelled"

            try:
                with session_scope() as session:
                    record_attempt_completion(
                        session,
                        attempt_id=attempt_id,
                        execution_status=(
                            ExecutionStatus.FAILED
                            if error_type != "cancelled"
                            else ExecutionStatus.CANCELLED
                        ),
                        error_type=error_type,
                        error_message=error_message,
                        stderr_tail=stderr_tail,
                        stdout_tail=stdout_tail,
                        duration_seconds=duration,
                    )
            except Exception as e:
                LOG.error("Failed to record attempt completion: %s", e)

            return ExecutionResult(
                success=False,
                attempt_id=attempt_id,
                error_type=error_type,
                error_message=error_message,
                stdout_tail=stdout_tail,
                stderr_tail=stderr_tail,
                duration_seconds=duration,
            )

        # Parse JSON result from stdout (last line)
        try:
            stdout_lines = stdout.strip().splitlines()
            if not stdout_lines:
                raise ValueError("No output from process")

            summary_line = stdout_lines[-1].strip()
            summary = json.loads(summary_line)

            if not summary.get("ok", False):
                error_msg = summary.get("error", "Unknown error")
                try:
                    with session_scope() as session:
                        record_attempt_completion(
                            session,
                            attempt_id=attempt_id,
                            execution_status=ExecutionStatus.FAILED,
                            error_type="ml_error",
                            error_message=error_msg,
                            stderr_tail=stderr_tail,
                            stdout_tail=stdout_tail,
                            duration_seconds=duration,
                        )
                except Exception as e:
                    LOG.error("Failed to record attempt completion: %s", e)

                return ExecutionResult(
                    success=False,
                    attempt_id=attempt_id,
                    error_type="ml_error",
                    error_message=error_msg,
                    stdout_tail=stdout_tail,
                    stderr_tail=stderr_tail,
                    duration_seconds=duration,
                )

            # Success - load run_record.json
            artifact_rel = summary.get("artifact", "")
            run_record_path = self.repo_root / artifact_rel / "run_record.json"

            if not run_record_path.exists():
                error_msg = f"run_record.json not found at {run_record_path}"
                try:
                    with session_scope() as session:
                        record_attempt_completion(
                            session,
                            attempt_id=attempt_id,
                            execution_status=ExecutionStatus.FAILED,
                            error_type="missing_artifact",
                            error_message=error_msg,
                            stderr_tail=stderr_tail,
                            stdout_tail=stdout_tail,
                            duration_seconds=duration,
                        )
                except Exception as e:
                    LOG.error("Failed to record attempt completion: %s", e)

                return ExecutionResult(
                    success=False,
                    attempt_id=attempt_id,
                    error_type="missing_artifact",
                    error_message=error_msg,
                    stdout_tail=stdout_tail,
                    stderr_tail=stderr_tail,
                    duration_seconds=duration,
                )

            run_record = json.loads(run_record_path.read_text())

            # Broadcast run metrics to WebSocket
            if mission_id:
                ws_manager = get_ws_manager()
                try:
                    await ws_manager.broadcast_run_metrics(
                        mission_id=mission_id,
                        run_id=run_record.get("id", ""),
                        metrics=run_record.get("metrics", {}),
                    )
                except Exception as e:
                    LOG.warning("WebSocket metrics broadcast failed: %s", e)

            # Record successful completion (without experiment_id - will be set by execute_and_register)
            config_hash = summary.get("config_hash", "")
            try:
                with session_scope() as session:
                    record_attempt_completion(
                        session,
                        attempt_id=attempt_id,
                        execution_status=ExecutionStatus.COMPLETED,
                        config_hash=config_hash,
                        artifact_path=artifact_rel,
                        stderr_tail=stderr_tail,
                        stdout_tail=stdout_tail,
                        duration_seconds=duration,
                    )
            except Exception as e:
                LOG.error("Failed to record attempt completion: %s", e)

            return ExecutionResult(
                success=True,
                experiment_id=run_record.get("id"),
                attempt_id=attempt_id,
                run_record=run_record,
                stdout_tail=stdout_tail,
                stderr_tail=stderr_tail,
                duration_seconds=duration,
            )

        except (json.JSONDecodeError, ValueError, IndexError) as e:
            error_msg = f"Failed to parse execution output: {e}"
            LOG.error("%s\nStdout: %s", error_msg, stdout[-1000:])

            try:
                with session_scope() as session:
                    record_attempt_completion(
                        session,
                        attempt_id=attempt_id,
                        execution_status=ExecutionStatus.FAILED,
                        error_type="parse_error",
                        error_message=error_msg,
                        stderr_tail=stderr_tail,
                        stdout_tail=stdout_tail,
                        duration_seconds=duration,
                    )
            except Exception as e:
                LOG.error("Failed to record attempt completion: %s", e)

            return ExecutionResult(
                success=False,
                attempt_id=attempt_id,
                error_type="parse_error",
                error_message=error_msg,
                stdout_tail=stdout_tail,
                stderr_tail=stderr_tail,
                duration_seconds=duration,
            )

    async def execute_and_register(
        self,
        config_path: str,
        mission_id: str | None = None,
        hypothesis_id: str | None = None,
        run_id: str | None = None,
        force: bool = False,
        timeout: float | None = None,
        cancellation_event: asyncio.Event | None = None,
    ) -> ExecutionResult:
        """
        Execute an experiment and register it in the registry if successful.

        This is the high-level method that connects execution to the experiment registry.
        """
        result = await self.execute_experiment(
            config_path=config_path,
            mission_id=mission_id,
            hypothesis_id=hypothesis_id,
            run_id=run_id,
            force=force,
            timeout=timeout,
            cancellation_event=cancellation_event,
        )

        if not result.success or not result.run_record:
            return result

        # Register the experiment in the scientific registry
        try:
            with session_scope() as session:
                experiment = insert_experiment(session, result.run_record)
                session.commit()

                # Link attempt to experiment
                attempt = session.get(ExperimentAttempt, result.attempt_id)
                if attempt:
                    attempt.experiment_id = experiment.id
                    session.add(attempt)
                    session.commit()

                result.experiment_id = experiment.id
                LOG.info("Registered experiment: %s", experiment.id)

        except Exception as e:
            LOG.error("Failed to register experiment: %s", e)
            result.success = False
            result.error_type = "registration_failed"
            result.error_message = f"Failed to register experiment: {e}"

        return result


# Global execution service instance
_execution_service: MLExecutionService | None = None


def get_execution_service() -> MLExecutionService:
    """Get the global execution service instance."""
    global _execution_service
    if _execution_service is None:
        # Determine repo root from backend location
        backend_dir = Path(__file__).resolve().parents[2]
        repo_root = backend_dir.parent
        _execution_service = MLExecutionService(repo_root=repo_root)
    return _execution_service


async def init_execution_service() -> MLExecutionService:
    """Initialize the global execution service."""
    service = get_execution_service()
    await service.start()
    return service


async def shutdown_execution_service():
    """Shutdown the global execution service."""
    global _execution_service
    if _execution_service:
        await _execution_service.stop()
        _execution_service = None
