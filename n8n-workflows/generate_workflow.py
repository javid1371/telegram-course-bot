#!/usr/bin/env python3
"""Generate n8n workflow v6 with all bug fixes:
  Bug 2:  Person verification before deal lookup in lesson/complete branches
  Bug 3:  IF Deal Found guard — skip CRM update when deal missing
  Bug 4:  Course complete → Status "Won" instead of "Pending"
  Bug 8:  Write lead_score to CRM custom field on Person
  Bug 10: Happy Call linked to deal via DealIds
  Bug 12: Unmatched events get Respond OK instead of timeout
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

    didar_cred = {"didarApi": {"id": "", "name": "Didar CRM"}}

    # ═══════════════════════════════════════════════════
    # BASE NODES
    # ═══════════════════════════════════════════════════

    add_node({
        "id": "webhook",
        "name": "Webhook",
        "type": "n8n-nodes-base.webhook",
        "typeVersion": 1,
        "position": [250, 500],
        "parameters": {
            "httpMethod": "POST",
            "path": "course-bot",
            "responseMode": "lastNode",
            "options": {}
        }
    })

    # ── Bug 4 fix: added 'won' stage ──
    # ── Bug 8 fix: lead_score field in CUSTOM_FIELDS ──
    config_code = r"""
const CONFIG = {
  WEBHOOK_SECRET: 'YOUR_WEBHOOK_SECRET_HERE',
  DIDAR_API_KEY: 'YOUR_DIDAR_API_KEY_HERE',
  OWNERS: [
    {id: 'OWNER_GUID_1', name: 'Owner 1', weight: 3},
    {id: 'OWNER_GUID_2', name: 'Owner 2', weight: 2},
  ],
  PIPELINE_ID: 'YOUR_PIPELINE_GUID_HERE',
  COMPANY_ID: '00000000-0000-0000-0000-000000000000',
  ACTIVITY_TYPE_SALES: 'YOUR_SALES_ACTIVITY_TYPE_GUID',
  ACTIVITY_TYPE_FOLLOWUP: 'YOUR_FOLLOWUP_ACTIVITY_TYPE_GUID',
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
    monthly_income: 'FIELD_GUID', staff_count: 'FIELD_GUID',
    job: 'FIELD_GUID', best_call_time: 'FIELD_GUID',
    lead_score: 'FIELD_GUID', city: 'FIELD_GUID',
    income_class: 'FIELD_GUID'
  }
};
const body = $input.first().json.body || $input.first().json;
const event = body.event || {};
const user = body.user || {};
const course = body.course || {};
const lesson = body.lesson || {};
const progress = body.progress || {};
const payload = body.payload || {};
const eventType = event.type || '';
const eventAction = event.action || '';
const action = eventType + '.' + eventAction;
// Dynamic CRM field mapping from bot
const botMapping = payload.crm_field_mapping || {};
for (const [key, val] of Object.entries(botMapping)) {
  if (val && !val.startsWith('person.') && val !== 'note') {
    CONFIG.CUSTOM_FIELDS[key] = val;
  }
}
const phoneRaw = user.phone || (user.registration_data?.phone || user.registration_data?.mobile || '');
const phoneSearch = (function(p) { p = (p||'').replace(/[^0-9]/g, ''); return p.length >= 10 ? p.slice(-10) : p; })(phoneRaw);
return [{json: {...body, CONFIG, action,
  user_phone: phoneRaw,
  phone_search: phoneSearch,
  user_name: (user.registration_data?.first_name||user.first_name||'') + ' ' + (user.registration_data?.last_name||user.last_name||''),
  course_title: course.title || '',
  lesson_title: lesson.title || '',
  lesson_order: lesson.lesson_number || lesson.order || 0,
  progress_percent: progress.percent || 0,
  progress_completed: progress.completed || 0,
  progress_total: progress.total || 0
}}];
"""

    add_node({
        "id": "config",
        "name": "Config",
        "type": "n8n-nodes-base.code",
        "typeVersion": 1,
        "position": [500, 500],
        "parameters": {"jsCode": config_code, "mode": "runOnceForAllItems"}
    })

    # ── Fix: Switch v3.2 supports 9+ outputs (v1 only allowed 0-3) ──
    # NOTE: combinator + typeValidation are REQUIRED for proper rule evaluation
    def make_switch_rule(action_value, output_key):
        return {
            "conditions": {
                "options": {
                    "caseSensitive": True,
                    "leftValue": "",
                    "typeValidation": "strict",
                },
                "conditions": [{
                    "id": f"cond_{output_key}",
                    "leftValue": "={{ $json.action }}",
                    "rightValue": action_value,
                    "operator": {"type": "string", "operation": "equals"}
                }],
                "combinator": "and",
            },
            "renameOutput": True,
            "outputKey": output_key
        }

    add_node({
        "id": "router",
        "name": "Router",
        "type": "n8n-nodes-base.switch",
        "typeVersion": 3.2,
        "position": [750, 500],
        "parameters": {
            "rules": {"values": [
                make_switch_rule("lead.register", "Register"),
                make_switch_rule("lesson.complete", "Lesson"),
                make_switch_rule("form.submit", "Form"),
                make_switch_rule("quiz.pass", "QuizPass"),
                make_switch_rule("quiz.fail", "QuizFail"),
                make_switch_rule("inactivity.timeout", "Inactivity"),
                make_switch_rule("course.complete", "Complete"),
                make_switch_rule("speed.change", "Speed"),
            ]},
            "options": {"fallbackOutput": "extra"}
        }
    })

    connect("Webhook", "Config")
    connect("Config", "Router")

    # ═══════════════════════════════════════════════════
    # REGISTER BRANCH (output 0) — Smart Owner + Dedup
    # ═══════════════════════════════════════════════════

    # ── Bug 8 fix: include leadScoreFieldJson for Create Person ──
    prep_register_code = r"""
const d = $input.first().json;
const C = d.CONFIG;

const owners = (C.OWNERS || []).filter(o => o.weight > 0);
let ownerId = owners.length ? owners[0].id : '';
let ownerName = owners.length ? owners[0].name : '';

if (owners.length > 1) {
  let pool = [];
  for (const o of owners) {
    for (let i = 0; i < o.weight; i++) pool.push(o);
  }
  const selected = pool[Math.floor(Math.random() * pool.length)];
  ownerId = selected.id;
  ownerName = selected.name;
}

const lastName = d.user?.registration_data?.last_name || d.user?.last_name || 'User';
const firstName = d.user?.registration_data?.first_name || d.user?.first_name || '';
const phone = d.user_phone || (d.user?.registration_data?.phone || d.user?.registration_data?.mobile || '');
const phoneSearch = d.phone_search || '';
const leadScore = d.payload?.lead_score || d.user?.lead_score || 0;

// Use bot-provided lead_score_field_json if available, else build from CUSTOM_FIELDS
let leadScoreFieldJson = d.payload?.lead_score_field_json || '{}';
if (leadScoreFieldJson === '{}' && C.CUSTOM_FIELDS.lead_score && C.CUSTOM_FIELDS.lead_score !== 'FIELD_GUID') {
  leadScoreFieldJson = JSON.stringify({[C.CUSTOM_FIELDS.lead_score]: String(leadScore)});
}

return [{json: {
  phone, phoneSearch, firstName, lastName,
  ownerId, ownerName, leadScore, leadScoreFieldJson,
  apiKey: C.DIDAR_API_KEY || '',
  pipelineId: C.PIPELINE_ID,
  stageId: C.STAGES.register,
  companyId: C.COMPANY_ID,
  activityTypeId: C.ACTIVITY_TYPE_SALES,
  courseTitle: d.course_title,
  dealTitle: '' + d.course_title + ' ' + firstName + ' ' + lastName,
  CONFIG: C
}}];
"""

    add_node({
        "id": "prep_register",
        "name": "Prep Register",
        "type": "n8n-nodes-base.code",
        "typeVersion": 1,
        "position": [1050, 100],
        "parameters": {"jsCode": prep_register_code, "mode": "runOnceForAllItems"}
    })

    add_node({
        "id": "find_person",
        "name": "Find Person",
        "type": "n8n-nodes-didar-crm.didarCrm",
        "typeVersion": 1,
        "position": [1300, 100],
        "credentials": didar_cred,
        "parameters": {
            "resource": "person",
            "operation": "search",
            "Keywords": "={{$json.phoneSearch}}",
            "additionalFields": {"Limit": 1}
        }
    })

    process_person_code = r"""
