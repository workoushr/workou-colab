# ノートブックのセル「APIと一時トンネルを起動」と「Chatと外部到達性を検証」の実行後、同じカーネルで実行する（key, MODEL を使用）。
# 例: colab exec -s <name> -f bench/speed.py --timeout 3000
import json, time
from urllib.request import Request, urlopen
LOCAL = 'http://127.0.0.1:8090/v1'
def call(payload, timeout=900):
    r = Request(LOCAL + '/chat/completions', data=json.dumps(payload).encode(),
                headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'})
    with urlopen(r, timeout=timeout) as resp: return json.load(resp)
res = {}
# decode speed
for n in (256, 1024):
    t0 = time.monotonic()
    out = call({'model': MODEL, 'messages': [{'role':'user','content':'Write a long, detailed essay about the history of computing. Do not stop early.'}], 'max_tokens': n, 'temperature': 0.7})
    dt = time.monotonic() - t0; u = out.get('usage', {})
    ct = u.get('completion_tokens'); print(f'decode max={n}: {dt:.1f}s usage={u} -> {ct/dt if ct else float("nan"):.1f} tok/s', flush=True)
# prefill speed
filler = 'The quick brown fox jumps over the lazy dog. ' * 10  # ~100 tokens
for k in (8, 32, 128, 240):
    body = '\n'.join(f'[{i}] ' + filler for i in range(k*10)) + '\nNEEDLE: the secret code is 7341.\n' + '\n'.join(f'[{i}] ' + filler for i in range(3))
    t0 = time.monotonic()
    out = call({'model': MODEL, 'messages': [{'role':'user','content': body + '\nWhat is the secret code? Answer with the number only.'}], 'max_tokens': 16, 'temperature': 0})
    dt = time.monotonic() - t0; u = out.get('usage', {})
    pt = u.get('prompt_tokens'); ans = out['choices'][0]['message'].get('content','').strip()
    print(f'prefill ~{k}k: prompt_tokens={pt} {dt:.1f}s -> {pt/dt if pt else float("nan"):.0f} tok/s | answer={ans!r}', flush=True)
