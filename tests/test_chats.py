"""Tests for the persisted chat-session store."""

from fit2json.chats import ChatStore, sanitize_id


def _msgs(*pairs):
    return [{"id": f"m{i}", "role": r, "content": c} for i, (r, c) in enumerate(pairs, 1)]


class TestSave:
    def test_creates_file_and_returns_doc(self, tmp_path):
        store = ChatStore(tmp_path)
        doc = store.save("chat-1", {"messages": _msgs(("user", "How was my run?"))})
        assert (tmp_path / "chat-1.json").exists()
        assert doc["id"] == "chat-1"
        assert doc["created_at"] and doc["updated_at"]
        assert doc["messages"][0]["content"] == "How was my run?"

    def test_title_derived_from_first_user_message(self, tmp_path):
        store = ChatStore(tmp_path)
        doc = store.save("c", {"messages": _msgs(("user", "Compare my long runs"))})
        assert doc["title"] == "Compare my long runs"

    def test_explicit_title_wins(self, tmp_path):
        store = ChatStore(tmp_path)
        doc = store.save("c", {"title": "Weekly review", "messages": _msgs(("user", "hi"))})
        assert doc["title"] == "Weekly review"

    def test_long_title_is_truncated(self, tmp_path):
        store = ChatStore(tmp_path)
        doc = store.save("c", {"messages": _msgs(("user", "x" * 200))})
        assert doc["title"].endswith("…")
        assert len(doc["title"]) <= 82

    def test_update_preserves_created_at(self, tmp_path):
        store = ChatStore(tmp_path)
        first = store.save("c", {"messages": _msgs(("user", "hi"))})
        second = store.save("c", {"messages": _msgs(("user", "hi"), ("assistant", "hello"))})
        assert second["created_at"] == first["created_at"]
        assert len(second["messages"]) == 2

    def test_unknown_roles_dropped(self, tmp_path):
        store = ChatStore(tmp_path)
        doc = store.save("c", {"messages": [{"id": "x", "role": "system", "content": "nope"}]})
        assert doc["messages"] == []

    def test_persists_settings_and_activity_ids(self, tmp_path):
        store = ChatStore(tmp_path)
        doc = store.save(
            "c",
            {
                "backend": "ollama",
                "model": "llama3.1",
                "reasoning_effort": "high",
                "activity_ids": ["a1", "a2"],
                "messages": _msgs(("user", "hi")),
            },
        )
        assert doc["backend"] == "ollama"
        assert doc["model"] == "llama3.1"
        assert doc["reasoning_effort"] == "high"
        assert doc["activity_ids"] == ["a1", "a2"]


class TestListGetDelete:
    def test_list_is_newest_first_without_bodies(self, tmp_path):
        import json

        store = ChatStore(tmp_path)
        store.save("old", {"messages": _msgs(("user", "first"))})
        # Backdate "old" so ordering by updated_at is deterministic.
        old_doc = store.get("old")
        old_doc["updated_at"] = "2000-01-01T00:00:00+00:00"
        (tmp_path / "old.json").write_text(json.dumps(old_doc), encoding="utf-8")

        store.save("new", {"messages": _msgs(("user", "second"), ("assistant", "ok"))})

        listed = store.list()
        assert [s["id"] for s in listed] == ["new", "old"]
        assert listed[0]["message_count"] == 2
        assert "messages" not in listed[0]

    def test_get_missing_returns_none(self, tmp_path):
        assert ChatStore(tmp_path).get("nope") is None

    def test_delete(self, tmp_path):
        store = ChatStore(tmp_path)
        store.save("c", {"messages": _msgs(("user", "hi"))})
        assert store.delete("c") is True
        assert store.get("c") is None
        assert store.delete("c") is False

    def test_list_skips_corrupt_files(self, tmp_path):
        store = ChatStore(tmp_path)
        store.save("good", {"messages": _msgs(("user", "hi"))})
        (tmp_path / "broken.json").write_text("{not json", encoding="utf-8")
        assert [s["id"] for s in store.list()] == ["good"]


class TestSanitizeId:
    def test_strips_path_traversal(self):
        assert "/" not in sanitize_id("../../etc/passwd")
        assert ".." not in sanitize_id("..")

    def test_empty_falls_back(self):
        assert sanitize_id("") == "chat"
        assert sanitize_id("///") == "chat"

    def test_keeps_safe_chars(self):
        assert sanitize_id("chat_2024-01-01.abc") == "chat_2024-01-01.abc"

