from agent.memory.working import ErrorSignature, IterationSnapshot, SubTask, WorkingMemory


def test_record_iteration_appends() -> None:
    wm = WorkingMemory()
    for i in range(3):
        wm.record_iteration(IterationSnapshot(iteration=i))
    assert len(wm.iteration_history) == 3

def test_deque_evicts_oldest() -> None:
    wm = WorkingMemory()
    for i in range(15):
        wm.record_iteration(IterationSnapshot(iteration=i))
    assert len(wm.iteration_history) == 10
    assert wm.iteration_history[0].iteration == 5

def test_has_tried_exact_match() -> None:
    wm = WorkingMemory()
    wm.mark_tried("fix import")
    assert wm.has_tried("fix import")

def test_has_tried_normalized() -> None:
    wm = WorkingMemory()
    wm.mark_tried("Fix Import.")
    assert wm.has_tried("fix import")
    assert wm.has_tried("FIX IMPORT!")

def test_has_tried_false_for_untried() -> None:
    wm = WorkingMemory()
    wm.mark_tried("fix import")
    assert not wm.has_tried("new thing")

def test_reset_clears_everything() -> None:
    wm = WorkingMemory()
    wm.current_goal = "goal"
    wm.record_iteration(IterationSnapshot(iteration=1))
    wm.active_errors.append(ErrorSignature(error_type="E", core_message="msg", raw_message="raw"))
    wm.mark_tried("hyp")

    wm.reset()
    assert wm.current_goal == ""
    assert len(wm.iteration_history) == 0
    assert len(wm.active_errors) == 0
    assert len(wm.tried_hypotheses) == 0

def test_to_context_string_includes_goal() -> None:
    wm = WorkingMemory()
    wm.current_goal = "fix auth bug"
    ctx = wm.to_context_string()
    assert "fix auth bug" in ctx

def test_to_context_string_includes_errors() -> None:
    wm = WorkingMemory()
    wm.active_errors.append(ErrorSignature(error_type="SyntaxError", core_message="bad syntax", raw_message=""))
    ctx = wm.to_context_string()
    assert "SyntaxError" in ctx
    assert "bad syntax" in ctx

def test_subtask_model_validates() -> None:
    st = SubTask(task_id="t1", description="desc")
    assert st.status == "pending"
    assert st.task_id == "t1"
