#!/usr/bin/env python3
"""Generate n8n workflow v3 with smart owner assignment, person dedup, deal dedup."""
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

    config_code = r"""
const CONFIG = {
  WEBHOOK_SECRET: 'YOUR_WEBHOOK_SECRET_HERE',
  // Weighted owner list — weight = relative chance of assignment
  OWNERS: [
    {id: 'OWNER_GUID_1', name: 'Owner 1', weight: 3},
    {id: 'OWNER_GUID_2', name: 'Owner 2', weight: 2},
    // Add more owners as needed
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
    followup_3: 'STAGE_GUID_HERE'
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
return [{json: {...body, CONFIG, action,
  user_phone: user.phone || (user.registration_data?.phone || ''),
  user_name: (user.first_name||'') + ' ' + (user.last_name||''),
  course_title: course.title || '',
  lesson_title: lesson.title || '',
  lesson_order: lesson.order || 0,
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

    add_node({
        "id": "router",
        "name": "Router",
        "type": "n8n-nodes-base.switch",
        "typeVersion": 1,
        "position": [750, 500],
        "parameters": {
            "dataType": "string",
            "value1": "={{$json.action}}",
            "rules": {"rules": [
                {"value2": "lead.register", "output": 0},
                {"value2": "lesson.complete", "output": 1},
                {"value2": "form.submit", "output": 2},
                {"value2": "quiz.pass", "output": 3},
                {"value2": "quiz.fail", "output": 4},
                {"value2": "inactivity.timeout", "output": 5},
                {"value2": "course.complete", "output": 6},
                {"value2": "speed.change", "output": 7}
            ]},
            "fallbackOutput": -1
        }
    })

    connect("Webhook", "Config")
    connect("Config", "Router")

    # ═══════════════════════════════════════════════════
    # REGISTER BRANCH (output 0) — Smart Owner + Dedup
    # ═══════════════════════════════════════════════════

    prep_register_code = r"""
const d = $input.first().json;
const C = d.CONFIG;

// ── Weighted owner selection ──
const owners = (C.OWNERS || []).filter(o => o.weight > 0);
let ownerId = owners.length ? owners[0].id : '';
let ownerName = owners.length ? owners[0].name : '';

if (owners.length > 1) {
  // Build weighted pool
  let pool = [];
  for (const o of owners) {
    for (let i = 0; i < o.weight; i++) pool.push(o);
  }
  const selected = pool[Math.floor(Math.random() * pool.length)];
  ownerId = selected.id;
  ownerName = selected.name;
}

const lastName = d.user?.last_name || d.user?.first_name || 'User';
const firstName = d.user?.first_name || '';
const phone = d.user_phone || (d.user?.registration_data?.phone || '');

return [{json: {
  phone, firstName, lastName,
  ownerId, ownerName,
  pipelineId: C.PIPELINE_ID,
  stageId: C.STAGES.register,
  companyId: C.COMPANY_ID,
  activityTypeId: C.ACTIVITY_TYPE_SALES,
  courseTitle: d.course_title,
  dealTitle: '\u062f\u0648\u0631\u0647 ' + d.course_title + ' - ' + lastName,
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
            "operation": "getByPhone",
            "MobilePhone": "={{$json.phone}}"
        }
    })

    process_person_code = r"""
const prev = $('Prep Register').first().json;
const resp = $input.first().json;
const found = resp?.Response?.Id || null;
return [{json: {...prev, personExists: !!found, personId: found || null}}];
"""

    add_node({
        "id": "process_person",
        "name": "Process Person",
        "type": "n8n-nodes-base.code",
        "typeVersion": 1,
        "position": [1550, 100],
        "parameters": {"jsCode": process_person_code, "mode": "runOnceForAllItems"}
    })

    # IF Person Exists?
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

    # True branch: person exists → use existing
    use_existing_code = r"""
const d = $input.first().json;
// Person already exists in CRM, use their ID
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

    # False branch: create new person
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
                "VisibilityType": "Owner"
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

    # Both person paths connect to Search Deal
    add_node({
        "id": "search_deal_reg",
        "name": "Search Deal Reg",
        "type": "n8n-nodes-didar-crm.didarCrm",
        "typeVersion": 1,
        "position": [2550, 100],
        "credentials": didar_cred,
        "parameters": {
            "resource": "deal",
            "operation": "search",
            "Keywords": "={{$json.courseTitle}}",
            "Status": "Pending",
            "PipelineMode": "manual",
            "PipelineIdManual": "={{$json.pipelineId}}",
            "PipelineStageIdManual": "",
            "ContactIds": [],
            "LabelIds": [],
            "additionalFields": {"Limit": 5}
        }
    })

    process_deal_code = r"""