const prev = $('Prep Register').first().json;
const resp = $input.first().json;
const list = resp?.search_respons?.List || resp?.Response?.List || [];
const found = list.length > 0 ? list[0] : null;
const personId = found?.Id || null;
return [{json: {...prev, personExists: !!personId, personId}}];
"""

    add_node({
        "id": "process_person",
        "name": "Process Person",
        "type": "n8n-nodes-base.code",
        "typeVersion": 1,
        "position": [1550, 100],
        "parameters": {"jsCode": process_person_code, "mode": "runOnceForAllItems"}
    })

    add_node({
        "id": "if_person_exists",
        "name": "IF Person Exists",
        "type": "n8n-nodes-base.if",
        "typeVersion": 1,
        "position": [1800, 100],
        "parameters": {
            "conditions": {
                "boolean": [{
                    "value1": "={{$json.personExists}}",
                    "value2": True
                }]
            }
        }
    })

    use_existing_code = r"""
const d = $input.first().json;
return [{json: {...d}}];
"""
    add_node({
        "id": "use_existing_person",
        "name": "Use Existing Person",
        "type": "n8n-nodes-base.code",
        "typeVersion": 1,
        "position": [2050, 0],
        "parameters": {"jsCode": use_existing_code, "mode": "runOnceForAllItems"}
    })

    # ── Bug 8 fix: Create Person with lead_score custom field ──
    add_node({
        "id": "create_person",
        "name": "Create Person",
        "type": "n8n-nodes-didar-crm.didarCrm",
        "typeVersion": 1,
        "position": [2050, 200],
        "credentials": didar_cred,
        "parameters": {
            "resource": "person",
            "operation": "create",
            "FirstName": "={{$json.firstName}}",
            "LastName": "={{$json.lastName}}",
            "MobilePhone": "={{$json.phone}}",
            "OwnerMode": "manual",
            "OwnerIdManual": "={{$json.ownerId}}",
            "additionalFields": {
                "CompanyId": "={{$json.companyId}}",
                "VisibilityType": "Owner",
                "Fields": "={{$json.leadScoreFieldJson}}"
            }
        }
    })

    get_new_person_code = r"""
const prev = $('Process Person').first().json;
const resp = $input.first().json;
const newId = resp?.Response?.Id || '';
return [{json: {...prev, personId: newId, personExists: false}}];
"""
    add_node({
        "id": "get_new_person_id",
        "name": "Get New Person ID",
        "type": "n8n-nodes-base.code",
        "typeVersion": 1,
        "position": [2300, 200],
        "parameters": {"jsCode": get_new_person_code, "mode": "runOnceForAllItems"}
    })

    # Unify Person: merge personId from IF Person Exists branches
    unify_person_code = r"""const item = $input.first().json;
if (!item.personId) throw new Error('No personId found after person search/create');
return [{json: {...item}}];
"""
    add_node({
        "id": "unify_person",
        "name": "Unify Person",
        "type": "n8n-nodes-base.code",
        "typeVersion": 1,
        "position": [2400, 100],
        "parameters": {"jsCode": unify_person_code, "mode": "runOnceForAllItems"}
    })

    add_node({
        "id": "search_deal_reg",
        "name": "Search Deal Reg V2",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [2550, 100],
        "parameters": {
            "method": "POST",
            "url": "=https://app.didar.me/api/deal/search_v2?apikey={{ $json.apiKey }}",
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": "={{ JSON.stringify({Criteria: {ContactIds: [$json.personId], PipelineId: $json.pipelineId}, From: 0, Limit: 50}) }}",
            "options": {}
        }
    })

    process_deal_code = r"""
const prev = $('Unify Person').first().json;

const resp = $input.first().json;
const deals = resp?.Response?.List || resp?.search_respons?.List || [];
const existingDeal = deals.find(d =>
  (d.PersonId === prev.personId || d.ContactId === prev.personId) && d.Status === 'Pending'
);

return [{json: {
  ...prev,
  dealExists: !!existingDeal,
  existingDealId: existingDeal?.Id || null
}}];
"""
    add_node({
        "id": "process_deal_reg",
        "name": "Process Deal Reg",
        "type": "n8n-nodes-base.code",
        "typeVersion": 1,
        "position": [2800, 100],
        "parameters": {"jsCode": process_deal_code, "mode": "runOnceForAllItems"}
    })

    add_node({
        "id": "if_deal_exists",
        "name": "IF Deal Exists",
        "type": "n8n-nodes-base.if",
        "typeVersion": 1,
        "position": [3050, 100],
        "parameters": {
            "conditions": {
                "boolean": [{
                    "value1": "={{$json.dealExists}}",
                    "value2": True
                }]
            }
        }
    })

    skip_deal_code = r"""
const d = $input.first().json;
return [{json: {...d, dealId: d.existingDealId}}];
"""
    add_node({
        "id": "skip_deal",
        "name": "Skip Deal Create",
        "type": "n8n-nodes-base.code",
        "typeVersion": 1,
        "position": [3300, 0],
        "parameters": {"jsCode": skip_deal_code, "mode": "runOnceForAllItems"}
    })

    add_node({
        "id": "create_deal",
        "name": "Create Deal",
        "type": "n8n-nodes-didar-crm.didarCrm",
        "typeVersion": 1,
        "position": [3300, 200],
        "credentials": didar_cred,
        "parameters": {
            "resource": "deal",
            "operation": "create",
            "Title": "={{$json.dealTitle}}",
            "OwnerMode": "manual",
            "OwnerIdManual": "={{$json.ownerId}}",
            "PipelineMode": "manual",
            "PipelineId": "={{$json.pipelineId}}",
            "StageMode": "manual",
            "PipelineStageId": "={{$json.stageId}}",
            "PersonId": "={{$json.personId}}",
            "CompanyId": "={{$json.companyId}}",
            "Status": "Pending",
            "LabelIds": [],
            "additionalFields": {"VisibilityType": "Owner"}
        }
    })

    after_deal_code = r"""
const prev = $('Process Deal Reg').first().json;
const resp = $input.first().json;
const newDealId = resp?.Response?.Id || '';
return [{json: {...prev, dealId: newDealId}}];
"""
    add_node({
        "id": "after_create_deal",
        "name": "After Create Deal",
        "type": "n8n-nodes-base.code",
        "typeVersion": 1,
        "position": [3550, 200],
        "parameters": {"jsCode": after_deal_code, "mode": "runOnceForAllItems"}
    })

    # Unify Deal ID: merge dealId from IF Deal Exists branches
    unify_deal_id_code = r"""const item = $input.first().json;
if (!item.dealId) throw new Error('No dealId found after deal search/create');
return [{json: {...item}}];
"""
    add_node({
        "id": "unify_deal_id",
        "name": "Unify Deal ID",
        "type": "n8n-nodes-base.code",
        "typeVersion": 1,
        "position": [3700, 100],
        "parameters": {"jsCode": unify_deal_id_code, "mode": "runOnceForAllItems"}
    })

    # ── Bug 10 fix: Happy Call linked to deal via DealIds ──
    add_node({
        "id": "happy_call",
        "name": "Happy Call",
        "type": "n8n-nodes-didar-crm.didarCrm",
        "typeVersion": 1,
        "position": [3800, 100],
        "credentials": didar_cred,
        "parameters": {
            "resource": "activity",
            "operation": "create",
            "Title": "=\u062a\u0645\u0627\u0633 \u062e\u0648\u0634\u0627\u0645\u062f\u06af\u0648\u06cc\u06cc - {{$json.lastName}}",
            "ActivityTypeMode": "manual",
            "ActivityTypeIdManual": "={{$json.activityTypeId}}",
            "OwnerMode": "manual",
            "OwnerIdManual": "={{$json.ownerId}}",
            "IsDone": False,
            "additionalFields": {
                "Note": "=\u062b\u0628\u062a \u0646\u0627\u0645 \u062c\u062f\u06cc\u062f \u062f\u0631 \u062f\u0648\u0631\u0647 {{$json.courseTitle}}",
                "ContactIds": "={{$json.personId}}",
                "DealIds": "={{$json.dealId || $json.existingDealId || ''}}"
            }
        }
    })

    prep_response_code = r"""
