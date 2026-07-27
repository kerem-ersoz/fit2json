"""Tests for the filesystem memory corpus."""


from fit2json.memory import MemoryStore, activity_id
from fit2json.models import DecodedActivity


def _activity(sport="running", start="2024-03-10T07:30:00+00:00", source="run.fit", distance=10000.0):
    return DecodedActivity(
        source_file=source,
        messages={
            "session": [{
                "sport": sport,
                "start_time": start,
                "total_distance": distance,
                "total_timer_time": 3000.0,
                "avg_heart_rate": 150,
            }],
        },
    )


class TestRecord:
    def test_writes_file_and_index(self, tmp_path):
        store = MemoryStore(tmp_path)
        path = store.record(_activity(), "How was it?", "Great run.", backend="ollama", model="llama3.1")
        assert path.exists()
        assert path.parent.name == "running"
        entries = store.load_index()
        assert len(entries) == 1
        assert entries[0]["sport"] == "running"
        assert entries[0]["metrics"]["distance_m"] == 10000.0

    def test_frontmatter_and_body(self, tmp_path):
        store = MemoryStore(tmp_path)
        path = store.record(_activity(), "Pacing?", "Even splits throughout.")
        text = path.read_text()
        assert text.startswith("---")
        assert "sport: running" in text
        assert "Even splits throughout." in text

    def test_multiple_prompts_same_workout_are_distinct(self, tmp_path):
        store = MemoryStore(tmp_path)
        a = _activity()
        p1 = store.record(a, "Prompt one", "A")
        p2 = store.record(a, "Prompt two", "B")
        assert p1 != p2
        assert len(store.load_index()) == 2

    def test_activity_id_stable(self):
        a = _activity()
        assert activity_id(a) == activity_id(_activity())


class TestRecall:
    def _seed(self, tmp_path):
        store = MemoryStore(tmp_path)
        store.record(_activity("running", "2024-03-10T07:00:00+00:00", "r1.fit"), "p", "run analysis")
        store.record(_activity("cycling", "2024-03-11T07:00:00+00:00", "c1.fit", 40000.0), "p", "bike analysis")
        return store

    def test_mode_none_returns_empty(self, tmp_path):
        store = self._seed(tmp_path)
        assert store.recall(sport="running", mode="none") == []

    def test_same_sport_filters(self, tmp_path):
        store = self._seed(tmp_path)
        got = store.recall(sport="running", mode="same-sport")
        assert [e["sport"] for e in got] == ["running"]

    def test_all_returns_everything(self, tmp_path):
        store = self._seed(tmp_path)
        assert len(store.recall(mode="all")) == 2

    def test_auto_prioritizes_same_sport(self, tmp_path):
        store = self._seed(tmp_path)
        got = store.recall(sport="cycling", mode="auto")
        assert got[0]["sport"] == "cycling"

    def test_limit(self, tmp_path):
        store = self._seed(tmp_path)
        assert len(store.recall(mode="all", limit=1)) == 1

    def test_digest_and_read_entry(self, tmp_path):
        store = self._seed(tmp_path)
        entries = store.recall(mode="all")
        digest = store.digest(entries)
        assert "running" in digest and "cycling" in digest
        content = store.read_entry(entries[0]["entry_id"])
        assert content is not None
