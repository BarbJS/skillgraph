from src.progress_ui import ResumeProgress


def test_progress_starts_and_finishes(monkeypatch):
    class Status:
        def __init__(self):
            self.updates = []

        def update(self, **kwargs):
            self.updates.append(kwargs)

        def write(self, value):
            self.updates.append({"write": value})

    status = Status()
    import src.progress_ui as module

    monkeypatch.setattr(module.st, "status", lambda *args, **kwargs: status)
    progress = ResumeProgress.start()
    progress.update("ocr", "OCR", "extração")
    progress.finish(True)
    assert any(
        item.get("state") == "complete" for item in status.updates if "state" in item
    )
    assert any("OCR" in item.get("write", "") for item in status.updates)
