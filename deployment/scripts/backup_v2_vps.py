"""Keep a private PostgreSQL snapshot and prove it restores in an isolated database."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from uuid import uuid4


def main():
    root = Path(__file__).resolve().parents[2]
    if root != Path('/opt/marketfusion'):
        raise SystemExit('Expected the dedicated /opt/marketfusion checkout')
    os.umask(0o077)
    compose = ['docker', 'compose', '-f', 'docker-compose.yml', '-f', 'docker-compose.browser.yml']

    def run(args, **kwargs):
        return subprocess.run(args, cwd=root, check=True, **kwargs)

    def db(*args, **kwargs):
        return run(compose + ['exec', '-T', 'db', *args], **kwargs)

    backup_root = Path('/var/backups/marketfusion')
    backup_root.mkdir(mode=0o700, exist_ok=True)
    if backup_root.stat().st_mode & 0o077:
        raise SystemExit('Backup directory must be private')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    folder = Path(tempfile.mkdtemp(prefix=stamp + '-', dir=backup_root))
    dump = folder / 'marketfusion.dump'
    with dump.open('xb') as file:
        db('pg_dump', '-U', 'marketfusion', '-d', 'marketfusion', '-Fc', stdout=file)
    shutil.copyfile(root / '.env', folder / '.env')
    revision = run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
    image_ids = run(compose + ['images', '--quiet'], capture_output=True, text=True).stdout.splitlines()
    scratch = 'mf_restore_' + uuid4().hex
    db('createdb', '-U', 'marketfusion', scratch)
    try:
        with dump.open('rb') as file:
            db('pg_restore', '--exit-on-error', '--no-owner', '-U', 'marketfusion', '-d', scratch, stdin=file)
        counts = db('psql', '-XAt', '-v', 'ON_ERROR_STOP=1', '-U', 'marketfusion', '-d', scratch,
                    '-c', 'SELECT (SELECT count(*) FROM schema_migrations), '
                          '(SELECT count(*) FROM mf_products), (SELECT count(*) FROM v2_watches)',
                    capture_output=True, text=True).stdout.strip()
        if int(counts.split('|')[0]) < 1:
            raise RuntimeError('Restored snapshot has no migration history')
    finally:
        db('dropdb', '-U', 'marketfusion', scratch)

    with dump.open('rb') as file:
        digest = hashlib.file_digest(file, 'sha256').hexdigest()
    result = {'commit': revision, 'images': image_ids, 'sha256': digest,
              'restored_migrations_products_watches': counts, 'restore_verified': True}
    (folder / 'manifest.json').write_text(json.dumps(result, indent=2) + '\n')
    print(f'Verified restore at {folder}. Counts (migrations|products|watches): {counts}')


if __name__ == '__main__':
    main()
