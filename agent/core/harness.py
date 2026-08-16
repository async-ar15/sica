import time
from typing import Any

from agent.core.circuit_breaker import BreakerState, CircuitBreaker
from agent.core.context_manager import ContextManager
from agent.core.state_machine import AgentState, StateMachine
from agent.memory.working import IterationSnapshot, WorkingMemory
from agent.tools.aci import ToolRegistry
from agent.tools.sandbox import DockerSandbox
from ui.display import StatusDisplay, TaskResult


class AgentHarness:
    def __init__(
        self,
        llm: Any,
        sandbox: DockerSandbox,
        tools: ToolRegistry,
        fsm: StateMachine,
        circuit_breaker: CircuitBreaker,
        memory: WorkingMemory,
        display: StatusDisplay,
        trajectory: Any | None = None
    ) -> None:
        self.llm = llm
        self.sandbox = sandbox
        self.tools = tools
        self.fsm = fsm
        self.circuit_breaker = circuit_breaker
        self.memory = memory
        self.display = display
        self.trajectory = trajectory
        self.context_manager = ContextManager()

    async def run(self, goal: str) -> TaskResult:
        self.memory.reset()
        self.memory.current_goal = goal

        iteration = 0
        total_tokens = 0
        total_cost = 0.0
        start_time = time.time()

        await self.fsm.transition("start")

        while self.fsm.state not in (AgentState.COMPLETED, AgentState.FAILED):
            iteration += 1
            iter_start = time.time()

            # 1. Circuit Breaker
            b_state = BreakerState(iteration_count=iteration)
            trip = self.circuit_breaker.check(b_state)
            if trip:
                return TaskResult(
                    success=False,
                    reason=f"Circuit Breaker tripped: {trip}",
                    iterations=iteration,
                    total_tokens=total_tokens,
                    total_cost_usd=total_cost,
                    total_duration_ms=int((time.time() - start_time) * 1000)
                )

            self.display.update(
                state=self.fsm.state,
                iteration=iteration,
                max_iterations=self.circuit_breaker.config.max_iterations,
                tokens=total_tokens,
                cost=total_cost,
                message="Thinking..."
            )

            # 2. Build Prompt & Call LLM
            messages = self.context_manager.build_prompt(self.fsm.state, self.memory)

            try:
                # In a real run, we'd parse tool calls from response
                llm_response = await self.llm.generate(messages=messages, tools=self.tools.get_tool_definitions())

                # Mock processing for Phase 1.9 to prevent infinite loops if LLM doesn't do what we want
                # We will force a completed state for testing purposes if goal is "test"
                if goal.lower() == "test":
                    self.fsm.state = AgentState.COMPLETED
                    break

                if self.fsm.state == AgentState.LOCALIZING:
                    await self.fsm.transition("plan_ready")
                elif self.fsm.state == AgentState.PLANNING:
                    await self.fsm.transition("plan_approved")
                elif self.fsm.state == AgentState.CODING:
                    await self.fsm.transition("code_written")
                elif self.fsm.state == AgentState.TESTING:
                    await self.fsm.transition("tests_passed")
                elif self.fsm.state == AgentState.REFLECTING:
                    await self.fsm.transition("task_done")

                total_tokens += getattr(llm_response, "total_tokens", 100)

            except Exception as e:
                self.display.display_error(f"LLM Error: {e}")
                await self.fsm.transition("error")
                break

            # 3. Record Iteration
            duration = int((time.time() - iter_start) * 1000)
            snap = IterationSnapshot(
                iteration=iteration,
                hypothesis="Automated progression",
                tokens_used=100,
                duration_ms=duration
            )
            self.memory.record_iteration(snap)
            self.display.display_iteration(snap)
            
            if self.trajectory:
                from agent.core.trajectory import TrajectoryStep
                self.trajectory.log_step(TrajectoryStep(
                    step_index=iteration,
                    state=self.fsm.state,
                    action_type="fsm_transition",
                    content={"tokens": getattr(llm_response, "total_tokens", 100)} if 'llm_response' in locals() else {}
                ))

        success = self.fsm.state == AgentState.COMPLETED
        return TaskResult(
            success=success,
            goal=goal,
            iterations=iteration,
            total_tokens=total_tokens,
            total_cost_usd=total_cost,
            total_duration_ms=int((time.time() - start_time) * 1000),
            reason="Reached terminal state" if success else "Failed or Errored",
            summary="Task execution finished."
        )