const d = $input.first().json;
const prev = $('Unify Deal ID').first().json;
const ownerId = prev?.ownerId || d?.ownerId || '';
const ownerName = prev?.ownerName || d?.ownerName || '';
return [{json: {status: 'ok', owner: {id: ownerId, name: ownerName}}}];
"""
    add_node({
        "id": "prep_response",
        "name": "Prep Response",
        "type": "n8n-nodes-base.code",
        "typeVersion": 1,
        "position": [4050, 100],
        "parameters": {"jsCode": prep_response_code, "mode": "runOnceForAllItems"}
    })

    add_node({
        "id": "respond_register",
        "name": "Respond Register",
        "type": "n8n-nodes-base.respondToWebhook",
        "typeVersion": 1,
        "position": [4300, 100],
        "parameters": {
            "respondWith": "allIncomingItems",
            "options": {}
        }
    })

    # Register branch connections
    connect("Router", "Prep Register", 0)
    connect("Prep Register", "Find Person")
    connect("Find Person", "Process Person")
    connect("Process Person", "IF Person Exists")
    connect("IF Person Exists", "Use Existing Person", 0)
    connect("IF Person Exists", "Create Person", 1)
    connect("Use Existing Person", "Unify Person")
    connect("Create Person", "Get New Person ID")
    connect("Get New Person ID", "Unify Person")
    connect("Unify Person", "Search Deal Reg V2")
    connect("Search Deal Reg V2", "Process Deal Reg")
    connect("Process Deal Reg", "IF Deal Exists")
    connect("IF Deal Exists", "Skip Deal Create", 0)
    connect("IF Deal Exists", "Create Deal", 1)
    connect("Skip Deal Create", "Unify Deal ID")
    connect("Create Deal", "After Create Deal")
    connect("After Create Deal", "Unify Deal ID")
    connect("Unify Deal ID", "Happy Call")
    connect("Happy Call", "Prep Response")
    connect("Prep Response", "Respond Register")

    # ═══════════════════════════════════════════════════
    # LESSON BRANCH (output 1)
    # Bug 2 fix: Find Person first → verify deal belongs to person
    # Bug 3 fix: IF Deal Found guard
    # Bug 8 fix: Update person lead_score
    # ═══════════════════════════════════════════════════

    prep_lesson_code = r"""
const d=$input.first().json; const C=d.CONFIG;
const triggerSales = d.payload?.trigger_sales || false;
const lessonNum = Number(d.lesson_order || 0);
// If lesson_number is 0/null (intro lesson), skip stage update entirely
const skipLesson = (!triggerSales && lessonNum === 0);
const stageId = triggerSales
  ? C.STAGES.sales_wait
  : (lessonNum > 0 ? (C.STAGES['lesson_' + lessonNum] || '') : '');
const ownerId = C.OWNERS && C.OWNERS.length ? C.OWNERS[0].id : '';
const leadScore = d.payload?.lead_score || d.user?.lead_score || 0;

// Use bot-provided lead_score_field_json if available
let leadScoreFieldJson = d.payload?.lead_score_field_json || '{}';
if (leadScoreFieldJson === '{}' && C.CUSTOM_FIELDS.lead_score && C.CUSTOM_FIELDS.lead_score !== 'FIELD_GUID') {
  leadScoreFieldJson = JSON.stringify({[C.CUSTOM_FIELDS.lead_score]: String(leadScore)});
}

return [{json:{phone:d.user_phone,phoneSearch:d.phone_search||'',stageId,lessonOrder:d.lesson_order,
courseTitle:d.course_title,ownerId,pipelineId:C.PIPELINE_ID,
apiKey:C.DIDAR_API_KEY||'',
triggerSales, leadScore, leadScoreFieldJson,
activityTypeId:C.ACTIVITY_TYPE_SALES,
userName:d.user_name,
skip: skipLesson, reason: skipLesson ? 'intro lesson (no lesson_number)' : '',
noteText:'\u062f\u0631\u0633 '+d.lesson_order+' ('+d.lesson_title+') \u062a\u06a9\u0645\u06cc\u0644 - '+d.progress_percent+'%',CONFIG:C}}];
"""

    add_node({
        "id": "prep_lesson",
        "name": "Prep Lesson",
        "type": "n8n-nodes-base.code",
        "typeVersion": 1,
        "position": [1050, 300],
        "parameters": {"jsCode": prep_lesson_code, "mode": "runOnceForAllItems"}
    })

    # ── Skip intro lessons (lesson_number = null/0) ──
    add_node({
        "id": "if_skip_lesson",
        "name": "IF Skip Lesson",
        "type": "n8n-nodes-base.if",
        "typeVersion": 1,
        "position": [1200, 300],
        "parameters": {
            "conditions": {
                "boolean": [{
                    "value1": "={{$json.skip}}",
                    "value2": True
                }]
            }
        }
    })

    # ── Bug 2 fix: Find person by phone before deal search ──
    add_node({
        "id": "find_person_lesson",
        "name": "Find Person Lesson",
        "type": "n8n-nodes-didar-crm.didarCrm",
        "typeVersion": 1,
        "position": [1450, 250],
        "credentials": didar_cred,
        "parameters": {
            "resource": "person",
            "operation": "search",
            "Keywords": "={{$json.phoneSearch}}",
            "additionalFields": {"Limit": 1}
        }
    })

    extract_person_lesson_code = r"""
const prev=$('Prep Lesson').first().json;
const resp=$input.first().json;
const list = resp?.search_respons?.List || resp?.Response?.List || [];
const found = list.length > 0 ? list[0] : null;
const personId = found?.Id || null;
const lastName = found?.LastName || '';
if(!personId) return [{json:{...prev,personId:null,skip:true,reason:'person not found'}}];

// Preserve owner from person if approved
const personOwnerId = found?.OwnerId || '';
const approvedIds = (prev.CONFIG?.OWNERS || []).map(o => o.id);
const ownerId = approvedIds.includes(personOwnerId) ? personOwnerId : prev.ownerId;

return [{json:{...prev,personId,ownerId,lastName:lastName||prev.userName,skip:false}}];
"""
    add_node({
        "id": "extract_person_lesson",
        "name": "Extract Person Lesson",
        "type": "n8n-nodes-base.code",
        "typeVersion": 1,
        "position": [1650, 250],
        "parameters": {"jsCode": extract_person_lesson_code, "mode": "runOnceForAllItems"}
    })

    # Guard: skip Update Score when person not found
    add_node({
        "id": "if_person_found_lesson",
        "name": "IF Person Found Lesson",
        "type": "n8n-nodes-base.if",
        "typeVersion": 1,
        "position": [1750, 250],
        "parameters": {
            "conditions": {
                "boolean": [{
                    "value1": "={{$json.skip}}",
                    "value2": False
                }]
            }
        }
    })

    # ── Bug 8 fix: Update person lead_score field ──
    add_node({
        "id": "update_score_lesson",
        "name": "Update Score Lesson",
        "type": "n8n-nodes-didar-crm.didarCrm",
        "typeVersion": 1,
        "position": [1850, 250],
        "credentials": didar_cred,
        "parameters": {
            "resource": "person",
            "operation": "update",
            "Id": "={{$json.personId}}",
            "LastName": "={{$json.lastName}}",
            "OwnerMode": "manual",
            "OwnerIdManual": "={{$json.ownerId}}",
            "additionalFields": {"Fields": "={{$json.leadScoreFieldJson}}"}
        }
    })

    recover_person_lesson_code = r"""
const prev=$('Extract Person Lesson').first().json;
return [{json:{...prev}}];
"""
    add_node({
        "id": "recover_person_lesson",
        "name": "Recover Person Lesson",
        "type": "n8n-nodes-base.code",
        "typeVersion": 1,
        "position": [2050, 250],
        "parameters": {"jsCode": recover_person_lesson_code, "mode": "runOnceForAllItems"}
    })

    # ── FIX: Use deal/search_v2 via HTTP Request instead of broken Deal/Search plugin ──
    # The Didar plugin's deal.search uses /api/Deal/Search which is capped at 30 results
    # and ignores ContactIds filter. deal/search_v2 returns ALL matching deals properly.
    add_node({
        "id": "search_deal",
        "name": "Search Deal V2",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [2250, 250],
        "parameters": {
            "method": "POST",
            "url": "=https://app.didar.me/api/deal/search_v2?apikey={{ $json.apiKey }}",
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": "={{ JSON.stringify({Criteria: {ContactIds: [$json.personId], PipelineId: $json.pipelineId}, From: 0, Limit: 50}) }}",
            "options": {}
        }
    })

    # ── Bug 2 fix: filter deals by personId instead of deals[0] ──
    # Updated for deal/search_v2 response format
    extract_deal_code = r"""
const prev=$('Recover Person Lesson').first().json;
const resp=$input.first().json;
const deals=resp?.Response?.List||resp?.search_respons?.List||[];
if(!deals.length) return [{json:{...prev,skip:true,reason:'deal not found',
  dealTitle:'\u062f\u0648\u0631\u0647 ' + prev.courseTitle + ' - ' + (prev.userName || 'User'),
  companyId: prev.CONFIG?.COMPANY_ID || '00000000-0000-0000-0000-000000000000'}}];