// Get person data from whichever path ran
let prev;
try { prev = $('Use Existing Person').first().json; }
catch(e) { prev = $('Get New Person ID').first().json; }

const resp = $input.first().json;
const deals = resp?.Response?.List || [];
// Look for an existing open deal with matching personId
const existingDeal = deals.find(d => d.PersonId === prev.personId && d.Status === 'Pending');

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

    # IF Deal Exists?
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

    # True: deal exists → skip creation
    skip_deal_code = r"""
const d = $input.first().json;
// Deal already exists, skip creation
return [{json: {...d}}];
"""
    add_node({
        "id": "skip_deal",
        "name": "Skip Deal Create",
        "type": "n8n-nodes-base.code",
        "typeVersion": 1,
        "position": [3300, 0],
        "parameters": {"jsCode": skip_deal_code, "mode": "runOnceForAllItems"}
    })

    # False: create new deal
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

    # Happy Call — both deal paths connect here
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
                "ContactIds": "={{$json.personId}}"
            }
        }
    })

    # Respond Register — return owner info to the bot
    prep_response_code = r"""
const d = $input.first().json;
// Prepare final response with owner info for the bot
let prev;
try { prev = $('Process Deal Reg').first().json; }
catch(e) { prev = $('Skip Deal Create').first().json || $('After Create Deal').first().json; }
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
    connect("IF Person Exists", "Use Existing Person", 0)     # true: person exists
    connect("IF Person Exists", "Create Person", 1)            # false: create new
    connect("Use Existing Person", "Search Deal Reg")
    connect("Create Person", "Get New Person ID")
    connect("Get New Person ID", "Search Deal Reg")
    connect("Search Deal Reg", "Process Deal Reg")
    connect("Process Deal Reg", "IF Deal Exists")
    connect("IF Deal Exists", "Skip Deal Create", 0)           # true: deal exists
    connect("IF Deal Exists", "Create Deal", 1)                # false: create new
    connect("Skip Deal Create", "Happy Call")
    connect("Create Deal", "After Create Deal")
    connect("After Create Deal", "Happy Call")
    connect("Happy Call", "Prep Response")
    connect("Prep Response", "Respond Register")

    # ═══════════════════════════════════════════════════
    # LESSON BRANCH (output 1) — unchanged
    # ═══════════════════════════════════════════════════

    prep_lesson_code = r"""
