# ノートブックのセル「APIと一時トンネルを起動」と「Chatと外部到達性を検証」の実行後、同じカーネルで実行する（key, MODEL を使用）。
# 架空のプロジェクトを /content/sandbox に作り、read/write/edit/bash ツールで課題を解かせる。
# 例: colab exec -s <name> -f bench/agent_tasks.py --timeout 3000
import json, time, subprocess, shutil
from pathlib import Path
from urllib.request import Request, urlopen
LOCAL = 'http://127.0.0.1:8090/v1'
def call(payload, timeout=900):
    r = Request(LOCAL + '/chat/completions', data=json.dumps(payload).encode(),
                headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'})
    with urlopen(r, timeout=timeout) as resp: return json.load(resp)
def fn(name, desc, props, req):
    return {'type':'function','function':{'name':name,'description':desc,'parameters':{'type':'object','properties':props,'required':req,'additionalProperties':False}}}
TOOLS = [
 fn('read','Read a file (path relative to project root).',{'path':{'type':'string'}},['path']),
 fn('write','Create or overwrite a file.',{'path':{'type':'string'},'content':{'type':'string'}},['path','content']),
 fn('edit','Replace exactly one occurrence of old_text with new_text in a file.',{'path':{'type':'string'},'old_text':{'type':'string'},'new_text':{'type':'string'}},['path','old_text','new_text']),
 fn('bash','Run a shell command in the project root; returns stdout+stderr.',{'command':{'type':'string'}},['command']),
]
TASKS = {
 'bugfix': ({
  'textstats.py': '''def word_count(text):
    return len(text.split(" "))

def top_words(text, n=3):
    counts = {}
    for w in text.lower().split():
        w = w.strip(".,!?")
        counts[w] = counts.get(w, 0) + 1
    return sorted(counts, key=lambda w: counts[w])[:n]

def average_word_length(text):
    words = text.split()
    return sum(len(w) for w in words) / len(words)
''',
  'test_textstats.py': '''from textstats import word_count, top_words, average_word_length
def test_word_count():
    assert word_count("hello   world\\nfoo") == 3
def test_top_words():
    assert top_words("b a b c b a", 2) == ["b", "a"]
def test_avg_empty():
    assert average_word_length("") == 0.0
def test_avg():
    assert average_word_length("ab abcd") == 3.0
'''}, 'Run the tests with `python -m pytest -q`, find the bugs in textstats.py and fix them so that all tests pass. Do not modify the tests. When done, reply with a short summary.'),
 'feature': ({
  'todo.py': '''import json, sys
from pathlib import Path
DB = Path("todos.json")
def load():
    return json.loads(DB.read_text()) if DB.exists() else []
def save(items):
    DB.write_text(json.dumps(items))
def main(argv):
    cmd = argv[0]
    items = load()
    if cmd == "add":
        items.append({"text": " ".join(argv[1:]), "done": False}); save(items)
    elif cmd == "list":
        for i, t in enumerate(items, 1):
            print(f"{i}. [{'x' if t['done'] else ' '}] {t['text']}")
if __name__ == "__main__":
    main(sys.argv[1:])
'''}, 'todo.py に `done N` コマンド（N番目を完了にする、範囲外ならエラーメッセージを出して終了コード1）と `clear` コマンド（完了済みを削除）を追加し、pytestのテスト test_todo.py も書いて、テストが全部通ることを確認してください。終わったら日本語で短く報告してください。'),
}
def run_tool(root, name, args):
    p = lambda x: root / x
    if name == 'read': return p(args['path']).read_text()
    if name == 'write': p(args['path']).write_text(args['content']); return 'ok'
    if name == 'edit':
        s = p(args['path']).read_text(); c = s.count(args['old_text'])
        if c != 1: return f'error: old_text found {c} times'
        p(args['path']).write_text(s.replace(args['old_text'], args['new_text'])); return 'ok'
    if name == 'bash':
        r = subprocess.run(args['command'], shell=True, cwd=root, capture_output=True, text=True, timeout=120)
        return (r.stdout + r.stderr)[-4000:] + f'\n[exit {r.returncode}]'
    return f'error: unknown tool {name}'
subprocess.run('pip -q install pytest', shell=True)
for tname, (files, prompt) in TASKS.items():
    root = Path('/content/sandbox')/tname; shutil.rmtree(root, ignore_errors=True); root.mkdir(parents=True)
    for f, c in files.items(): (root/f).write_text(c)
    msgs = [{'role':'system','content':'You are a coding agent working in a project directory. Use the tools to inspect, edit and test code. Work step by step until the task is complete.'},
            {'role':'user','content':prompt}]
    stats = {'turns':0,'calls':0,'bad_args':0,'tool_errors':0,'gen_s':0.0,'out_tokens':0}
    t0 = time.monotonic(); final = ''
    for turn in range(25):
        ts = time.monotonic()
        out = call({'model':MODEL,'messages':msgs,'tools':TOOLS,'max_tokens':4096,'temperature':0.2})
        stats['gen_s'] += time.monotonic()-ts; stats['out_tokens'] += out.get('usage',{}).get('completion_tokens',0); stats['turns'] += 1
        m = out['choices'][0]['message']; msgs.append(m)
        calls = m.get('tool_calls') or []
        if not calls: final = m.get('content') or ''; break
        for c in calls:
            stats['calls'] += 1; name = c['function']['name']
            try:
                a = json.loads(c['function']['arguments']); r = run_tool(root, name, a)
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                stats['bad_args'] += 1; r = f'error: bad arguments ({e})'
            except Exception as e:
                r = f'error: {e}'
            if r.startswith('error') and 'bad arguments' not in r: stats['tool_errors'] += 1
            print(f'  [{tname} t{turn}] {name}({c["function"]["arguments"][:120]}) -> {r[:100]!r}', flush=True)
            msgs.append({'role':'tool','tool_call_id':c['id'],'content':r})
    v = subprocess.run('python -m pytest -q 2>&1 | tail -3', shell=True, cwd=root, capture_output=True, text=True).stdout
    tests_untouched = tname != 'bugfix' or (root/'test_textstats.py').read_text() == files['test_textstats.py']
    print(f'== {tname}: wall {time.monotonic()-t0:.0f}s {stats} tests_untouched={tests_untouched}\n  pytest: {v.strip()}\n  final: {final[:400]}', flush=True)
