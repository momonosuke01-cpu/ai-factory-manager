# Task Manager 01（管理＋検査・納品）
# 役割: 仕事を処理役へ渡す → 結果を受け取る → 検査する → 利益を台帳に記録する。
# 起動後、最初の1回だけ試しの仕事で流れを1周させる（test_state.json で再実行を防ぐ）。
# 処理役のURLは環境変数 WORKER_URL で渡す。未設定なら接続先待ちで待機する。
import csv
import json
import os
import time
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
WORKER_URL = os.environ.get(
    "WORKER_URL", "http://se-sto02.tryaltare.ai:25946").rstrip("/")
# 処理役と同じ合言葉。環境変数 FACTORY_TOKEN で渡す
TOKEN = os.environ.get("FACTORY_TOKEN", "")
LEDGER_FILE = os.path.join(BASE, "ledger.csv")
STATE_FILE = os.path.join(BASE, "test_state.json")
REWARD_PER_ITEM = 10  # 試し用の仮単価（円/件）。本物の仕事が決まったら実単価に変える


def http_json(method, url, obj=None):
    data = json.dumps(obj).encode("utf-8") if obj is not None else None
    headers = {"Content-Type": "application/json"}
    if TOKEN:
        headers["X-Factory-Token"] = TOKEN
    req = urllib.request.Request(url, data=data, method=method,
                                 headers=headers)
    with urllib.request.urlopen(req, timeout=30) as res:
        return json.loads(res.read().decode("utf-8"))


def check(result):
    """検査: 件数のつじつま、空文字・重複が残っていないかを見る。"""
    lines = result["result"]["lines"]
    if len(lines) != result["items_out"]:
        return False, "items_out mismatch"
    if any(not str(s).strip() for s in lines):
        return False, "empty line remains"
    if len(lines) != len(set(lines)):
        return False, "duplicates remain"
    return True, "ok"


def append_ledger(row):
    new = not os.path.exists(LEDGER_FILE)
    with open(LEDGER_FILE, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["job_id", "items_out", "reward_yen", "ai_cost_yen",
                        "fee_yen", "profit_yen", "check", "note"])
        w.writerow(row)


def run_test_cycle():
    job = {
        "id": "test-001",
        "type": "text_clean",
        "payload": {"lines": [" りんご ", "ばなな", "りんご", "", "  みかん", "ばなな ", "ぶどう"]},
    }
    print(f"[manager] sending test job to {WORKER_URL}", flush=True)
    result = http_json("POST", WORKER_URL + "/jobs", job)
    ok, note = check(result)
    reward = result["items_out"] * REWARD_PER_ITEM
    ai_cost = result.get("ai_cost_yen", 0)
    fee = 0
    profit = reward - ai_cost - fee
    append_ledger([job["id"], result["items_out"], reward, ai_cost, fee,
                   profit, "pass" if ok else "fail", note])
    print(f"[manager] check={'pass' if ok else 'fail'} ({note}) "
          f"reward={reward} cost={ai_cost} profit={profit}", flush=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({"test_job_done": True, "check_pass": ok, "profit_yen": profit}, f)
    print("[manager] test cycle complete", flush=True)


if __name__ == "__main__":
    print("[manager] starting", flush=True)
    if not WORKER_URL:
        print("[manager] WORKER_URL is not set. Waiting (set WORKER_URL and restart).", flush=True)
    elif not os.path.exists(STATE_FILE):
        # 処理役の起動待ち
        for i in range(30):
            try:
                h = http_json("GET", WORKER_URL + "/health")
                if h.get("status") == "ok":
                    break
            except Exception:
                time.sleep(5)
        else:
            print("[manager] worker did not come up in time", flush=True)
        if os.path.exists(STATE_FILE) is False:
            try:
                run_test_cycle()
            except Exception as e:
                print(f"[manager] test cycle failed: {e}", flush=True)
    else:
        print("[manager] test job already done. Idling.", flush=True)
    while True:
        time.sleep(300)
        print("[manager] alive", flush=True)