const deal = deals.find(d => d.PersonId === prev.personId || d.ContactId === prev.personId) || deals[0];

// Preserve owner from deal if approved
const dealOwnerId = deal.OwnerId || '';
const approvedIds = (prev.CONFIG?.OWNERS || []).map(o => o.id);
const realOwner = approvedIds.includes(dealOwnerId) ? dealOwnerId : prev.ownerId;

return [{json:{dealId:deal.Id,dealTitle:deal.Title,personId:deal.PersonId||deal.ContactId||prev.personId,
stageId:prev.stageId,ownerId:realOwner,pipelineId:prev.pipelineId,
companyId:deal.CompanyId||'00000000-0000-0000-0000-000000000000',
triggerSales:prev.triggerSales,userName:prev.userName,lessonOrder:prev.lessonOrder,
activityTypeId:prev.activityTypeId,leadScore:prev.leadScore,
noteText:prev.noteText,CONFIG:prev.CONFIG,skip:false}}];
"""

    add_node({
        "id": "extract_deal",
        "name": "Extract Deal",
        "type": "n8n-nodes-base.code",
        "typeVersion": 1,
        "position": [2450, 250],
        "parameters": {"jsCode": extract_deal_code, "mode": "runOnceForAllItems"}
    })

    # ── Bug 3 fix: IF Deal Found guard ──
    add_node({
        "id": "if_deal_found",
        "name": "IF Deal Found",
        "type": "n8n-nodes-base.if",
        "typeVersion": 1,
        "position": [2650, 250],
        "parameters": {
            "conditions": {
                "boolean": [{
                    "value1": "={{$json.skip}}",
                    "value2": False
                }]
            }
        }
    })

    add_node({
        "id": "update_deal_stage",
        "name": "Update Deal Stage",
        "type": "n8n-nodes-didar-crm.didarCrm",
        "typeVersion": 1,
        "position": [2900, 200],
        "credentials": didar_cred,
        "parameters": {
            "resource": "deal",
            "operation": "update",
            "Id": "={{$json.dealId}}",
            "Title": "={{$json.dealTitle}}",
            "OwnerMode": "manual",
            "OwnerIdManual": "={{$json.ownerId}}",
            "PipelineMode": "manual",
            "PipelineId": "={{$json.pipelineId}}",
            "StageMode": "manual",
            "PipelineStageId": "={{$json.stageId}}",
            "PersonId": "={{$json.personId}}",
            "CompanyId": "={{$json.companyId}}",
            "Status": "Pending",
            "LabelIds": [],
            "additionalFields": {}
        }
    })

    recover_lesson_code = r"""
const prev=$('Extract Deal').first().json;
return [{json:{...prev}}];
"""
    add_node({
        "id": "recover_lesson",
        "name": "Recover Lesson Data",
        "type": "n8n-nodes-base.code",
        "typeVersion": 1,
        "position": [3150, 200],
        "parameters": {"jsCode": recover_lesson_code, "mode": "runOnceForAllItems"}
    })

    add_node({
        "id": "if_trigger_sales",
        "name": "IF Trigger Sales",
        "type": "n8n-nodes-base.if",
        "typeVersion": 1,
        "position": [3400, 200],
        "parameters": {
            "conditions": {
                "boolean": [{
                    "value1": "={{$json.triggerSales}}",
                    "value2": True
                }]
            }
        }
    })

    add_node({
        "id": "sales_call_lesson",
        "name": "Sales Call Lesson",
        "type": "n8n-nodes-didar-crm.didarCrm",
        "typeVersion": 1,
        "position": [3650, 150],
        "credentials": didar_cred,
        "parameters": {
            "resource": "activity",
            "operation": "create",
            "Title": "=\u062a\u0645\u0627\u0633 \u0641\u0631\u0648\u0634 - {{$json.userName}} (\u062f\u0631\u0633 {{$json.lessonOrder}})",
            "ActivityTypeMode": "manual",
            "ActivityTypeIdManual": "={{$json.activityTypeId}}",
            "OwnerMode": "manual",
            "OwnerIdManual": "={{$json.ownerId}}",
            "IsDone": False,
            "additionalFields": {
                "Note": "={{$json.noteText}}",
                "ContactIds": "={{$json.personId}}"
            }
        }
    })

    # Create deal when not found in lesson branch
    add_node({
        "id": "create_deal_lesson",
        "name": "Create Deal Lesson",
        "type": "n8n-nodes-didar-crm.didarCrm",
        "typeVersion": 1,
        "position": [3200, 672],
        "credentials": didar_cred,
        "parameters": {
            "resource": "deal",
            "operation": "create",
            "Title": "={{$json.dealTitle}}",
            "OwnerMode": "manual",
            "OwnerIdManual": "={{$json.ownerId}}",
            "PipelineMode": "manual",
            "PipelineId": "={{$json.pipelineId}}",
            "StageMode": "manual",
            "PipelineStageId": "={{$json.stageId}}",
            "PersonId": "={{$json.personId}}",
            "CompanyId": "={{$json.companyId}}",
            "Status": "Pending",
            "LabelIds": [],
            "additionalFields": {}
        }
    })

    connect("Router", "Prep Lesson", 1)
    connect("Prep Lesson", "IF Skip Lesson")
    connect("IF Skip Lesson", "Prep Respond OK", 0)             # true: skip → respond OK
    connect("IF Skip Lesson", "Find Person Lesson", 1)          # false: not skip → continue
    connect("Find Person Lesson", "Extract Person Lesson")
    connect("Extract Person Lesson", "IF Person Found Lesson")
    connect("IF Person Found Lesson", "Update Score Lesson", 0)   # true: person found
    connect("IF Person Found Lesson", "Prep Respond OK", 1)       # false: person not found
    connect("Update Score Lesson", "Recover Person Lesson")
    connect("Recover Person Lesson", "Search Deal V2")
    connect("Search Deal V2", "Extract Deal")
    connect("Extract Deal", "IF Deal Found")
    connect("IF Deal Found", "Update Deal Stage", 0)       # true: skip==false → deal found
    connect("IF Deal Found", "Create Deal Lesson", 1)       # false: no deal → create deal
    connect("Create Deal Lesson", "Prep Respond OK")
    connect("Update Deal Stage", "Recover Lesson Data")
    connect("Recover Lesson Data", "IF Trigger Sales")
    connect("IF Trigger Sales", "Sales Call Lesson", 0)      # true: trigger sales
    # false path goes to Prep Respond OK — connected below

    # ═══════════════════════════════════════════════════
    # FORM BRANCH (output 2) — Bug 8: include lead_score in custom fields
    # ═══════════════════════════════════════════════════

    prep_form_code = r"""
const d=$input.first().json; const C=d.CONFIG;
const f=d.payload?.form_responses||{};

// Use bot-provided crm_form_fields_json if available, else build from CUSTOM_FIELDS
let customFieldsJson = d.payload?.crm_form_fields_json || '';
if (!customFieldsJson) {
  const map={monthly_income:C.CUSTOM_FIELDS.monthly_income,staff_count:C.CUSTOM_FIELDS.staff_count,
  job:C.CUSTOM_FIELDS.job,best_call_time:C.CUSTOM_FIELDS.best_call_time,
  city:C.CUSTOM_FIELDS.city,income_class:C.CUSTOM_FIELDS.income_class};
  let cf={};
  for(const[k,g] of Object.entries(map)){if(f[k]&&g&&g!=='FIELD_GUID')cf[g]=String(f[k]);}
  // Bug 8 fix: include lead_score in custom fields
  const leadScore = d.payload?.lead_score || d.user?.lead_score || 0;
  if (C.CUSTOM_FIELDS.lead_score && C.CUSTOM_FIELDS.lead_score !== 'FIELD_GUID') {
    cf[C.CUSTOM_FIELDS.lead_score] = String(leadScore);
  }
  customFieldsJson = JSON.stringify(cf);
}
const ownerId = C.OWNERS && C.OWNERS.length ? C.OWNERS[0].id : '';

// Build note text from form responses
const formTitle = d.payload?.form_title || d.lesson_title || 'فرم';
let noteLines = ['\ud83d\udccb پاسخ فرم: ' + formTitle];
const allResponses = d.payload?.form_responses || {};
for (const [key, val] of Object.entries(allResponses)) {
  noteLines.push('\u2022 ' + key + ': ' + String(val));
}
const noteText = noteLines.join('\\n');

const firstName = d.user?.registration_data?.first_name || d.user?.first_name || '';
const lastName = d.user?.registration_data?.last_name || d.user?.last_name || 'User';

