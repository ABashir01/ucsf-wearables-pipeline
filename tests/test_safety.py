from pathlib import Path

from box_wearable_pipeline.state import save_state


class FakeBox:
    def __init__(self):
        self.calls = []

    def upload_file(self, folder_id, path, name):
        self.calls.append(("upload_file", folder_id, Path(path).name, name))
        return object()

    def upload_new_file_version(self, file_id, path, name):
        self.calls.append(("upload_new_file_version", file_id, Path(path).name, name))
        return object()


def test_state_save_only_uses_upload_methods(tmp_path):
    box = FakeBox()
    save_state(box, "control-folder", None, {"completed_fingerprints": {}}, tmp_path)
    assert box.calls == [("upload_file", "control-folder", "pipeline_state.json", "pipeline_state.json")]
