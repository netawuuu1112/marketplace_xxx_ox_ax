"""Run current V2 code temporarily, without installing it or touching its DB.

Default: local isolated Docker API. --vps uses the authorized SSH alias and
existing production connector transport. Only this diagnostic process sees
the temporary zip; existing services/code/configuration remain untouched.
"""
import argparse
import base64
import io
import json
from pathlib import Path
import subprocess
import sys
import shlex
import zipfile


def build_loader(environment=None):
    root=Path(__file__).resolve().parents[2]
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as archive:
        for path in (root/'backend/catalog_v2').glob('*.py'):
            archive.write(path,'catalog_v2/'+path.name)
        for package in ('compare-connector','yandex-connector'):
            src=root/'integrations/ru-marketplace-mcp/packages'/package/'src'
            for path in src.rglob('*.py'):
                archive.write(path,path.relative_to(src).as_posix())
    packed=base64.b64encode(stream.getvalue()).decode()
    script=(root/'deployment/scripts/probe_v2_live.py').read_text(encoding='utf-8')
    return 'import base64,tempfile,sys,pathlib,os\nos.environ.update('+repr(environment or {})+')\nwith tempfile.TemporaryDirectory(prefix="mf_v2_probe_") as d:\n p=pathlib.Path(d)/"probe.zip"\n p.write_bytes(base64.b64decode('+repr(packed)+'))\n sys.path.insert(0,str(p))\n exec(compile('+repr(script)+',"probe_v2_live.py","exec"))\n'


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--vps',action='store_true')
    parser.add_argument('--sources',default='yandex_market,wildberries')
    parser.add_argument('--query',default='Kingston NV3 1TB')
    parser.add_argument('--output',default='live-probe.json')
    args=parser.parse_args()
    if Path(args.output).name!=args.output:
        parser.error('output must be a filename under ignored backups/v2')
    root=Path(__file__).resolve().parents[2]
    loader=build_loader()
    invocation=['docker','exec','-i','marketfusion-api-1' if args.vps else 'marketfusion-v2-staging-api-1','python','-',
                '--query',args.query,'--sources',args.sources]
    command=(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15','codex-vps-2',shlex.join(invocation)] if args.vps else invocation)
    print('Running bounded live probe; no database connection or bot polling.',flush=True)
    result=subprocess.run(command,input=loader,capture_output=True,text=True,encoding='utf-8',timeout=95*len(args.sources.split(','))+45)
    if result.returncode:
        print(result.stderr[-3000:],file=sys.stderr)
        raise SystemExit(result.returncode)
    data=json.loads(result.stdout)
    folder=root/'backups/v2';folder.mkdir(parents=True,exist_ok=True)
    (folder/args.output).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'query':data['query'],'status':data['status'],'error':data.get('error'),
        'sources':data['sources'],'exact_groups':len(data['groups']),'related_groups':len(data['related']),
        'cross_source_exact_groups':sum(len({o['source'] for o in group['offers']})>1 for group in data['groups'])},ensure_ascii=True))


if __name__=='__main__':
    main()
