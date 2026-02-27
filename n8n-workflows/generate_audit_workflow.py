#!/usr/bin/env python3
"""Generate n8n workflow for CRM Audit — compares bot data with Didar CRM.

Reads shared config from config.json (same file used by generate_workflow.py).

Steps:
1. Login to bot panel → JWT token
2. Fetch all bot users via /api/audit/users
3. Fetch all Didar Deals in pipeline (includes embedded Person data)
4. Compare & generate discrepancy report
5. Output formatted report (manual trigger output)
"""
import json
import os


def load_config():
    """Load shared config from config.json."""
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    with open(config_path, "r") as f:
        return json.load(f)


def build_workflow(platform="telegram"):
    nodes = []
    connections = {}

    def add_node(node):
        nodes.append(node)

    def connect(from_name, to_name, from_output=0, to_input=0):
        if from_name not in connections:
            connections[from_name] = {"main": []}
        while len(connections[from_name]["main"]) <= from_output:
            connections[from_name]["main"].append([])
        connections[from_name]["main"][from_output].append({
            "node": to_name,
            "type": "main",
            "index": to_input
        })

    # ═══════════════════════════════════════════════════
    # MANUAL TRIGGER
    # ═══════════════════════════════════════════════════

    add_node({
        "id": "trigger",
        "name": "Manual Trigger",
        "type": "n8n-nodes-base.manualTrigger",
        "typeVersion": 1,
        "position": [250, 500],
        "parameters": {}
    })

    # ═══════════════════════════════════════════════════
    # CONFIG NODE — values injected from config.json
    # ═══════════════════════════════════════════════════

    cfg = load_config()
    d = cfg["didar"]
    panel = cfg["bot_panel"].get(platform, cfg["bot_panel"]["telegram"])

    # Build stages JS object
    stages_js = ",\n    ".join(
        f"{k}: '{v}'" for k, v in d["stages"].items()
    )
    # Build custom_fields JS object (only lead_score needed for audit)
    cf_js = ",\n    ".join(
        f"{k}: '{v}'" for k, v in d["custom_fields"].items()
    )

    config_code = f"""
const CONFIG = {{
  DIDAR_API_KEY: '{d["api_key"]}',
  PIPELINE_ID: '{d["pipeline_id"]}',
  COMPANY_ID: '{d["company_id"]}',

  STAGES: {{
    {stages_js}
  }},

  CUSTOM_FIELDS: {{
    {cf_js}
  }},

  BOT_PANEL_URL: '{panel["url"]}',
  BOT_ADMIN_USER: '{panel["username"]}',
  BOT_ADMIN_PASS: '{panel["password"]}',
}};

// Build reverse stage lookup: GUID → stage name
const stageToName = {{}};
for (const [name, guid] of Object.entries(CONFIG.STAGES)) {{
  stageToName[guid] = name;
}}
CONFIG._stageToName = stageToName;

// Build lesson_number → stage GUID mapping
const lessonToStage = {{}};
for (const [name, guid] of Object.entries(CONFIG.STAGES)) {{
  const m = name.match(/^lesson_(\\d+)$/);
  if (m) lessonToStage[parseInt(m[1])] = guid;
}}
CONFIG._lessonToStage = lessonToStage;

return [{{json: {{CONFIG}}}}];
"""

    add_node({
        "id": "config",
        "name": "Config",
        "type": "n8n-nodes-base.code",
        "typeVersion": 1,
        "position": [500, 500],
        "parameters": {"jsCode": config_code, "mode": "runOnceForAllItems"}
    })

    # ═══════════════════════════════════════════════════
    # STEP 1: LOGIN TO BOT PANEL
    # ═══════════════════════════════════════════════════

    add_node({
        "id": "login",
        "name": "Login Bot Panel",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [750, 500],
        "parameters": {
            "method": "POST",
            "url": "={{ $json.CONFIG.BOT_PANEL_URL + '/api/auth/login' }}",
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": "={{ JSON.stringify({username: $json.CONFIG.BOT_ADMIN_USER, password: $json.CONFIG.BOT_ADMIN_PASS}) }}",
            "options": {"timeout": 15000}
        }
    })

    # Extract JWT token + pass CONFIG forward
    extract_token_code = r"""
const config = $('Config').first().json.CONFIG;
const resp = $input.first().json;
const token = resp.access_token || '';
if (!token) throw new Error('Login failed — no access_token in response');
return [{json: {CONFIG: config, token}}];
"""

    add_node({
        "id": "extract_token",
        "name": "Extract Token",
        "type": "n8n-nodes-base.code",
        "typeVersion": 1,
        "position": [1000, 500],
        "parameters": {"jsCode": extract_token_code, "mode": "runOnceForAllItems"}
    })

    # ═══════════════════════════════════════════════════
    # STEP 2: FETCH BOT USERS
    # ═══════════════════════════════════════════════════

    add_node({
        "id": "fetch_bot_users",
        "name": "Fetch Bot Users",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [1250, 500],
        "parameters": {
            "method": "GET",
            "url": "={{ $json.CONFIG.BOT_PANEL_URL + '/api/audit/users' }}",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [{
                    "name": "Authorization",
                    "value": "=Bearer {{ $json.token }}"
                }]
            },
            "options": {"timeout": 30000}
        }
    })

    extract_bot_users_code = r"""
const config = $('Config').first().json.CONFIG;
const token = $('Extract Token').first().json.token;
const resp = $input.first().json;
const botUsers = resp.items || [];
return [{json: {CONFIG: config, token, botUsers, totalBotUsers: botUsers.length}}];
"""

    add_node({
        "id": "extract_bot_users",
        "name": "Extract Bot Users",
        "type": "n8n-nodes-base.code",
        "typeVersion": 1,
        "position": [1500, 500],
        "parameters": {"jsCode": extract_bot_users_code, "mode": "runOnceForAllItems"}
    })

    # ═══════════════════════════════════════════════════
    # STEP 3: FETCH ALL DIDAR DEALS IN PIPELINE
    # (Deals include embedded Person data with phone/fields)
    # ═══════════════════════════════════════════════════

    add_node({
        "id": "fetch_deals",
        "name": "Fetch Didar Deals",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [1750, 500],
        "parameters": {
            "method": "POST",
            "url": "={{ 'https://app.didar.me/api/deal/search_v2?apikey=' + $json.CONFIG.DIDAR_API_KEY }}",
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": "={{ JSON.stringify({Criteria: {PipelineId: $json.CONFIG.PIPELINE_ID}, From: 0, Limit: 5000}) }}",
            "options": {"timeout": 60000}
        }
    })

    # ═══════════════════════════════════════════════════
    # STEP 4: COMPARE & AUDIT
    # (Uses deal.Person embedded data — no separate person fetch)
    # ═══════════════════════════════════════════════════

    compare_code = r"""
// Gather inputs
const data = $('Extract Bot Users').first().json;
const CONFIG = data.CONFIG;
const botUsers = data.botUsers || [];

const dealsResp = $('Fetch Didar Deals').first().json;
const deals = dealsResp?.Response?.List || dealsResp?.search_respons?.List || [];

// ── Build lookup maps ──

// Normalise phone: remove leading 0, keep last 10 digits
function normalisePhone(raw) {
  if (!raw) return '';
  const digits = String(raw).replace(/\D/g, '');
  if (digits.length >= 10) return digits.slice(-10);
  return digits;
}

// Build deal lookup by person phone (using embedded Person data)
const dealByPhone = {};
const personByPhone = {};
for (const d of deals) {
  const person = d.Person || d.Contact || {};
  const phones = [person.MobilePhone, person.WorkPhone, person.Phone, person.HomePhone].filter(Boolean);
  for (const ph of phones) {
    const norm = normalisePhone(ph);
    if (norm) {
      // Prefer Pending deals; if multiple, keep first pending
      if (!dealByPhone[norm] || d.Status === 'Pending') {
        dealByPhone[norm] = d;
      }
      if (!personByPhone[norm]) {
        personByPhone[norm] = person;
      }
    }
  }
}

// Stage name from GUID lookup
const stageToName = CONFIG._stageToName || {};
const lessonToStage = CONFIG._lessonToStage || {};

// ── Build expected stage for each user ──
function expectedStage(user) {
  if (user.is_completed) return {name: 'won', guid: CONFIG.STAGES.won};
  const ln = user.current_lesson_number;
  if (ln && lessonToStage[ln]) {
    return {name: 'lesson_' + ln, guid: lessonToStage[ln]};
  }
  return {name: 'register', guid: CONFIG.STAGES.register};
}

// ── Compare each bot user ──
const report = {
  summary: {
    total_bot_users: botUsers.length,
    users_with_phone: 0,
    users_without_phone: 0,
    total_crm_deals: deals.length,
    deal_found: 0,
    deal_missing: 0,
    stage_match: 0,
    stage_mismatch: 0,
    status_match: 0,
    status_mismatch: 0,
    lead_score_match: 0,
    lead_score_mismatch: 0,
    fully_synced: 0,
  },
  missing_deals: [],
  stage_mismatches: [],
  status_mismatches: [],
  lead_score_mismatches: [],
  orphan_deals: [],
};

const matchedPhones = new Set();

for (const user of botUsers) {
  const phone = normalisePhone(user.phone);
  if (!phone) {
    report.summary.users_without_phone++;
    continue;
  }
  report.summary.users_with_phone++;

  const deal = dealByPhone[phone];
  const person = personByPhone[phone];
  const issues = [];

  if (!deal) {
    report.summary.deal_missing++;
    report.missing_deals.push({
      bot_user_id: user.id,
      name: (user.first_name || '') + ' ' + (user.last_name || ''),
      phone: user.phone,
      lesson: user.current_lesson_number,
      completed: user.is_completed,
    });
    continue;
  }

  matchedPhones.add(phone);
  report.summary.deal_found++;

  // Check stage
  const exp = expectedStage(user);
  const actualStageGuid = deal.PipelineStageId || '';
  const actualStageName = stageToName[actualStageGuid] || actualStageGuid;

  if (actualStageGuid === exp.guid) {
    report.summary.stage_match++;
  } else {
    report.summary.stage_mismatch++;
    report.stage_mismatches.push({
      bot_user_id: user.id,
      name: (user.first_name || '') + ' ' + (user.last_name || ''),
      phone: user.phone,
      expected_stage: exp.name,
      actual_stage: actualStageName,
      deal_id: deal.Id,
      lesson: user.current_lesson_number,
      completed: user.is_completed,
    });
    issues.push('stage_mismatch');
  }

  // Check deal status
  const expectedStatus = user.is_completed ? 'Won' : 'Pending';
  const actualStatus = deal.Status || 'Unknown';
  if (actualStatus === expectedStatus) {
    report.summary.status_match++;
  } else {
    report.summary.status_mismatch++;
    report.status_mismatches.push({
      bot_user_id: user.id,
      name: (user.first_name || '') + ' ' + (user.last_name || ''),
      phone: user.phone,
      expected_status: expectedStatus,
      actual_status: actualStatus,
      deal_id: deal.Id,
    });
    issues.push('status_mismatch');
  }

  // Check lead_score (on embedded Person custom fields)
  const crmLeadScoreField = CONFIG.CUSTOM_FIELDS?.lead_score;
  if (crmLeadScoreField && crmLeadScoreField !== 'FIELD_GUID' && person?.Fields) {
    const crmScore = parseInt(person.Fields[crmLeadScoreField] || '0', 10);
    const botScore = user.lead_score || 0;
    if (crmScore === botScore) {
      report.summary.lead_score_match++;
    } else {
      report.summary.lead_score_mismatch++;
      report.lead_score_mismatches.push({
        bot_user_id: user.id,
        name: (user.first_name || '') + ' ' + (user.last_name || ''),
        phone: user.phone,
        bot_lead_score: botScore,
        crm_lead_score: crmScore,
        crm_person_id: person.Id,
      });
      issues.push('lead_score_mismatch');
    }
  }

  if (issues.length === 0) {
    report.summary.fully_synced++;
  }
}

// Find orphan deals (in pipeline but no matching bot user)
const botPhones = new Set(botUsers.map(u => normalisePhone(u.phone)).filter(Boolean));
for (const deal of deals) {
  const person = deal.Person || deal.Contact || {};
  const phones = [person.MobilePhone, person.WorkPhone].filter(Boolean).map(normalisePhone);
  const hasMatch = phones.some(ph => botPhones.has(ph));
  if (!hasMatch) {
    report.orphan_deals.push({
      deal_id: deal.Id,
      deal_title: deal.Title || '',
      person_name: person.DisplayName || 'Unknown',
      phone: person.MobilePhone || '',
      stage: stageToName[deal.PipelineStageId] || deal.PipelineStageId,
      status: deal.Status,
    });
  }
}

return [{json: report}];
"""

    add_node({
        "id": "compare",
        "name": "Compare & Audit",
        "type": "n8n-nodes-base.code",
        "typeVersion": 1,
        "position": [2100, 500],
        "parameters": {"jsCode": compare_code, "mode": "runOnceForAllItems"}
    })

    # ═══════════════════════════════════════════════════
    # STEP 5: FORMAT REPORT (Persian + English)
    # ═══════════════════════════════════════════════════

    format_code = r"""
const r = $input.first().json;
const s = r.summary;

const lines = [];
lines.push('═══════════════════════════════════');
lines.push('  📊 گزارش آدیت ربات ↔ CRM دیدار');
lines.push('  CRM Sync Audit Report');
lines.push('═══════════════════════════════════');
lines.push('');
lines.push('📋 خلاصه / Summary');
lines.push('───────────────────────────────────');
lines.push(`  کاربران ربات (کل)        : ${s.total_bot_users}`);
lines.push(`  دارای شماره تلفن          : ${s.users_with_phone}`);
lines.push(`  بدون شماره تلفن           : ${s.users_without_phone}`);
lines.push(`  دیل‌های CRM               : ${s.total_crm_deals}`);
lines.push('');
lines.push('🔍 نتایج مقایسه / Comparison Results');
lines.push('───────────────────────────────────');
lines.push(`  ✅ دیل پیدا شد            : ${s.deal_found}`);
lines.push(`  ❌ دیل ناموجود            : ${s.deal_missing}`);
lines.push(`  ✅ استیج صحیح             : ${s.stage_match}`);
lines.push(`  ❌ استیج اشتباه           : ${s.stage_mismatch}`);
lines.push(`  ✅ وضعیت صحیح             : ${s.status_match}`);
lines.push(`  ❌ وضعیت اشتباه           : ${s.status_mismatch}`);
lines.push(`  ✅ امتیاز لید صحیح        : ${s.lead_score_match}`);
lines.push(`  ❌ امتیاز لید اشتباه      : ${s.lead_score_mismatch}`);
lines.push('');

const syncRate = s.users_with_phone > 0
  ? ((s.fully_synced / s.users_with_phone) * 100).toFixed(1)
  : '0.0';
lines.push(`  🎯 کاملاً سینک شده: ${s.fully_synced} / ${s.users_with_phone} (${syncRate}%)`);
lines.push('');

// ── Details sections ──
if (r.missing_deals.length > 0) {
  lines.push('');
  lines.push('🚫 دیل ناموجود در CRM / Missing Deals');
  lines.push('───────────────────────────────────');
  for (const d of r.missing_deals.slice(0, 50)) {
    lines.push(`  • ${d.name} | 📱 ${d.phone} | درس ${d.lesson || '-'} | ${d.completed ? 'تکمیل' : 'فعال'}`);
  }
  if (r.missing_deals.length > 50) {
    lines.push(`  ... و ${r.missing_deals.length - 50} مورد دیگر`);
  }
}

if (r.stage_mismatches.length > 0) {
  lines.push('');
  lines.push('⚠️ عدم تطابق استیج / Stage Mismatches');
  lines.push('───────────────────────────────────');
  for (const m of r.stage_mismatches.slice(0, 50)) {
    lines.push(`  • ${m.name} | 📱 ${m.phone} | مورد انتظار: ${m.expected_stage} | واقعی: ${m.actual_stage}`);
  }
  if (r.stage_mismatches.length > 50) {
    lines.push(`  ... و ${r.stage_mismatches.length - 50} مورد دیگر`);
  }
}

if (r.status_mismatches.length > 0) {
  lines.push('');
  lines.push('⚠️ عدم تطابق وضعیت دیل / Status Mismatches');
  lines.push('───────────────────────────────────');
  for (const m of r.status_mismatches.slice(0, 50)) {
    lines.push(`  • ${m.name} | 📱 ${m.phone} | مورد انتظار: ${m.expected_status} | واقعی: ${m.actual_status}`);
  }
  if (r.status_mismatches.length > 50) {
    lines.push(`  ... و ${r.status_mismatches.length - 50} مورد دیگر`);
  }
}

if (r.lead_score_mismatches.length > 0) {
  lines.push('');
  lines.push('⚠️ عدم تطابق امتیاز لید / Lead Score Mismatches');
  lines.push('───────────────────────────────────');
  for (const m of r.lead_score_mismatches.slice(0, 50)) {
    lines.push(`  • ${m.name} | 📱 ${m.phone} | ربات: ${m.bot_lead_score} | CRM: ${m.crm_lead_score}`);
  }
  if (r.lead_score_mismatches.length > 50) {
    lines.push(`  ... و ${r.lead_score_mismatches.length - 50} مورد دیگر`);
  }
}

if (r.orphan_deals.length > 0) {
  lines.push('');
  lines.push('👻 دیل‌های یتیم (بدون کاربر ربات) / Orphan Deals');
  lines.push('───────────────────────────────────');
  for (const d of r.orphan_deals.slice(0, 30)) {
    lines.push(`  • ${d.person_name} | ${d.deal_title} | استیج: ${d.stage} | ${d.status}`);
  }
  if (r.orphan_deals.length > 30) {
    lines.push(`  ... و ${r.orphan_deals.length - 30} مورد دیگر`);
  }
}

lines.push('');
lines.push('═══════════════════════════════════');
lines.push(`  تاریخ اجرا: ${new Date().toLocaleString('fa-IR', {timeZone: 'Asia/Tehran'})}`);
lines.push('═══════════════════════════════════');

const reportText = lines.join('\n');

return [{json: {
  report_text: reportText,
  report_data: r,
  generated_at: new Date().toISOString(),
}}];
"""

    add_node({
        "id": "format_report",
        "name": "Format Report",
        "type": "n8n-nodes-base.code",
        "typeVersion": 1,
        "position": [2350, 500],
        "parameters": {"jsCode": format_code, "mode": "runOnceForAllItems"}
    })

    # ═══════════════════════════════════════════════════
    # CONNECTIONS
    # ═══════════════════════════════════════════════════

    connect("Manual Trigger", "Config")
    connect("Config", "Login Bot Panel")
    connect("Login Bot Panel", "Extract Token")
    connect("Extract Token", "Fetch Bot Users")
    connect("Fetch Bot Users", "Extract Bot Users")

    # Deals fetch runs from Extract Bot Users, then straight to Compare
    connect("Extract Bot Users", "Fetch Didar Deals")
    connect("Fetch Didar Deals", "Compare & Audit")
    connect("Compare & Audit", "Format Report")

    # ═══════════════════════════════════════════════════
    # BUILD FINAL WORKFLOW
    # ═══════════════════════════════════════════════════

    workflow = {
        "name": f"CRM Audit — Bot vs Didar ({platform.title()})",
        "nodes": nodes,
        "connections": connections,
        "active": False,
        "settings": {"executionOrder": "v1"},
        "tags": [
            {"name": "course-bot"},
            {"name": "audit"},
            {"name": "didar-crm"},
            {"name": platform}
        ]
    }

    return workflow


if __name__ == "__main__":
    import sys
    platforms = sys.argv[1:] if len(sys.argv) > 1 else ["telegram"]
    base_dir = os.path.dirname(os.path.abspath(__file__))

    for plat in platforms:
        wf = build_workflow(platform=plat)
        out_path = os.path.join(base_dir, f"crm-audit-{plat}.json")
        with open(out_path, "w") as f:
            json.dump(wf, f, indent=2, ensure_ascii=False)
        print(f"[{plat}] Generated audit workflow with {len(wf['nodes'])} nodes → {out_path}")
