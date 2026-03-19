#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime

GLOBAL = Path('/Users/seo/.openclaw/workspace/global_state.json')


def now_iso():
    return datetime.now().astimezone().isoformat()


def load_state():
    if GLOBAL.exists():
        return json.loads(GLOBAL.read_text())
    return {}


def save_state(state):
    state['updated_at'] = now_iso()
    GLOBAL.write_text(json.dumps(state, ensure_ascii=False, indent=2))


def update_latest_snapshot(path, source='admin_bot'):
    state = load_state()
    state.setdefault('latest_account_snapshot', {})
    state['latest_account_snapshot']['path'] = str(path)
    state['latest_account_snapshot']['updated_at'] = now_iso()
    state['latest_account_snapshot']['source'] = source
    save_state(state)


def update_dashboard_status(path, source='main_session'):
    state = load_state()
    state.setdefault('latest_dashboard_status', {})
    state['latest_dashboard_status']['path'] = str(path)
    state['latest_dashboard_status']['updated_at'] = now_iso()
    state['latest_dashboard_status']['source'] = source
    save_state(state)
