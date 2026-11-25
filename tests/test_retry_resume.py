import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
from moss import MossInference
from moss.inference import Task

from mossbench.clients.tasks import TasksClient
from mossbench.state import Ledger


COMPLETED_EVENT = {
    "type": "response.completed",
    "response": {
        "id": "resp_mock", "status": "completed", "model": "moss-fastlane",
        "output": [{"type": "message", "content": [{"type": "output_text", "text": "OK"}]}],
        "usage": {"input_tokens": 2, "output_tokens": 1, "total_tokens": 3},
    },
}


class RetryAndResumeTests(unittest.IsolatedAsyncioTestCase):
    async def test_responses_retries_429_after_retry_after_and_completes(self):
        calls = []

        async def handler(request):
            calls.append(request)
            if len(calls) == 1:
                return httpx.Response(
                    429,
                    headers={"Retry-After": "0"},
                    json={"error": {"type": "rate_limit_error", "code": "rate_limit_exceeded", "message": "retry"}},
                )
            body = f"data: {json.dumps(COMPLETED_EVENT)}\n\n".encode()
            return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=body)

        client = MossInference("project", "key", max_retries=1)
        transport = httpx.MockTransport(handler)
        client._state = (asyncio.get_running_loop(), httpx.AsyncClient(transport=transport))
        try:
            with patch("moss.inference.asyncio.sleep", new_callable=AsyncMock) as sleep:
                response = await client.responses.create(
                    model="moss-fastlane", input="Say OK", retrieve=False, cache=False,
                    max_retries=1,
                )
            self.assertEqual(len(calls), 2)
            self.assertEqual(response.output_text, "OK")
            self.assertEqual(response.status, "completed")
            sleep.assert_awaited_once_with(0.0)
        finally:
            await client.close()

    async def test_retry_disabled_returns_rate_limit_without_replay(self):
        calls = []

        async def handler(request):
            calls.append(request)
            return httpx.Response(
                429,
                json={"error": {"type": "rate_limit_error", "code": "rate_limit_exceeded", "message": "limited"}},
            )

        client = MossInference("project", "key", max_retries=0)
        client._state = (asyncio.get_running_loop(), httpx.AsyncClient(transport=httpx.MockTransport(handler)))
        try:
            with self.assertRaises(Exception) as caught:
                await client.responses.create(
                    model="moss-fastlane", input="Say OK", retrieve=False, cache=False,
                    max_retries=0,
                )
            self.assertEqual(len(calls), 1)
            self.assertEqual(getattr(caught.exception, "code", None), "rate_limit_exceeded")
        finally:
            await client.close()

    async def test_truncated_stream_is_reported_as_incomplete(self):
        first_event = {"type": "response.created", "response": {"id": "resp_partial", "status": "in_progress"}}
        body = f"data: {json.dumps(first_event)}\n\n".encode()

        async def handler(request):
            return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=body)

        client = MossInference("project", "key", max_retries=0)
        client._state = (asyncio.get_running_loop(), httpx.AsyncClient(transport=httpx.MockTransport(handler)))
        try:
            stream = await client.responses.create(
                model="moss-fastlane", input="Say OK", stream=True,
                retrieve=False, cache=False, max_retries=0,
            )
            with self.assertRaises(Exception) as caught:
                async for _ in stream:
                    pass
            self.assertEqual(getattr(caught.exception, "type", None), "incomplete_stream")
        finally:
            await client.close()

    async def test_wait_resumes_same_task_id_without_creating_another(self):
        client = MossInference("project", "key")
        calls = []
        statuses = ["queued", "running", "completed"]

        async def retrieve(task_id, **kwargs):
            calls.append((task_id, kwargs))
            return Task(id=task_id, status=statuses.pop(0))

        client.tasks.retrieve = retrieve
        try:
            with patch("moss.inference.asyncio.sleep", new_callable=AsyncMock) as sleep:
                result = await client.tasks.wait("existing-task-123", timeout=5, poll_interval=0.01)
            self.assertEqual(result.id, "existing-task-123")
            self.assertEqual(result.status, "completed")
            self.assertEqual([task_id for task_id, _ in calls], ["existing-task-123"] * 3)
            self.assertEqual(len(calls), 3)
            self.assertEqual(sleep.await_count, 2)
        finally:
            await client.close()

    async def test_ledger_upserts_state_for_same_task_id(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = Ledger(Path(directory) / "state.sqlite3")
            try:
                ledger.save_task("existing-task-123", "running")
                ledger.save_task("existing-task-123", "completed")
                rows = ledger.db.execute("SELECT task_id,state FROM tasks").fetchall()
                self.assertEqual(rows, [("existing-task-123", "completed")])
            finally:
                ledger.db.close()

    async def test_tasks_client_wait_delegates_to_existing_task(self):
        class FakeTasks:
            def __init__(self):
                self.wait_args = None
                self.create_called = False

            async def wait(self, task_id, **kwargs):
                self.wait_args = (task_id, kwargs)
                return Task(id=task_id, status="completed")

            async def create(self, **kwargs):
                self.create_called = True
                raise AssertionError("resume must not submit a new task")

        class FakeClient:
            def __init__(self):
                self.tasks = FakeTasks()

        wrapper = TasksClient.__new__(TasksClient)
        wrapper.client = FakeClient()
        result = await wrapper.wait("existing-task-123", timeout=9)
        self.assertEqual(result.id, "existing-task-123")
        self.assertEqual(wrapper.client.tasks.wait_args, ("existing-task-123", {"timeout": 9, "poll_interval": 2}))
        self.assertFalse(wrapper.client.tasks.create_called)


if __name__ == "__main__":
    unittest.main()