const d=$input.first().json; const C=d.CONFIG;
const stageId=C.STAGES['lesson_'+d.lesson_order]||'';
const ownerId = C.OWNERS && C.OWNERS.length ? C.OWNERS[0].id : '';
return [{json:{phone:d.user_phone,stageId,lessonOrder:d.lesson_order,
courseTitle:d.course_title,ownerId,pipelineId:C.PIPELINE_ID,
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

    add_node({
        "id": "search_deal",
        "name": "Search Deal",
        "type": "n8n-nodes-didar-crm.didarCrm",
        "typeVersion": 1,
        "position": [1300, 300],
        "credentials": didar_cred,
        "parameters": {
            "resource": "deal",
            "operation": "search",
            "Keywords": "={{$json.courseTitle}}",
            "Status": "Pending",
            "PipelineMode": "manual",
            "PipelineIdManual": "={{$json.pipelineId}}",
            "PipelineStageIdManual": "",
            "ContactIds": [], "LabelIds": [],
            "additionalFields": {"Limit": 5}
        }
    })

    extract_deal_code = r"""
const prev=$('Prep Lesson').first().json;
const resp=$input.first().json;
const deals=resp?.Response?.List||[];
if(!deals.length) return [{json:{skip:true,reason:'deal not found'}}];
const deal=deals[0];
return [{json:{dealId:deal.Id,dealTitle:deal.Title,personId:deal.PersonId||'00000000-0000-0000-0000-000000000000',
stageId:prev.stageId,ownerId:prev.ownerId,pipelineId:prev.pipelineId,
companyId:deal.CompanyId||'00000000-0000-0000-0000-000000000000',
noteText:prev.noteText,CONFIG:prev.CONFIG}}];
"""

    add_node({
        "id": "extract_deal",
        "name": "Extract Deal",
        "type": "n8n-nodes-base.code",
        "typeVersion": 1,
        "position": [1550, 300],
        "parameters": {"jsCode": extract_deal_code, "mode": "runOnceForAllItems"}
    })

    add_node({
        "id": "update_deal_stage",
        "name": "Update Deal Stage",
        "type": "n8n-nodes-didar-crm.didarCrm",
        "typeVersion": 1,
        "position": [1800, 300],
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

    connect("Router", "Prep Lesson", 1)
    connect("Prep Lesson", "Search Deal")
    connect("Search Deal", "Extract Deal")
    connect("Extract Deal", "Update Deal Stage")

    # ═══════════════════════════════════════════════════
    # FORM BRANCH (output 2) — unchanged
    # ═══════════════════════════════════════════════════

    prep_form_code = r"""
const d=$input.first().json; const C=d.CONFIG;
const f=d.payload?.form_responses||{};
const map={monthly_income:C.CUSTOM_FIELDS.monthly_income,staff_count:C.CUSTOM_FIELDS.staff_count,
job:C.CUSTOM_FIELDS.job,best_call_time:C.CUSTOM_FIELDS.best_call_time,
city:C.CUSTOM_FIELDS.city,income_class:C.CUSTOM_FIELDS.income_class};
let cf={};
for(const[k,g] of Object.entries(map)){if(f[k]&&g&&g!=='FIELD_GUID')cf[g]=String(f[k]);}
const ownerId = C.OWNERS && C.OWNERS.length ? C.OWNERS[0].id : '';
return [{json:{phone:d.user_phone,customFieldsJson:JSON.stringify(cf),ownerId,CONFIG:C}}];
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
            "operation": "getByPhone",
            "MobilePhone": "={{$json.phone}}"
        }
    })

    extract_person_form_code = r"""
const prev=$('Prep Form').first().json;
const resp=$input.first().json;
const personId=resp?.Response?.Id||null;
const lastName=resp?.Response?.LastName||'User';
if(!personId) return [{json:{skip:true,reason:'person not found by phone'}}];
return [{json:{...prev,personId,lastName}}];
"""

    add_node({
        "id": "extract_person_form",
        "name": "Extract Person Form",
        "type": "n8n-nodes-base.code",
        "typeVersion": 1,
        "position": [1550, 500],
        "parameters": {"jsCode": extract_person_form_code, "mode": "runOnceForAllItems"}
    })

    add_node({
        "id": "update_person_fields",
        "name": "Update Person Fields",
        "type": "n8n-nodes-didar-crm.didarCrm",
        "typeVersion": 1,
        "position": [1800, 500],
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
    connect("Extract Person Form", "Update Person Fields")

    # ═══════════════════════════════════════════════════
    # QUIZ PASS / FAIL / SPEED → shared Create Note
    # ═══════════════════════════════════════════════════

    prep_quiz_pass_code = r"""
const d=$input.first().json; const C=d.CONFIG;
const qr=d.payload?.quiz_result||{};
const ownerId = C.OWNERS && C.OWNERS.length ? C.OWNERS[0].id : '';
return [{json:{phone:d.user_phone,ownerId,CONFIG:C,
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
        "position": [1300, 755],
        "credentials": didar_cred,
        "parameters": {
            "resource": "note",
            "operation": "create",
            "ResultNote": "={{$json.noteText}}",
            "OwnerMode": "manual",
            "OwnerIdManual": "={{$json.ownerId}}"
        }
    })

    prep_quiz_fail_code = r"""
const d=$input.first().json; const C=d.CONFIG;
const qr=d.payload?.quiz_result||{};
const ownerId = C.OWNERS && C.OWNERS.length ? C.OWNERS[0].id : '';
return [{json:{phone:d.user_phone,ownerId,CONFIG:C,
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

    connect("Router", "Prep Quiz Pass", 3)
    connect("Router", "Prep Quiz Fail", 4)
    connect("Prep Quiz Pass", "Create Note")
    connect("Prep Quiz Fail", "Create Note")

    # ═══════════════════════════════════════════════════
    # INACTIVITY BRANCH (output 5) — unchanged
    # ═══════════════════════════════════════════════════

    prep_inactivity_code = r"""
const d=$input.first().json; const C=d.CONFIG;
const ownerId = C.OWNERS && C.OWNERS.length ? C.OWNERS[0].id : '';
return [{json:{phone:d.user_phone,ownerId,CONFIG:C,
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
    # COURSE COMPLETE BRANCH (output 6) — unchanged
    # ═══════════════════════════════════════════════════

    prep_complete_code = r"""
const d=$input.first().json; const C=d.CONFIG;
const ownerId = C.OWNERS && C.OWNERS.length ? C.OWNERS[0].id : '';
return [{json:{phone:d.user_phone,userName:d.user_name,courseTitle:d.course_title,
stageId:C.STAGES.sales_wait,ownerId,pipelineId:C.PIPELINE_ID,
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

    add_node({
        "id": "search_deal_complete",
        "name": "Search Deal Complete",
        "type": "n8n-nodes-didar-crm.didarCrm",
        "typeVersion": 1,
        "position": [1300, 1150],
        "credentials": didar_cred,
        "parameters": {
            "resource": "deal",
            "operation": "search",
            "Keywords": "={{$json.courseTitle}}",
            "Status": "Pending",
            "PipelineMode": "manual",
            "PipelineIdManual": "={{$json.pipelineId}}",
            "PipelineStageIdManual": "",
            "ContactIds": [], "LabelIds": [],
            "additionalFields": {"Limit": 5}
        }
    })

    extract_deal_complete_code = r"""
const prev=$('Prep Complete').first().json;
const resp=$input.first().json;
const deals=resp?.Response?.List||[];
if(!deals.length) return [{json:{skip:true,reason:'deal not found for completion'}}];
const deal=deals[0];
return [{json:{...prev,dealId:deal.Id,dealTitle:deal.Title,
personId:deal.PersonId||'00000000-0000-0000-0000-000000000000',
companyId:deal.CompanyId||'00000000-0000-0000-0000-000000000000'}}];
"""

    add_node({
        "id": "extract_deal_complete",
        "name": "Extract Deal Complete",
        "type": "n8n-nodes-base.code",
        "typeVersion": 1,
        "position": [1550, 1150],
        "parameters": {"jsCode": extract_deal_complete_code, "mode": "runOnceForAllItems"}
    })

    add_node({
        "id": "update_deal_complete",
        "name": "Update Deal Complete",
        "type": "n8n-nodes-didar-crm.didarCrm",
        "typeVersion": 1,
        "position": [1800, 1150],
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

    add_node({
        "id": "sales_call",
        "name": "Sales Call",
        "type": "n8n-nodes-didar-crm.didarCrm",
        "typeVersion": 1,
        "position": [2050, 1150],
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

    connect("Router", "Prep Complete", 6)
    connect("Prep Complete", "Search Deal Complete")
    connect("Search Deal Complete", "Extract Deal Complete")
    connect("Extract Deal Complete", "Update Deal Complete")
    connect("Update Deal Complete", "Sales Call")

    # ═══════════════════════════════════════════════════
    # SPEED CHANGE BRANCH (output 7) — unchanged
    # ═══════════════════════════════════════════════════

    prep_speed_code = r"""
const d=$input.first().json; const C=d.CONFIG;
const ownerId = C.OWNERS && C.OWNERS.length ? C.OWNERS[0].id : '';
return [{json:{phone:d.user_phone,ownerId,CONFIG:C,
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

    connect("Router", "Prep Speed", 7)
    connect("Prep Speed", "Create Note")

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
    connect("Update Deal Stage", "Prep Respond OK")
    connect("Update Person Fields", "Prep Respond OK")
    connect("Create Note", "Prep Respond OK")
    connect("Create Followup", "Prep Respond OK")
    connect("Sales Call", "Prep Respond OK")
    connect("Prep Respond OK", "Respond OK")

    # ═══════════════════════════════════════════════════
    # BUILD FINAL WORKFLOW
    # ═══════════════════════════════════════════════════

    workflow = {
        "name": "Course Bot - Didar CRM (v3)",
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
    wf = build_workflow()
    with open("/private/tmp/telegram-course-bot/n8n-workflows/course-bot-didar-crm.json", "w") as f:
        json.dump(wf, f, indent=2, ensure_ascii=False)
    print(f"Generated workflow with {len(wf['nodes'])} nodes")
