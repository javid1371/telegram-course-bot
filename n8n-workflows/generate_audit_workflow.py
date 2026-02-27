#!/usr/bin/env python3
"""Generate n8n workflow for CRM Audit — compares bot data with Didar CRM.

Steps:
1. Login to bot panel → JWT token
2. Fetch all bot users via /api/audit/users
3. Fetch all Didar Persons (paginated)
4. Fetch all Didar Deals in pipeline (paginated)
5. Compare & generate discrepancy report
6. Output report (respond to webhook or manual trigger output)
"""
import json


def build_workflow():
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
    # CONFIG NODE
    # ═══════════════════════════════════════════════════

    config_code = r"""
const CONFIG = {
  // ── Didar CRM ──
  DIDAR_API_KEY: 'YOUR_DIDAR_API_KEY_HERE',
  PIPELINE_ID: 'YOUR_PIPELINE_GUID_HERE',
  COMPANY_ID: '00000000-0000-0000-0000-000000000000',

  // Stages — same GUIDs as main workflow
  STAGES: {
    register: 'STAGE_GUID_HERE',
    lesson_1: 'STAGE_GUID_HERE', lesson_2: 'STAGE_GUID_HERE',
    lesson_3: 'STAGE_GUID_HERE', lesson_4: 'STAGE_GUID_HERE',
    lesson_5: 'STAGE_GUID_HERE', lesson_6: 'STAGE_GUID_HERE',
    lesson_7: 'STAGE_GUID_HERE', lesson_8: 'STAGE_GUID_HERE',
    sales_wait: 'STAGE_GUID_HERE',
    followup_1: 'STAGE_GUID_HERE', followup_2: 'STAGE_GUID_HERE',
    followup_3: 'STAGE_GUID_HERE',
    won: 'STAGE_GUID_HERE'
  },

  CUSTOM_FIELDS: {
    lead_score: 'FIELD_GUID'
  },

  // ── Bot Panel Access ──
  BOT_PANEL_URL: 'http://YOUR_SERVER_IP:8080',
  BOT_ADMIN_USER: 'admin',
  BOT_ADMIN_PASS: 'YOUR_ADMIN_PASS',
};

// Build reverse stage lookup: GUID → stage name
const stageToName = {};
for (const [name, guid] of Object.entries(CONFIG.STAGES)) {
  stageToName[guid] = name;
}
CONFIG._stageToName = stageToName;

// Build lesson_number → stage GUID mapping
const lessonToStage = {};
for (const [name, guid] of Object.entries(CONFIG.STAGES)) {
  const m = name.match(/^lesson_(\d+)$/);
  if (m) lessonToStage[parseInt(m[1])] = guid;
}
CONFIG._lessonToStage = lessonToStage;

return [{json: {CONFIG}}];
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
    # STEP 3: FETCH ALL DIDAR PERSONS
    # ═══════════════════════════════════════════════════

    add_node({
        "id": "fetch_persons",
        "name": "Fetch Didar Persons",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [1750, 400],
        "parameters": {
            "method": "POST",
            "url": "={{ 'https://app.didar.me/api/person/getall?apikey=' + $json.CONFIG.DIDAR_API_KEY }}",
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": "={{ JSON.stringify({From: 0, Limit: 5000}) }}",
            "options": {"timeout": 60000}
        }
    })

    # ═══════════════════════════════════════════════════
    # STEP 4: FETCH ALL DIDAR DEALS IN PIPELINE
    # ═══════════════════════════════════════════════════

    add_node({
        "id": "fetch_deals",
        "name": "Fetch Didar Deals",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [1750, 600],
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
    # STEP 5: COMPARE & AUDIT
    # ═══════════════════════════════════════════════════

    compare_code = r"""
// Gather inputs
const data = $('Extract Bot Users').first().json;
const CONFIG = data.CONFIG;
const botUsers = data.botUsers || [];

const personsResp = $('Fetch Didar Persons').first().json;
const dealsResp = $('Fetch Didar Deals').first().json;

const persons = personsResp?.Response?.List || personsResp?.search_respons?.List || [];
const deals = dealsResp?.Response?.List || dealsResp?.search_respons?.List || [];

// ── Build lookup maps ──

// Normalise phone: remove leading 0, keep last 10 digits
function normalisePhone(raw) {
  if (!raw) return '';
  const digits = String(raw).replace(/\D/g, '');
  if (digits.length >= 10) return digits.slice(-10);
  return digits;
}

// Person lookup by normalised phone
const personByPhone = {};
for (const p of persons) {
  const phones = [p.MobilePhone, p.Phone, p.HomePhone].filter(Boolean);
  for (const ph of phones) {
    const norm = normalisePhone(ph);
    if (norm) personByPhone[norm] = p;
  }
}

