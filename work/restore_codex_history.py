import datetime
import json
import pathlib
import re
import shutil
import sqlite3
import uuid

HOME = pathlib.Path(r'C:\Users\nishimoto\.codex')
TARGET = r'C:\DATA\project'
OLD_PROJECT = r'C:\Users\i58400am\Desktop\newapp'
BACKUP = pathlib.Path(r'C:\DATA\project\work') / ('codex-history-backup-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))

def normalize(value):
    return value.removeprefix('\\\\?\\').replace('\\\\', '\\').lower()

def map_path(value):
    if not isinstance(value, str):
        return value
    normal = normalize(value)
    for old, new in [(OLD_PROJECT, TARGET), (r'C:\Users\i58400am\.codex', str(HOME))]:
        if normal == old.lower() or normal.startswith(old.lower() + '\\'):
            return new + normal[len(old):]
    return value

def map_tree(value):
    if isinstance(value, dict):
        return {k: map_tree(v) for k, v in value.items()}
    if isinstance(value, list):
        return [map_tree(v) for v in value]
    return map_path(value)

def main():
    assert pathlib.Path(TARGET).is_dir()
    BACKUP.mkdir(parents=True)
    connection = sqlite3.connect(HOME / 'state_5.sqlite', timeout=20)
    with sqlite3.connect(BACKUP / 'state_5.sqlite') as backup_connection:
        connection.backup(backup_connection)
    rows = connection.execute('select id,rollout_path,cwd,sandbox_policy from threads').fetchall()
    files = {f.name: f for directory in ['sessions', 'archived_sessions'] for f in (HOME / directory).rglob('*.jsonl')}
    assert all(pathlib.PureWindowsPath(row[1]).name in files for row in rows), 'Missing transcript: refusing changes'
    affected = [row[0] for row in rows if normalize(row[2]) == OLD_PROJECT.lower()]
    with connection:
        existing = connection.execute('select project_id from project_roots where lower(path)=lower(?)', (TARGET,)).fetchone()
        project_id = existing[0] if existing else str(uuid.uuid4())
        if not existing:
            now = int(datetime.datetime.now().timestamp() * 1000)
            position = connection.execute('select coalesce(max(position),-1)+1 from projects').fetchone()[0]
            connection.execute('insert into projects(id,name,metadata,position,created_at_ms,updated_at_ms) values(?,?,?,?,?,?)', (project_id, 'project', '{}', position, now, now))
            connection.execute('insert into project_roots(project_id,position,path) values(?,?,?)', (project_id, 0, TARGET))
        for thread_id, rollout, cwd, policy in rows:
            new_rollout = str(files[pathlib.PureWindowsPath(rollout).name])
            new_policy = json.dumps(map_tree(json.loads(policy)), ensure_ascii=False, separators=(',', ':'))
            connection.execute('update threads set rollout_path=?,cwd=?,sandbox_policy=? where id=?', (new_rollout, map_path(cwd), new_policy, thread_id))
            if thread_id in affected:
                connection.execute('update threads set project_id=? where id=?', (project_id, thread_id))
    assert connection.execute('pragma integrity_check').fetchone()[0] == 'ok'
    assert all(pathlib.Path(row[0]).is_file() for row in connection.execute('select rollout_path from threads'))
    assert connection.execute('select count(*) from threads where project_id=?', (project_id,)).fetchone()[0] >= len(affected)
    connection.close()
    report = {'backup': str(BACKUP), 'threads_checked': len(rows), 'project_threads_restored': len(affected), 'project_root': TARGET, 'integrity_check': 'ok'}
    (BACKUP / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