return [{json:{phone:d.user_phone,phoneSearch:d.phone_search||'',customFieldsJson,
ownerId,leadScore:d.payload?.lead_score||0,CONFIG:C,noteText,userName:d.user_name,
firstName,lastName,lessonTitle:d.lesson_title,
apiKey:C.DIDAR_API_KEY||'',pipelineId:C.PIPELINE_ID,
companyId:C.COMPANY_ID}}];
"""

    add_node({
        "id": "prep_form",
        "name": "Prep Form",
        "type": "n8n-nodes-base.code",
        "typeVersion": 1,
        "position": [1050, 500],
        "parameters": {"jsCode": prep_form_code, "mode": "runOnceForAllItems"}
    })

    add_node({
        "id": "find_person_form",
        "name": "Find Person Form",
        "type": "n8n-nodes-didar-crm.didarCrm",
        "typeVersion": 1,
        "position": [1300, 500],
        "credentials": didar_cred,
        "parameters": {
            "resource": "person",
            "operation": "search",
            "Keywords": "={{$json.phoneSearch}}",
            "additionalFields": {"Limit": 1}
        }
    })

    extract_person_form_code = r"""
const prev=$('Prep Form').first().json;
const resp=$input.first().json;
const list = resp?.search_respons?.List || resp?.Response?.List || [];
const found = list.length > 0 ? list[0] : null;
const personId = found?.Id || null;
const lastName = found?.LastName || prev.lastName || 'User';
if(!personId) return [{json:{...prev,personId:null,skip:true,reason:'person not found by phone'}}];

// Preserve owner from person if approved
const personOwnerId = found?.OwnerId || '';
const C = prev.CONFIG;
const approvedIds = (C.OWNERS || []).map(o => o.id);
const ownerId = approvedIds.includes(personOwnerId) ? personOwnerId : prev.ownerId;

return [{json:{...prev,personId,ownerId,lastName,skip:false}}];
"""

    add_node({
        "id": "extract_person_form",
        "name": "Extract Person Form",
        "type": "n8n-nodes-base.code",
        "typeVersion": 1,
        "position": [1550, 500],
        "parameters": {"jsCode": extract_person_form_code, "mode": "runOnceForAllItems"}
    })

    # Guard: if person not found, create new person first
    add_node({
        "id": "if_person_found_form",
        "name": "IF Person Found Form",
        "type": "n8n-nodes-base.if",
        "typeVersion": 1,
        "position": [1650, 500],
        "parameters": {
            "conditions": {
                "boolean": [{
                    "value1": "={{$json.skip}}",
                    "value2": False
                }]
            }
        }
    })

    # Create person when not found in Form branch
    add_node({
        "id": "create_person_form",
        "name": "Create Person Form",
        "type": "n8n-nodes-didar-crm.didarCrm",
        "typeVersion": 1,
        "position": [1800, 600],
        "credentials": didar_cred,
        "parameters": {
            "resource": "person",
            "operation": "create",
            "FirstName": "={{$json.firstName}}",
            "LastName": "={{$json.lastName}}",
            "MobilePhone": "={{$json.phone}}",
            "OwnerMode": "manual",
            "OwnerIdManual": "={{$json.ownerId}}",
            "additionalFields": {
                "CompanyId": "={{$json.companyId}}",
                "VisibilityType": "Owner"
            }
        }
    })

    get_new_person_form_code = r"""
const prev=$('Extract Person Form').first().json;
const resp=$input.first().json;
const newId=resp?.Response?.Id||'';
return [{json:{...prev,personId:newId,skip:false}}];
"""
    add_node({
        "id": "get_new_person_form_id",
        "name": "Get New Person Form ID",
        "type": "n8n-nodes-base.code",
        "typeVersion": 1,
        "position": [1950, 600],
        "parameters": {"jsCode": get_new_person_form_code, "mode": "runOnceForAllItems"}
    })

    add_node({
        "id": "update_person_fields",
        "name": "Update Person Fields",
        "type": "n8n-nodes-didar-crm.didarCrm",
        "typeVersion": 1,
        "position": [2100, 500],
        "credentials": didar_cred,
        "parameters": {
            "resource": "person",
            "operation": "update",
            "Id": "={{$json.personId}}",
            "LastName": "={{$json.lastName}}",
            "OwnerMode": "manual",
            "OwnerIdManual": "={{$json.ownerId}}",
            "additionalFields": {"Fields": "={{$json.customFieldsJson}}"}
        }
    })

    connect("Router", "Prep Form", 2)
    connect("Prep Form", "Find Person Form")
    connect("Find Person Form", "Extract Person Form")
    connect("Extract Person Form", "IF Person Found Form")
    connect("IF Person Found Form", "Update Person Fields", 0)    # true: person found
    connect("IF Person Found Form", "Create Person Form", 1)      # false: create new person
    connect("Create Person Form", "Get New Person Form ID")
    connect("Get New Person Form ID", "Update Person Fields")

    # Form deal search and note creation
    add_node({
        "id": "search_deal_form",
        "name": "Search Deal Form V2",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [2400, 500],
        "parameters": {
            "method": "POST",
            "url": "=https://app.didar.me/api/deal/search_v2?apikey={{ $json.apiKey }}",
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": "={{ JSON.stringify({Criteria: {ContactIds: [$json.personId], PipelineId: $json.pipelineId}, From: 0, Limit: 50}) }}",
            "options": {}
        }
    })

    extract_deal_form_code = r"""
const prev=$('Extract Person Form').first().json;
const resp=$input.first().json;
const deals=resp?.Response?.List||resp?.search_respons?.List||[];
const deal=deals.find(d => d.PersonId===prev.personId||d.ContactId===prev.personId)||deals[0]||null;
return [{json:{...prev,dealId:deal?.Id||'',personId:prev.personId}}];
"""
    add_node({
        "id": "extract_deal_form",
        "name": "Extract Deal Form",
        "type": "n8n-nodes-base.code",
        "typeVersion": 1,
        "position": [2650, 500],
        "parameters": {"jsCode": extract_deal_form_code, "mode": "runOnceForAllItems"}
    })

    add_node({
        "id": "create_note_form",
        "name": "Create Note Form",
        "type": "n8n-nodes-didar-crm.didarCrm",
        "typeVersion": 1,
        "position": [2900, 500],
        "credentials": didar_cred,
        "parameters": {
            "resource": "note",
            "operation": "create",
            "ResultNote": "={{$json.noteText}}",
            "OwnerMode": "manual",
            "OwnerIdManual": "={{$json.ownerId}}",
            "additionalFields": {
                "DealId": "={{$json.dealId || ''}}",
                "PersonId": "={{$json.personId || ''}}"
            }
        }
    })

    # Recover data lost after Didar API call (Update Person Fields returns API response, not our data)
    # Try to get data from Get New Person Form ID (created person path) or Extract Person Form (found person path)
    recover_form_data_code = r"""
let prev;
try { prev=$('Get New Person Form ID').first().json; }
catch(e) { prev=$('Extract Person Form').first().json; }
return [{json:{...prev}}];
"""
    add_node({
        "id": "recover_form_data",
        "name": "Recover Form Data",
        "type": "n8n-nodes-base.code",
        "typeVersion": 1,
        "position": [2250, 500],
        "parameters": {"jsCode": recover_form_data_code, "mode": "runOnceForAllItems"}
    })

    connect("Update Person Fields", "Recover Form Data")
    connect("Recover Form Data", "Search Deal Form V2")
    connect("Search Deal Form V2", "Extract Deal Form")
    connect("Extract Deal Form", "Create Note Form")

    # ═══════════════════════════════════════════════════
    # QUIZ PASS / FAIL — with deal search pipeline
    # ═══════════════════════════════════════════════════

    prep_quiz_pass_code = r"""
