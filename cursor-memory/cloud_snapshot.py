"""One private, atomically replaced GCS publication object."""
import json


class CloudSnapshot:
    def __init__(self, bucket, name):
        from google.cloud import storage
        self.bucket = storage.Client().bucket(bucket)
        self.name = name

    def load(self):
        blob = self.bucket.blob(self.name)
        blob.reload(timeout=5)
        generation = str(blob.generation)
        if blob.size is None or blob.size > 8_000_000:
            raise ValueError("Publication object exceeds its size limit.")
        raw = blob.download_as_bytes(if_generation_match=int(generation), timeout=10)
        return json.loads(raw), generation

    def replace(self, data, generation):
        from google.api_core.exceptions import PreconditionFailed
        blob = self.bucket.blob(self.name)
        raw = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        try:
            blob.upload_from_string(raw, content_type="application/json", if_generation_match=int(generation), timeout=10)
        except PreconditionFailed as error:
            raise ValueError("Publication changed concurrently.") from error
        return str(blob.generation)
