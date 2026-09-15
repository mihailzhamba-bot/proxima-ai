"""Load the bot credential without putting it in Docker env/arguments/config."""
import json
import os
import re
from pathlib import Path


def main():
    config = json.loads(Path('/etc/loop/native-telegram.json').read_text())
    os.environ.pop('TELEGRAM_BOT_TOKEN', None)
    user = str(config.get('user_id', ''))
    if user:
        if not re.fullmatch(r'[1-9][0-9]{0,19}', user) or user != str(config.get('chat_id', '')):
            raise SystemExit('Native Telegram requires one private owner chat')
        token_path = Path('/run/secrets/hermes_telegram_bot')
        if token_path.stat().st_mode & 0o077:
            raise SystemExit('Native Telegram token file must be private')
        token = token_path.read_text().strip()
        if not re.fullmatch(r'[0-9]+:[A-Za-z0-9_-]{30,}', token):
            raise SystemExit('Native Telegram token unavailable')
        os.environ['TELEGRAM_BOT_TOKEN'] = token
        os.environ['TELEGRAM_ALLOWED_USERS'] = user
        os.environ['TELEGRAM_ALLOWED_CHATS'] = user
        os.environ['TELEGRAM_HOME_CHANNEL'] = user
    exe = '/opt/hermes/.venv/bin/hermes'
    os.execv(exe, [exe, 'gateway', 'run', '--external-supervisor'])


if __name__ == '__main__':
    main()