// Deal lookup by PersonId (keep first pending deal per person)
const dealByPersonId = {};
for (const d of deals) {
  const pid = d.PersonId || d.ContactId;
  if (!pid) continue;
  // Prefer Pending deals; if multiple, keep first
  if (!dealByPersonId[pid] || d.Status === 'Pending') {
    dealByPersonId[pid] = d;
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
    total_crm_persons: persons.length,
    total_crm_deals: deals.length,
    person_found: 0,
    person_missing: 0,
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
  discrepancies: [],
  missing_persons: [],
  missing_deals: [],
  stage_mismatches: [],
  status_mismatches: [],
  lead_score_mismatches: [],
  orphan_deals: [],
};

const matchedPersonIds = new Set();

for (const user of botUsers) {
  const phone = normalisePhone(user.phone);
  if (!phone) {
    report.summary.users_without_phone++;
    continue;
  }
  report.summary.users_with_phone++;

  const person = personByPhone[phone];
  const issues = [];

  if (!person) {
    report.summary.person_missing++;
    report.missing_persons.push({
      bot_user_id: user.id,
      name: (user.first_name || '') + ' ' + (user.last_name || ''),
      phone: user.phone,
      lesson: user.current_lesson_number,
      completed: user.is_completed,
    });
    continue; // No person → skip deal check
  }

  report.summary.person_found++;
  matchedPersonIds.add(person.Id);

  // Check deal
  const deal = dealByPersonId[person.Id];
  if (!deal) {
    report.summary.deal_missing++;
    report.missing_deals.push({
      bot_user_id: user.id,
      name: (user.first_name || '') + ' ' + (user.last_name || ''),
      phone: user.phone,
      crm_person_id: person.Id,
      lesson: user.current_lesson_number,
      completed: user.is_completed,
    });
    issues.push('deal_missing');
  } else {
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
  }

  // Check lead_score (on Person custom fields)
  const crmLeadScoreField = CONFIG.CUSTOM_FIELDS?.lead_score;
  if (crmLeadScoreField && crmLeadScoreField !== 'FIELD_GUID' && person.Fields) {
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
  const pid = deal.PersonId || deal.ContactId;
  if (pid && !matchedPersonIds.has(pid)) {
    // Check if person's phone matches any bot user
    const person = persons.find(p => p.Id === pid);
    const personPhones = person ? [person.MobilePhone, person.Phone].filter(Boolean).map(normalisePhone) : [];
    const hasMatch = personPhones.some(ph => botPhones.has(ph));
    if (!hasMatch) {
      report.orphan_deals.push({
        deal_id: deal.Id,
        deal_title: deal.Title || '',
        person_id: pid,
        person_name: person ? ((person.FirstName || '') + ' ' + (person.LastName || '')) : 'Unknown',
        stage: stageToName[deal.PipelineStageId] || deal.PipelineStageId,
        status: deal.Status,
      });
    }
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
    # STEP 6: FORMAT REPORT (Persian + English)
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
lines.push(`  پرسن‌های CRM              : ${s.total_crm_persons}`);
lines.push(`  دیل‌های CRM               : ${s.total_crm_deals}`);
lines.push('');
lines.push('🔍 نتایج مقایسه / Comparison Results');
lines.push('───────────────────────────────────');
lines.push(`  ✅ پرسن پیدا شد           : ${s.person_found}`);
lines.push(`  ❌ پرسن ناموجود           : ${s.person_missing}`);
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
if (r.missing_persons.length > 0) {
  lines.push('');
  lines.push('🚫 پرسن ناموجود در CRM / Missing Persons');
  lines.push('───────────────────────────────────');
  for (const p of r.missing_persons.slice(0, 50)) {
    lines.push(`  • ${p.name} | 📱 ${p.phone} | درس ${p.lesson || '-'} | ${p.completed ? 'تکمیل' : 'فعال'}`);
  }
  if (r.missing_persons.length > 50) {
    lines.push(`  ... و ${r.missing_persons.length - 50} مورد دیگر`);
  }
}

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

    # Both Didar fetches run in parallel from Extract Bot Users
    connect("Extract Bot Users", "Fetch Didar Persons")
    connect("Extract Bot Users", "Fetch Didar Deals")

    # Merge node to wait for both Didar fetches before comparison
    add_node({
        "id": "merge",
        "name": "Wait for Both",
        "type": "n8n-nodes-base.merge",
        "typeVersion": 2.1,
        "position": [2000, 500],
        "parameters": {
            "mode": "combine",
            "combinationMode": "mergeByPosition",
            "options": {}
        }
    })

    # Override connections: both Didar results → Merge → Compare
    # Remove old direct connections to Compare
    # Connect Didar results to Merge
    connections["Fetch Didar Persons"] = {"main": [[{"node": "Wait for Both", "type": "main", "index": 0}]]}
    connections["Fetch Didar Deals"] = {"main": [[{"node": "Wait for Both", "type": "main", "index": 1}]]}
    connect("Wait for Both", "Compare & Audit")
    connect("Compare & Audit", "Format Report")

    # ═══════════════════════════════════════════════════
    # BUILD FINAL WORKFLOW
    # ═══════════════════════════════════════════════════

    workflow = {
        "name": "CRM Audit — Bot vs Didar Sync Check",
        "nodes": nodes,
        "connections": connections,
        "active": False,
        "settings": {"executionOrder": "v1"},
        "tags": [
            {"name": "course-bot"},
            {"name": "audit"},
            {"name": "didar-crm"}
        ]
    }

    return workflow


if __name__ == "__main__":
    import os
    wf = build_workflow()
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "crm-audit-workflow.json")
    with open(out_path, "w") as f:
        json.dump(wf, f, indent=2, ensure_ascii=False)
    print(f"Generated audit workflow with {len(wf['nodes'])} nodes → {out_path}")