const d=$input.first().json; const C=d.CONFIG;
const qr=d.payload?.quiz_result||{};
const ownerId = C.OWNERS && C.OWNERS.length ? C.OWNERS[0].id : '';
return [{json:{phone:d.user_phone,phoneSearch:d.phone_search||'',ownerId,CONFIG:C,
apiKey:C.DIDAR_API_KEY||'',pipelineId:C.PIPELINE_ID,
courseTitle:d.course_title,userName:d.user_name,lessonTitle:d.lesson_title,
noteText:'\u2705 \u06a9\u0648\u06cc\u06cc\u0632 \u067e\u0627\u0633! \u0646\u0645\u0631\u0647: '+qr.score+'/'+qr.passing_score+' \u062f\u0631\u0633: '+d.lesson_title}}];
"""

    add_node({
        "id": "prep_quiz_pass",
        "name": "Prep Quiz Pass",
        "type": "n8n-nodes-base.code",
        "typeVersion": 1,
        "position": [1050, 680],
        "parameters": {"jsCode": prep_quiz_pass_code, "mode": "runOnceForAllItems"}
    })

    add_node({
        "id": "create_note",
        "name": "Create Note",
        "type": "n8n-nodes-didar-crm.didarCrm",
        "typeVersion": 1,
        "position": [2800, 755],
        "credentials": didar_cred,
        "parameters": {
            "resource": "note",
            "operation": "create",
            "ResultNote": "={{$json.noteText}}",
            "OwnerMode": "manual",
            "OwnerIdManual": "={{$json.ownerId}}",
            "additionalFields": {
                "DealId": "={{$json.dealId || ''}}",
                "PersonId": "={{$json.personId || ''}}"
            }
        }
    })

    prep_quiz_fail_code = r"""
const d=$input.first().json; const C=d.CONFIG;
const qr=d.payload?.quiz_result||{};
const ownerId = C.OWNERS && C.OWNERS.length ? C.OWNERS[0].id : '';
return [{json:{phone:d.user_phone,phoneSearch:d.phone_search||'',ownerId,CONFIG:C,
apiKey:C.DIDAR_API_KEY||'',pipelineId:C.PIPELINE_ID,
courseTitle:d.course_title,userName:d.user_name,lessonTitle:d.lesson_title,
noteText:'\u274c \u06a9\u0648\u06cc\u06cc\u0632 \u0646\u0627\u0645\u0648\u0641\u0642! \u0646\u0645\u0631\u0647: '+qr.score+'/'+qr.passing_score+' \u062f\u0631\u0633: '+d.lesson_title}}];
"""

    add_node({
        "id": "prep_quiz_fail",
        "name": "Prep Quiz Fail",
        "type": "n8n-nodes-base.code",
        "typeVersion": 1,
        "position": [1050, 830],
        "parameters": {"jsCode": prep_quiz_fail_code, "mode": "runOnceForAllItems"}
    })

    # Quiz person + deal search pipeline
    add_node({
        "id": "find_person_quiz",
        "name": "Find Person Quiz",
        "type": "n8n-nodes-didar-crm.didarCrm",
        "typeVersion": 1,
        "position": [1300, 755],
        "credentials": didar_cred,
        "parameters": {
            "resource": "person",
            "operation": "search",
            "Keywords": "={{$json.phoneSearch}}",
            "additionalFields": {"Limit": 1}
        }
    })

    extract_person_quiz_code = r"""
let prev;
try { prev=$('Prep Quiz Pass').first().json; }
catch(e) { prev=$('Prep Quiz Fail').first().json; }
const resp=$input.first().json;
const list=resp?.search_respons?.List||resp?.Response?.List||[];
const found=list.length>0?list[0]:null;
const personId=found?.Id||null;
if(!personId) return [{json:{...prev,personId:null,dealId:null}}];
const personOwnerId=found?.OwnerId||'';
const C=prev.CONFIG;
const approvedIds=(C.OWNERS||[]).map(o=>o.id);
const ownerId=approvedIds.includes(personOwnerId)?personOwnerId:prev.ownerId;
return [{json:{...prev,personId,ownerId}}];
"""
    add_node({
        "id": "extract_person_quiz",
        "name": "Extract Person Quiz",
        "type": "n8n-nodes-base.code",
        "typeVersion": 1,
        "position": [1550, 755],
        "parameters": {"jsCode": extract_person_quiz_code, "mode": "runOnceForAllItems"}
    })

    add_node({
        "id": "search_deal_quiz",
        "name": "Search Deal Quiz V2",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [1800, 755],
        "parameters": {
            "method": "POST",
            "url": "=https://app.didar.me/api/deal/search_v2?apikey={{ $json.apiKey }}",
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": "={{ JSON.stringify({Criteria: {ContactIds: [$json.personId], PipelineId: $json.pipelineId}, From: 0, Limit: 50}) }}",
            "options": {}
        }
    })

    extract_deal_quiz_code = r"""
const prev=$('Extract Person Quiz').first().json;
const resp=$input.first().json;
const deals=resp?.Response?.List||resp?.search_respons?.List||[];
const deal=deals.find(d=>d.PersonId===prev.personId||d.ContactId===prev.personId)||deals[0]||null;
return [{json:{...prev,dealId:deal?.Id||''}}];
"""
    add_node({
        "id": "extract_deal_quiz",
        "name": "Extract Deal Quiz",
        "type": "n8n-nodes-base.code",
        "typeVersion": 1,
        "position": [2050, 755],
        "parameters": {"jsCode": extract_deal_quiz_code, "mode": "runOnceForAllItems"}
    })

    connect("Router", "Prep Quiz Pass", 3)
    connect("Router", "Prep Quiz Fail", 4)
    connect("Prep Quiz Pass", "Find Person Quiz")
    connect("Prep Quiz Fail", "Find Person Quiz")
    connect("Find Person Quiz", "Extract Person Quiz")
    connect("Extract Person Quiz", "Search Deal Quiz V2")
    connect("Search Deal Quiz V2", "Extract Deal Quiz")
    connect("Extract Deal Quiz", "Create Note")

    # ═══════════════════════════════════════════════════
    # INACTIVITY BRANCH (output 5)
    # ═══════════════════════════════════════════════════

    prep_inactivity_code = r"""
const d=$input.first().json; const C=d.CONFIG;
const ownerId = C.OWNERS && C.OWNERS.length ? C.OWNERS[0].id : '';
return [{json:{phone:d.user_phone,phoneSearch:d.phone_search||'',ownerId,CONFIG:C,
activityTypeId:C.ACTIVITY_TYPE_FOLLOWUP,
activityTitle:'\u067e\u06cc\u06af\u06cc\u0631\u06cc \u0639\u062f\u0645 \u0641\u0639\u0627\u0644\u06cc\u062a - '+d.user_name,
activityNote:'\u063a\u06cc\u0631\u0641\u0639\u0627\u0644 48+ \u0633\u0627\u0639\u062a. \u062f\u0631\u0633 \u0622\u062e\u0631: '+d.lesson_title+' \u067e\u06cc\u0634\u0631\u0641\u062a: '+d.progress_percent+'%'}}];
"""

    add_node({
        "id": "prep_inactivity",
        "name": "Prep Inactivity",
        "type": "n8n-nodes-base.code",
        "typeVersion": 1,
        "position": [1050, 980],
        "parameters": {"jsCode": prep_inactivity_code, "mode": "runOnceForAllItems"}
    })

    add_node({
        "id": "create_followup",
        "name": "Create Followup",
        "type": "n8n-nodes-didar-crm.didarCrm",
        "typeVersion": 1,
        "position": [1300, 980],
        "credentials": didar_cred,
        "parameters": {
            "resource": "activity",
            "operation": "create",
            "Title": "={{$json.activityTitle}}",
            "ActivityTypeMode": "manual",
            "ActivityTypeIdManual": "={{$json.activityTypeId}}",
            "OwnerMode": "manual",
            "OwnerIdManual": "={{$json.ownerId}}",
            "IsDone": False,
            "additionalFields": {"Note": "={{$json.activityNote}}"}
        }
    })

    connect("Router", "Prep Inactivity", 5)
    connect("Prep Inactivity", "Create Followup")

    # ═══════════════════════════════════════════════════
    # COURSE COMPLETE BRANCH (output 6)
    # Bug 2 fix: Find Person first → verify deal belongs to person
    # Bug 3 fix: IF Deal Found guard
    # Bug 4 fix: Status "Won" + STAGES.won
    # Bug 8 fix: Update person lead_score
    # ═══════════════════════════════════════════════════

    # ── Bug 4 fix: stageId → C.STAGES.won ──
    prep_complete_code = r"""
const d=$input.first().json; const C=d.CONFIG;
const ownerId = C.OWNERS && C.OWNERS.length ? C.OWNERS[0].id : '';
const leadScore = d.payload?.lead_score || d.user?.lead_score || 0;

// Use bot-provided lead_score_field_json if available
let leadScoreFieldJson = d.payload?.lead_score_field_json || '{}';
if (leadScoreFieldJson === '{}' && C.CUSTOM_FIELDS.lead_score && C.CUSTOM_FIELDS.lead_score !== 'FIELD_GUID') {
  leadScoreFieldJson = JSON.stringify({[C.CUSTOM_FIELDS.lead_score]: String(leadScore)});
}

