"""Ephemeral VPS->desktop agent acceptance; no production deployment/DB writes.

No public port, sshd change, copied key or installed service. Own temporary
socket lives under the existing container's /tmp and is removed in finally.
The private agent token is passed via encrypted SSH stdin and never printed.
"""
import json
from pathlib import Path
import shlex
import subprocess
import sys
from uuid import uuid4

from run_v2_probe import build_loader


def ssh(arguments,*,input=None,timeout=30):
    result=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15','codex-vps-2',shlex.join(arguments)],
        input=input,capture_output=True,text=True,encoding='utf-8',timeout=timeout)
    if result.returncode:
        raise RuntimeError('Private diagnostic SSH command failed: '+result.stderr[-300:])
    return result.stdout


def main():
    root=Path(__file__).resolve().parents[2]
    settings=dict(line.split('=',1) for line in (root/'.env.v2-staging').read_text().splitlines() if '=' in line)
    token=settings['V2_AGENT_TOKEN']
    pid=int(ssh(['docker','inspect','--format','{{.State.Pid}}','marketfusion-api-1']).strip())
    folder='/tmp/mf_v2_agent_probe_'+uuid4().hex
    socket=folder+'/source.sock'
    ssh(['docker','exec','-i','marketfusion-api-1','python','-'],input='import os\nos.mkdir('+repr(folder)+',0o700)\n')
    tunnel=None
    try:
        forwarded=f'/proc/{pid}/root{socket}:127.0.0.1:8092'
        tunnel=subprocess.Popen(['ssh','-N','-o','BatchMode=yes','-o','ExitOnForwardFailure=yes',
            '-o','ServerAliveInterval=15','-o','StreamLocalBindUnlink=yes','-R',forwarded,'codex-vps-2'],
            stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        ready='import os,time\nfor _ in range(15):\n if os.path.exists('+repr(socket)+'): break\n time.sleep(.5)\nelse: raise RuntimeError("Private socket did not appear")\n'
        ssh(['docker','exec','-i','marketfusion-api-1','python','-'],input=ready)
        environment={'MARKETFUSION_SOURCE_AGENT_SOCKET':socket,'MARKETFUSION_SOURCE_AGENT_TOKEN':token,
            'MARKETFUSION_SOURCE_AGENT_SOURCES':'avito,dns,aliexpress'}
        print('Testing real VPS -> private SSH socket -> local agent; no public listener.',flush=True)
        stdout=ssh(['docker','exec','-i','marketfusion-api-1','python','-','--agent','--query','Kingston NV3 1TB',
                    '--sources','avito,dns,aliexpress'],input=build_loader(environment),timeout=330)
        data=json.loads(stdout)
        output=root/'backups/v2/live-private-agent-vps.json'
        output.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({'status':data['status'],'sources':data['sources'],'groups':len(data['groups']),
                          'related':len(data['related'])},ensure_ascii=True))
    finally:
        if tunnel is not None:
            tunnel.terminate()
            try: tunnel.wait(timeout=5)
            except subprocess.TimeoutExpired: tunnel.kill();tunnel.wait()
        # Only exact names created above are removed; no recursive deletion.
        cleanup='from pathlib import Path\np=Path('+repr(folder)+')\nassert p.parent==Path("/tmp") and p.name.startswith("mf_v2_agent_probe_")\n(p/"source.sock").unlink(missing_ok=True)\np.rmdir()\n'
        ssh(['docker','exec','-i','marketfusion-api-1','python','-'],input=cleanup)
        print('Temporary SSH tunnel and its socket removed; production unchanged.')


if __name__=='__main__':
    main()
