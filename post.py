import json, os, pathlib, subprocess, sys, time, urllib.parse, urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = pathlib.Path(__file__).resolve().parent
CHAT = "@setkahhegor"


def git(*args, check=True):
    return subprocess.run(["git", *args], cwd=ROOT, check=check)


def main():
    now = datetime.now(ZoneInfo("Europe/Moscow"))
    if not (7 <= now.hour <= 16):
        print("Outside Moscow posting window")
        return
    slot = now.strftime("%Y-%m-%d %H")
    slot_file = ROOT / "last_slot.txt"
    if slot_file.exists() and slot_file.read_text().strip() == slot:
        print("Slot already published:", slot)
        return
    if (ROOT / "STOP").exists():
        print("STOP file present, publishing paused")
        return
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    posts = json.loads((ROOT / "posts.json").read_text(encoding="utf-8"))
    counter = ROOT / "sent_count.txt"
    sent = int(counter.read_text().strip())
    if sent >= len(posts):
        print("All posts published")
        return
    message = posts[sent]
    if len(message) > 4096:
        raise ValueError("Post too long for Telegram")
    data = urllib.parse.urlencode({"chat_id": CHAT, "text": message}).encode()
    req = urllib.request.Request("https://api.telegram.org/bot" + token + "/sendMessage", data=data)
    with urllib.request.urlopen(req, timeout=30) as r:
        result = json.loads(r.read())
    if not result.get("ok"):
        raise RuntimeError("Telegram did not confirm publication")
    # Message is out: record state, retrying the push so a hiccup cannot cause a repeat.
    counter.write_text(str(sent + 1) + "\n")
    slot_file.write_text(slot + "\n")
    git("config", "user.name", "github-actions[bot]")
    git("config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    git("add", "sent_count.txt", "last_slot.txt")
    git("commit", "-m", "Record published post " + str(sent + 1))
    for attempt in range(5):
        if git("push", check=False).returncode == 0:
            print("Published post", sent + 1, "of", len(posts))
            return
        time.sleep(5 * (attempt + 1))
        git("pull", "--rebase", "-X", "theirs", check=False)
    print("PUSH FAILED: post", sent + 1, "was sent but counter not saved. Set sent_count.txt to", sent + 1, file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