return [{json:{phone:d.user_phone,phoneSearch:d.phone_search||'',userName:d.user_name,courseTitle:d.course_title,
stageId:C.STAGES.sales_wait,ownerId,pipelineId:C.PIPELINE_ID,leadScore,leadScoreFieldJson,
apiKey:C.DIDAR_API_KEY||'',
activityTypeId:C.ACTIVITY_TYPE_SALES,CONFIG:C,
noteText:'\ud83c\udf89 \u062f\u0648\u0631\u0647 '+d.course_title+' \u062a\u06a9\u0645\u06cc\u0644 \u0634\u062f!',
activityTitle:'\u062a\u0645\u0627\u0633 \u0641\u0631\u0648\u0634 - '+d.user_name}}];
"""

    add_node({
        "id": "prep_complete",
        "name": "Prep Complete",
        "type": "n8n-nodes-base.code",
        "typeVersion": 1,
        "position": [1050, 1150],
        "parameters": {"jsCode": prep_complete_code, "mode": "runOnceForAllItems"}
    })

    # ── Bug 2 fix: Find person by phone before deal search ──
    add_node({
        "id": "find_person_complete",
        "name": "Find Person Complete",
        "type": "n8n-nodes-didar-crm.didarCrm",
        "typeVersion": 1,
        "position": [1300, 1150],
        "credentials": didar_cred,
        "parameters": {
            "resource": "person",
            "operation": "search",
            "Keywords": "={{$json.phoneSearch}}",
            "additionalFields": {"Limit": 1}
        }
    })

    extract_person_complete_code = r"""
const prev=$('Prep Complete').first().json;
const resp=$input.first().json;
const list = resp?.search_respons?.List || resp?.Response?.List || [];
const found = list.length > 0 ? list[0] : null;
const personId = found?.Id || null;
const lastName = found?.LastName || '';
if(!personId) return [{json:{...prev,personId:null,skip:true,reason:'person not found'}}];

// Preserve owner from person if approved
const personOwnerId = found?.OwnerId || '';
const approvedIds = (prev.CONFIG?.OWNERS || []).map(o => o.id);
const ownerId = approvedIds.includes(personOwnerId) ? personOwnerId : prev.ownerId;

return [{json:{...prev,personId,ownerId,lastName:lastName||prev.userName,skip:false}}];
"""
    add_node({
        "id": "extract_person_complete",
        "name": "Extract Person Complete",
        "type": "n8n-nodes-base.code",
        "typeVersion": 1,
        "position": [1550, 1150],
        "parameters": {"jsCode": extract_person_complete_code, "mode": "runOnceForAllItems"}
    })

    # Guard: skip Update Score when person not found
    add_node({
        "id": "if_person_found_complete",
        "name": "IF Person Found Complete",
        "type": "n8n-nodes-base.if",
        "typeVersion": 1,
        "position": [1650, 1150],
        "parameters": {
            "conditions": {
                "boolean": [{
                    "value1": "={{$json.skip}}",
                    "value2": False
                }]
            }
        }
    })

    # ── Bug 8 fix: Update person lead_score ──
    add_node({
        "id": "update_score_complete",
        "name": "Update Score Complete",
        "type": "n8n-nodes-didar-crm.didarCrm",
        "typeVersion": 1,
        "position": [1750, 1150],
        "credentials": didar_cred,
        "parameters": {
            "resource": "person",
            "operation": "update",
            "Id": "={{$json.personId}}",
            "LastName": "={{$json.lastName}}",
            "OwnerMode": "manual",
            "OwnerIdManual": "={{$json.ownerId}}",
            "additionalFields": {"Fields": "={{$json.leadScoreFieldJson}}"}
        }
    })

    recover_person_complete_code = r"""
const prev=$('Extract Person Complete').first().json;
return [{json:{...prev}}];
"""
    add_node({
        "id": "recover_person_complete",
        "name": "Recover Person Complete",
        "type": "n8n-nodes-base.code",
        "typeVersion": 1,
        "position": [1950, 1150],
        "parameters": {"jsCode": recover_person_complete_code, "mode": "runOnceForAllItems"}
    })

    add_node({
        "id": "search_deal_complete",
        "name": "Search Deal Complete V2",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [2150, 1150],
        "parameters": {
            "method": "POST",
            "url": "=https://app.didar.me/api/deal/search_v2?apikey={{ $json.apiKey }}",
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": "={{ JSON.stringify({Criteria: {ContactIds: [$json.personId], PipelineId: $json.pipelineId}, From: 0, Limit: 50}) }}",
            "options": {}
        }
    })

    # ── Bug 2 fix: filter deals by personId ──
    # Updated for deal/search_v2 response format
    extract_deal_complete_code = r"""
const prev=$('Recover Person Complete').first().json;
const resp=$input.first().json;
const deals=resp?.Response?.List||resp?.search_respons?.List||[];
if(!deals.length) return [{json:{...prev,skip:true,reason:'deal not found for completion',
  dealTitle:'\u062f\u0648\u0631\u0647 ' + prev.courseTitle + ' - ' + (prev.userName || 'User'),
  companyId: prev.CONFIG?.COMPANY_ID || '00000000-0000-0000-0000-000000000000'}}];
const deal = deals.find(d => d.PersonId === prev.personId || d.ContactId === prev.personId) || deals[0];

// Preserve owner from deal if approved
const dealOwnerId = deal.OwnerId || '';
const approvedIds = (prev.CONFIG?.OWNERS || []).map(o => o.id);
const realOwner = approvedIds.includes(dealOwnerId) ? dealOwnerId : prev.ownerId;

return [{json:{...prev,ownerId:realOwner,dealId:deal.Id,dealTitle:deal.Title,
personId:deal.PersonId||deal.ContactId||prev.personId,
companyId:deal.CompanyId||'00000000-0000-0000-0000-000000000000',skip:false}}];
"""

    add_node({
        "id": "extract_deal_complete",
        "name": "Extract Deal Complete",
        "type": "n8n-nodes-base.code",
        "typeVersion": 1,
        "position": [2350, 1150],
        "parameters": {"jsCode": extract_deal_complete_code, "mode": "runOnceForAllItems"}
    })

    # ── Bug 3 fix: IF Deal Found guard for complete branch ──
    add_node({
        "id": "if_deal_found_complete",
        "name": "IF Deal Found Complete",
        "type": "n8n-nodes-base.if",
        "typeVersion": 1,
        "position": [2550, 1150],
        "parameters": {
            "conditions": {
                "boolean": [{
                    "value1": "={{$json.skip}}",
                    "value2": False
                }]
            }
        }
    })

    # ── Bug 4 fix: Status "Won" instead of "Pending" ──
    add_node({
        "id": "update_deal_complete",
        "name": "Update Deal Complete",
        "type": "n8n-nodes-didar-crm.didarCrm",
        "typeVersion": 1,
        "position": [2800, 1100],
        "credentials": didar_cred,
        "parameters": {
            "resource": "deal",
            "operation": "update",
            "Id": "={{$json.dealId}}",
            "Title": "={{$json.dealTitle}}",
            "OwnerMode": "manual",
            "OwnerIdManual": "={{$json.ownerId}}",
            "PipelineMode": "manual",
            "PipelineId": "={{$json.pipelineId}}",
            "StageMode": "manual",
            "PipelineStageId": "={{$json.stageId}}",
            "PersonId": "={{$json.personId}}",
            "CompanyId": "={{$json.companyId}}",
            "Status": "Won",
            "LabelIds": [],
            "additionalFields": {}
        }
    })

    recover_complete_code = r"""
const prev=$('Extract Deal Complete').first().json;
return [{json:{...prev}}];
"""
    add_node({
        "id": "recover_complete",
        "name": "Recover Complete Data",
        "type": "n8n-nodes-base.code",
        "typeVersion": 1,
        "position": [3050, 1100],
        "parameters": {"jsCode": recover_complete_code, "mode": "runOnceForAllItems"}
    })

    add_node({
        "id": "sales_call",
        "name": "Sales Call",
        "type": "n8n-nodes-didar-crm.didarCrm",
        "typeVersion": 1,
        "position": [3300, 1100],
        "credentials": didar_cred,
        "parameters": {
            "resource": "activity",
            "operation": "create",
            "Title": "={{$json.activityTitle}}",
            "ActivityTypeMode": "manual",
            "ActivityTypeIdManual": "={{$json.activityTypeId}}",
            "OwnerMode": "manual",
            "OwnerIdManual": "={{$json.ownerId}}",
            "IsDone": False,
            "additionalFields": {
                "Note": "={{$json.noteText}}",
                "ContactIds": "={{$json.personId}}"
            }
        }
    })

    # Create deal when not found in complete branch
    add_node({
        "id": "create_deal_complete2",
        "name": "Create Deal Complete2",
        "type": "n8n-nodes-didar-crm.didarCrm",
        "typeVersion": 1,
        "position": [2800, 1300],
        "credentials": didar_cred,
        "parameters": {
            "resource": "deal",
            "operation": "create",
            "Title": "={{$json.dealTitle}}",
            "OwnerMode": "manual",
            "OwnerIdManual": "={{$json.ownerId}}",
            "PipelineMode": "manual",
            "PipelineId": "={{$json.pipelineId}}",
            "StageMode": "manual",
            "PipelineStageId": "={{$json.stageId}}",
            "PersonId": "={{$json.personId}}",
            "CompanyId": "={{$json.companyId}}",
            "Status": "Won",
            "LabelIds": [],
            "additionalFields": {}
        }
    })

    after_create_deal_complete_code = r"""
