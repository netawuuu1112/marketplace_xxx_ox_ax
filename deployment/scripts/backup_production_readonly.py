"""Read-only production backup, restored only into a fresh LOCAL staging DB.

Never starts migrations on production, stops a service or prints environment
contents/credentials. SQL dumps use binary files, avoiding PowerShell redirects.
"""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
from uuid import uuid4

TABLES=('users','favorites','watchlists','price_history','notifications','ai_providers',
        'ai_routes','sessions','settings','llm_budget','audit_events','cache')
QUERY=' UNION ALL '.join("SELECT '{0}:'||count(*)||':'||md5(COALESCE(jsonb_agg(to_jsonb(r) ORDER BY to_jsonb(r)::text)::text,'[]')) FROM {0} r".format(table) for table in TABLES)+';'


def remote(arguments,*,input=None,destination=None):
    command=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15','codex-vps-2',shlex.join(arguments)]
    result=subprocess.run(command,input=input,stdout=destination or subprocess.PIPE,stderr=subprocess.PIPE,timeout=120)
    if result.returncode:
        raise RuntimeError('Read-only production backup command failed: '+result.stderr.decode('utf-8',errors='replace')[:300])
    return result.stdout


def run(arguments,*,input=None):
    return subprocess.run(arguments,input=input,capture_output=True,check=True,text=True,encoding='utf-8',timeout=90).stdout


def main():
    root=Path(__file__).resolve().parents[2]
    container='marketfusion-v2-staging-db-1'
    details=json.loads(run(['docker','inspect',container]))
    assert details[0]['Config']['Labels']['com.docker.compose.project']=='marketfusion-v2-staging'
    directory=root/'backups/v2'/('production-'+datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S'))
    directory.mkdir(parents=True,exist_ok=False)
    sql=['docker','exec','-i','marketfusion-db-1','sh','-c',
         'exec psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -v ON_ERROR_STOP=1']
    before=remote(sql,input=QUERY.encode()).decode().splitlines()
    dump=directory/'production.dump'
    with dump.open('wb') as file:
        remote(['docker','exec','marketfusion-db-1','sh','-c',
                'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc'],destination=file)
    after=remote(sql,input=QUERY.encode()).decode().splitlines()
    for filename in ('.env','docker-compose.yml','docker-compose.browser.yml'):
        with (directory/filename).open('wb') as file:
            remote(['cat','/opt/marketfusion/'+filename],destination=file)
    sha=remote(['git','-C','/opt/marketfusion','rev-parse','HEAD']).decode().strip()
    identity=uuid4().hex
    scratch='restore_production_'+identity
    temporary='/tmp/restore_production_'+identity+'.dump'
    run(['docker','cp',str(dump),container+':'+temporary])
    run(['docker','exec',container,'createdb','-U','marketfusion',scratch])
    try:
        run(['docker','exec',container,'pg_restore','-U','marketfusion','--exit-on-error','--no-owner','--no-privileges','-d',scratch,temporary])
        restored=run(['docker','exec','-i',container,'psql','-U','marketfusion','-d',scratch,'-At'],input=QUERY).splitlines()
        verified=before==after==restored
        manifest={'production_sha':sha,'dump_sha256':hashlib.sha256(dump.read_bytes()).hexdigest(),
                  'source_before':before,'source_after':after,'restored':restored,'verified':verified}
        (directory/'restore-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
        assert verified,'Concurrent source writes or restored data mismatch; archive retained, no production mutation'
        counts=[row.rsplit(':',1)[0] for row in restored]
        print(json.dumps({'restore_verified':True,'tables':counts,'production_sha':sha,
            'private_archive_directory':directory.name,'production_changed':False}))
    finally:
        run(['docker','exec',container,'dropdb','-U','marketfusion',scratch])
        run(['docker','exec',container,'rm','-f',temporary])


if __name__=='__main__':
    main()
