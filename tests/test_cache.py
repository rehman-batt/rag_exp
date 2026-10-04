from app import cache as cache_module
from app.cache import ResponseCache


def test_missing_prompt_records_a_miss():
    cache = ResponseCache()

    assert cache.get("unknown") is None
    assert cache.stats() == {"hits": 0, "misses": 1, "size": 0}


def test_set_and_get_use_case_insensitive_trimmed_keys():
    cache = ResponseCache()
    cache.set("  Hello World  ", "first answer")

    assert cache.get("hello world") == "first answer"
    assert cache.get("HELLO WORLD ") == "first answer"
    assert cache.stats() == {"hits": 2, "misses": 0, "size": 1}


def test_different_prompts_keep_separate_responses():
    cache = ResponseCache()
    cache.set("first prompt", "first answer")
    cache.set("second prompt", "second answer")

    assert cache.get("first prompt") == "first answer"
    assert cache.get("second prompt") == "second answer"
    assert cache.stats() == {"hits": 2, "misses": 0, "size": 2}


def test_setting_existing_prompt_replaces_response_and_refreshes_ttl(monkeypatch):
    now = [100.0]
    monkeypatch.setattr(cache_module.time, "time", lambda: now[0])
    cache = ResponseCache(ttl=10)

    cache.set("prompt", "old answer")
    now[0] = 105.0
    cache.set(" PROMPT ", "new answer")
    now[0] = 114.0

    assert cache.get("prompt") == "new answer"
    assert cache.stats() == {"hits": 1, "misses": 0, "size": 1}


def test_entry_expires_at_ttl_boundary_and_is_removed_on_lookup(monkeypatch):
    now = [100.0]
    monkeypatch.setattr(cache_module.time, "time", lambda: now[0])
    cache = ResponseCache(ttl=10)
    cache.set("prompt", "answer")

    now[0] = 109.9
    assert cache.get("prompt") == "answer"

    now[0] = 110.0
    assert cache.get("prompt") is None
    assert cache.stats() == {"hits": 1, "misses": 1, "size": 0}


def test_cache_instances_do_not_share_entries_or_counters():
    first = ResponseCache()
    second = ResponseCache()
    first.set("prompt", "answer")

    assert second.get("prompt") is None
    assert first.stats() == {"hits": 0, "misses": 0, "size": 1}
    assert second.stats() == {"hits": 0, "misses": 1, "size": 0}