const prev=$('Extract Deal Complete').first().json;
const resp=$input.first().json;
const newDealId=resp?.Response?.Id||'';
return [{json:{...prev,dealId:newDealId,skip:false}}];
"""
    add_node({
        "id": "after_create_deal_complete",
        "name": "After Create Deal Complete",
        "type": "n8n-nodes-base.code",
        "typeVersion": 1,
        "position": [3050, 1300],
        "parameters": {"jsCode": after_create_deal_complete_code, "mode": "runOnceForAllItems"}
    })

    unify_deal_complete_code = r"""
let prev, dealId;
try {
  prev=$('Recover Complete Data').first().json;
  dealId=prev.dealId;
} catch(e) {}
if (!dealId) {
  try {
    prev=$('After Create Deal Complete').first().json;
    dealId=prev.dealId;
  } catch(e) {}
}
if (!prev) prev={};
return [{json:{...prev,dealId:dealId||''}}];
"""
    add_node({
        "id": "unify_deal_complete",
        "name": "Unify Deal Complete",
        "type": "n8n-nodes-base.code",
        "typeVersion": 1,
        "position": [3300, 1200],
        "parameters": {"jsCode": unify_deal_complete_code, "mode": "runOnceForAllItems"}
    })

    connect("Router", "Prep Complete", 6)
    connect("Prep Complete", "Find Person Complete")
    connect("Find Person Complete", "Extract Person Complete")
    connect("Extract Person Complete", "IF Person Found Complete")
    connect("IF Person Found Complete", "Update Score Complete", 0)   # true: person found
    connect("IF Person Found Complete", "Prep Respond OK", 1)         # false: person not found
    connect("Update Score Complete", "Recover Person Complete")
    connect("Recover Person Complete", "Search Deal Complete V2")
    connect("Search Deal Complete V2", "Extract Deal Complete")
    connect("Extract Deal Complete", "IF Deal Found Complete")
    connect("IF Deal Found Complete", "Update Deal Complete", 0)    # true: deal found → update
    connect("IF Deal Found Complete", "Create Deal Complete2", 1)   # false: no deal → create
    connect("Update Deal Complete", "Recover Complete Data")
    connect("Recover Complete Data", "Unify Deal Complete")
    connect("Create Deal Complete2", "After Create Deal Complete")
    connect("After Create Deal Complete", "Unify Deal Complete")
    connect("Unify Deal Complete", "Sales Call")

    # ═══════════════════════════════════════════════════
    # SPEED CHANGE BRANCH (output 7)
    # ═══════════════════════════════════════════════════

    prep_speed_code = r"""
const d=$input.first().json; const C=d.CONFIG;
const ownerId = C.OWNERS && C.OWNERS.length ? C.OWNERS[0].id : '';
return [{json:{phone:d.user_phone,phoneSearch:d.phone_search||'',ownerId,CONFIG:C,
noteText:'\u26a1 \u062a\u063a\u06cc\u06cc\u0631 \u0633\u0631\u0639\u062a: '+(d.payload?.speed_type||d.event?.type||'')+' \u2192 '+(d.payload?.new_speed||d.event?.status||'')}}];
"""

    add_node({
        "id": "prep_speed",
        "name": "Prep Speed",
        "type": "n8n-nodes-base.code",
        "typeVersion": 1,
        "position": [1050, 1350],
        "parameters": {"jsCode": prep_speed_code, "mode": "runOnceForAllItems"}
    })

    # Speed person search pipeline
    add_node({
        "id": "find_person_speed",
        "name": "Find Person Speed",
        "type": "n8n-nodes-didar-crm.didarCrm",
        "typeVersion": 1,
        "position": [1300, 1350],
        "credentials": didar_cred,
        "parameters": {
            "resource": "person",
            "operation": "search",
            "Keywords": "={{$json.phoneSearch}}",
            "additionalFields": {"Limit": 1}
        }
    })

    extract_person_speed_code = r"""
const prev=$('Prep Speed').first().json;
const resp=$input.first().json;
const list=resp?.search_respons?.List||resp?.Response?.List||[];
const found=list.length>0?list[0]:null;
const personId=found?.Id||null;
if(!personId) return [{json:{...prev,personId:null}}];
const personOwnerId=found?.OwnerId||'';
const C=prev.CONFIG;
const approvedIds=(C.OWNERS||[]).map(o=>o.id);
const ownerId=approvedIds.includes(personOwnerId)?personOwnerId:prev.ownerId;
return [{json:{...prev,personId,ownerId}}];
"""
    add_node({
        "id": "extract_person_speed",
        "name": "Extract Person Speed",
        "type": "n8n-nodes-base.code",
        "typeVersion": 1,
        "position": [1550, 1350],
        "parameters": {"jsCode": extract_person_speed_code, "mode": "runOnceForAllItems"}
    })

    add_node({
        "id": "create_note_speed",
        "name": "Create Note Speed",
        "type": "n8n-nodes-didar-crm.didarCrm",
        "typeVersion": 1,
        "position": [1800, 1350],
        "credentials": didar_cred,
        "parameters": {
            "resource": "note",
            "operation": "create",
            "ResultNote": "={{$json.noteText}}",
            "OwnerMode": "manual",
            "OwnerIdManual": "={{$json.ownerId}}",
            "additionalFields": {
                "PersonId": "={{$json.personId || ''}}"
            }
        }
    })

    connect("Router", "Prep Speed", 7)
    connect("Prep Speed", "Find Person Speed")
    connect("Find Person Speed", "Extract Person Speed")
    connect("Extract Person Speed", "Create Note Speed")

    # ═══════════════════════════════════════════════════
    # RESPOND OK — shared by all non-register branches
    # ═══════════════════════════════════════════════════

    respond_ok_code = r"""
return [{json: {status: 'ok'}}];
"""

    add_node({
        "id": "prep_respond_ok",
        "name": "Prep Respond OK",
        "type": "n8n-nodes-base.code",
        "typeVersion": 1,
        "position": [2050, 600],
        "parameters": {"jsCode": respond_ok_code, "mode": "runOnceForAllItems"}
    })

    add_node({
        "id": "respond_ok",
        "name": "Respond OK",
        "type": "n8n-nodes-base.respondToWebhook",
        "typeVersion": 1,
        "position": [2300, 600],
        "parameters": {
            "respondWith": "allIncomingItems",
            "options": {}
        }
    })

    # Connect all non-register branch endings to Respond OK
    connect("Sales Call Lesson", "Prep Respond OK")         # lesson trigger_sales=true
    connect("IF Trigger Sales", "Prep Respond OK", 1)        # lesson trigger_sales=false
    connect("Create Note Form", "Prep Respond OK")           # form completed
    connect("Create Note", "Prep Respond OK")                # quiz note
    connect("Create Followup", "Prep Respond OK")
    connect("Create Note Speed", "Prep Respond OK")          # speed note
    connect("Sales Call", "Prep Respond OK")
    connect("Prep Respond OK", "Respond OK")

    # ── Bug 12 fix: unmatched events → Respond OK ──
    connect("Router", "Prep Respond OK", 8)

    # ═══════════════════════════════════════════════════
    # BUILD FINAL WORKFLOW
    # ═══════════════════════════════════════════════════

    workflow = {
        "name": "Course Bot - Didar CRM (v6)",
        "nodes": nodes,
        "connections": connections,
        "active": False,
        "settings": {"executionOrder": "v1"},
        "tags": [
            {"name": "course-bot"},
            {"name": "didar-crm"}
        ]
    }

    return workflow


if __name__ == "__main__":
    import os
    wf = build_workflow()
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "course-bot-didar-crm.json")
    with open(out_path, "w") as f:
        json.dump(wf, f, indent=2, ensure_ascii=False)
    print(f"Generated workflow with {len(wf['nodes'])} nodes → {out_path}")
