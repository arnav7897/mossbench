"""Bounded Moss Tasks API smoke workflow."""

from moss import MossInference


class TasksClient:
    def __init__(self, project_id, project_key):
        self.client = MossInference(project_id, project_key)

    async def run_smoke(self, goal, model="moss-fast", max_cost_usd=0.25):
        task = await self.client.tasks.create(
            goal=goal,
            environment={"type": "browser", "start_url": "https://docs.python.org/3/"},
            model=model,
            effort="low",
            limits={"max_runtime_seconds": 60, "max_cost_usd": max_cost_usd},
        )
        return task, await self.client.tasks.wait(task.id, timeout=120, poll_interval=2)

    async def submit(self, goal, start_url, model="moss-fast", max_runtime_seconds=60,
                     max_cost_usd=0.25, output_schema=None):
        if not isinstance(max_runtime_seconds, int) or isinstance(max_runtime_seconds, bool) or not 60 <= max_runtime_seconds <= 7200:
            raise ValueError("max_runtime_seconds must be an integer from 60 to 7200")
        if not isinstance(max_cost_usd, (int, float)) or isinstance(max_cost_usd, bool) or not 0 < max_cost_usd <= 0.25:
            raise ValueError("max_cost_usd must be greater than 0 and at most 0.25")
        return await self.client.tasks.create(
            goal=goal, environment={"type": "browser", "start_url": start_url},
            model=model, effort="low", output_schema=output_schema,
            limits={"max_runtime_seconds": max_runtime_seconds, "max_cost_usd": max_cost_usd},
        )

    async def retrieve(self, task_id):
        return await self.client.tasks.retrieve(task_id)

    async def cancel(self, task_id):
        return await self.client.tasks.cancel(task_id)

    async def wait(self, task_id, timeout=120):
        return await self.client.tasks.wait(task_id, timeout=timeout, poll_interval=2)

    async def close(self):
        await self.client.close()
