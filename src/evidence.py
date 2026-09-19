"""Application-owned image files and durable pending server predictions."""
import hashlib
import json
import os
from pathlib import Path
import shutil
from uuid import UUID, uuid4
from src.inference.config import ROOT
from src.inference.results import Prediction


class EvidenceError(ValueError):
    def __init__(self, message, status_code=409):
        super().__init__(message)
        self.status_code = status_code


class EvidenceFiles:
    def __init__(self, root=None):
        path = Path(root if root is not None else os.environ.get('SCAN_STORAGE_DIR', 'data/scans'))
        self.root = (ROOT / path).resolve()

    def directory(self, id, pending=False):
        parent = self.root / '.pending' if pending else self.root
        path = parent / str(UUID(str(id)))
        # Resolve before any recursive cleanup or read: symlinks cannot escape the owner directory.
        if path.resolve().parent != parent.resolve() or not path.resolve().is_relative_to(self.root):
            raise EvidenceError('Invalid evidence location')
        return path

    def cleanup(self, id, pending=False):
        path = self.directory(id, pending)
        if path.exists():
            shutil.rmtree(path)  # Only a checked, application-generated UUID directory.

    def stage(self, original, annotated, prediction):
        id = uuid4()
        directory = self.directory(id, pending=True)
        directory.mkdir(parents=True, exist_ok=False)
        # Input has already passed JPEG/PNG validation. Preserve its exact bytes.
        filename = 'original.png' if original.startswith(b'\x89PNG\r\n\x1a\n') else 'original.jpg'
        try:
            (directory / filename).write_bytes(original)
            (directory / 'annotated.jpg').write_bytes(annotated)
            manifest = {'original': filename, 'source_sha256': hashlib.sha256(original).hexdigest(),
                        'annotated_sha256': hashlib.sha256(annotated).hexdigest(),
                        'prediction': prediction.model_dump(mode='json')}
            (directory / 'prediction.json').write_text(json.dumps(manifest), encoding='utf-8')
        except Exception:
            self.cleanup(id, pending=True)
            raise
        return id

    def read(self, id):
        directory = self.directory(id, pending=True)
        try:
            manifest = json.loads((directory / 'prediction.json').read_text(encoding='utf-8'))
            if manifest['original'] not in {'original.jpg', 'original.png'}:
                raise EvidenceError('Invalid pending image format')
            for name, digest in [(manifest['original'], manifest['source_sha256']),
                                 ('annotated.jpg', manifest['annotated_sha256'])]:
                path = directory / name
                if path.resolve().parent != directory.resolve():
                    raise EvidenceError('Invalid evidence location')
                if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                    raise EvidenceError('Pending evidence is damaged; scan the photo again')
            prediction = Prediction.model_validate(manifest['prediction'])
        except (OSError, KeyError, ValueError) as e:
            if isinstance(e, EvidenceError):
                raise
            raise EvidenceError('Prediction evidence is unavailable; scan the photo again', 404) from e
        return manifest, prediction

    def publish(self, prediction_id, scan_id, manifest):
        source = self.directory(prediction_id, pending=True)
        target = self.directory(scan_id)
        target.mkdir(parents=True, exist_ok=False)
        try:
            for name in [manifest['original'], 'annotated.jpg']:
                shutil.copyfile(source / name, target / name)
        except Exception:
            self.cleanup(scan_id)
            raise
        return f'{scan_id}/{manifest["original"]}', f'{scan_id}/annotated.jpg'

    def image(self, scan_id, reference, kind):
        # DB references must be the exact managed name, even if the DB is manually corrupted.
        names = ['original.jpg', 'original.png'] if kind == 'original' else ['annotated.jpg']
        if reference not in {f'{scan_id}/{name}' for name in names}:
            return None
        directory = self.directory(scan_id)
        path = self.root / reference
        if path.resolve().parent != directory.resolve() or not path.is_file():
            return None
        return path
