from app.memory.long_term_memory import LongTermMemory


def test_long_term_memory_persists_between_instances(tmp_path):
    storage = tmp_path / "memory.json"
    memory = LongTermMemory(storage)
    memory.remember(
        "Vikas prefers concise answers.",
        importance=0.9,
        metadata={"topic": "preferences"},
    )

    reloaded = LongTermMemory(storage)

    assert len(reloaded.records) == 1
    record = next(iter(reloaded.records.values()))
    assert record.content == "Vikas prefers concise answers."
    assert record.importance == 0.9


def test_long_term_memory_search_ranks_importance(tmp_path):
    memory = LongTermMemory(tmp_path / "memory.json")
    memory.remember(
        "Python is useful",
        importance=0.2,
    )
    memory.remember(
        "Python user preferences",
        importance=0.9,
    )

    matches = memory.search(
        "Python preferences",
        limit=1,
    )

    assert len(matches) == 1
    assert matches[0][0].importance == 0.9


def test_long_term_memory_forget_and_prune(tmp_path):
    memory = LongTermMemory(tmp_path / "memory.json")
    low = memory.remember(
        "Temporary fact",
        importance=0.1,
    )
    high = memory.remember(
        "Important preference",
        importance=0.8,
    )

    assert memory.forget(low.id) is True
    assert memory.forget(low.id) is False

    memory.remember(
        "Low priority fact",
        importance=0.0,
    )
    assert memory.prune(max_importance=0.0) == 1
    assert high.id in memory.records


def test_long_term_memory_summarizes_highest_priority(tmp_path):
    memory = LongTermMemory(tmp_path / "memory.json")
    memory.remember("A low priority fact", importance=0.1)
    memory.remember("A high priority preference", importance=0.9)

    summary = memory.summarize()

    assert "A high priority preference" in summary
