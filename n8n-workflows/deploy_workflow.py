#!/usr/bin/env python3
"""Fill in real values into the generated workflow template for deployment."""
import json, os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(SCRIPT_DIR, 'course-bot-didar-crm.json')
OUTPUT = os.path.join(SCRIPT_DIR, 'course-bot-didar-crm-deploy.json')

with open(TEMPLATE) as f:
    wf = json.load(f)

# Real values from currently deployed v7 workflow
REAL_VALUES = {
    'YOUR_WEBHOOK_SECRET_HERE': 'MyStr0ngS3cret_2026!',
    'YOUR_DIDAR_API_KEY_HERE': '1t31qjd4bl43cxej1yybhr2uf24ael2a',
    'YOUR_PIPELINE_GUID_HERE': '9b0e5024-4822-4833-abe6-8ca426a937ae',
    'YOUR_SALES_ACTIVITY_TYPE_GUID': 'dc40fdb0-f8a5-4a40-80fe-1102a8a8b9f3',
    'YOUR_FOLLOWUP_ACTIVITY_TYPE_GUID': '3b9512e1-663c-4265-827e-43fa5bcee70e',
}

STAGE_VALUES = {
    "register: 'STAGE_GUID_HERE'": "register: 'b7e97097-ff9b-4207-a2e7-07dd2ea606af'",
    "lesson_1: 'STAGE_GUID_HERE'": "lesson_1: 'ffa64a67-02e0-462b-a0c2-60c85eee6af5'",
    "lesson_2: 'STAGE_GUID_HERE'": "lesson_2: 'bcfe1289-12bf-4ee6-88e7-2dcf0ed48469'",
    "lesson_3: 'STAGE_GUID_HERE'": "lesson_3: '4223a51c-544b-41e2-94bc-1e99016fbaba'",
    "lesson_4: 'STAGE_GUID_HERE'": "lesson_4: '09856491-6d78-40df-b3ed-c80083e77a8f'",
    "lesson_5: 'STAGE_GUID_HERE'": "lesson_5: '0fcb3769-e1ad-45d5-8847-e51e97065d85'",
    "lesson_6: 'STAGE_GUID_HERE'": "lesson_6: 'aee7d1c1-5f18-43e8-b1cb-050d59ce3517'",
    "lesson_7: 'STAGE_GUID_HERE'": "lesson_7: 'd9fc8133-052f-465b-9289-4211272b6e18'",
    "lesson_8: 'STAGE_GUID_HERE'": "lesson_8: '6faab0b4-be10-478d-9655-bf41eca744a8'",
    "sales_wait: 'STAGE_GUID_HERE'": "sales_wait: '6faab0b4-be10-478d-9655-bf41eca744a8'",
    "followup_1: 'STAGE_GUID_HERE'": "followup_1: 'be5d2b7a-4cf6-4b5d-873f-a3a76ccf2310'",
    "followup_2: 'STAGE_GUID_HERE'": "followup_2: 'daa24b66-5151-4e57-b08e-032a2961c339'",
    "followup_3: 'STAGE_GUID_HERE'": "followup_3: '3d3cf5e9-0726-43db-9e01-885c50c3b2bd'",
    "won: 'STAGE_GUID_HERE'": "won: ''",
}

OWNER_PLACEHOLDER = """    {id: 'OWNER_GUID_1', name: 'Owner 1', weight: 3},
    {id: 'OWNER_GUID_2', name: 'Owner 2', weight: 2},"""

OWNER_REAL = """    {id: 'a52a4294-f773-48cf-8201-d4402f7b7780', name: 'عباسی', weight: 3},
    {id: 'f4d3c7ad-3fb4-42f3-bf78-04ca86a24a1f', name: 'غلامی', weight: 2},"""

CUSTOM_FIELDS_PLACEHOLDER = """    monthly_income: 'FIELD_GUID', staff_count: 'FIELD_GUID',
    job: 'FIELD_GUID', best_call_time: 'FIELD_GUID',
    lead_score: 'FIELD_GUID', city: 'FIELD_GUID',
    income_class: 'FIELD_GUID'"""

CUSTOM_FIELDS_REAL = """    monthly_income: 'Field_996_0_26', staff_count: 'Field_996_0_25',
    job: 'J', best_call_time: 'Field_996_0_31',
    lead_score: 'Field_996_12_30', city: 'Field_996_0_11'"""

DIDAR_CRED = {"didarApi": {"id": "Hu6Sv3Cuz88ZlcNn", "name": "MasireSefidDidar"}}

# Apply replacements to Config code
config_node = next(n for n in wf['nodes'] if n['name'] == 'Config')
code = config_node['parameters']['jsCode']

for placeholder, real in REAL_VALUES.items():
    code = code.replace(placeholder, real)
for placeholder, real in STAGE_VALUES.items():
    code = code.replace(placeholder, real)
code = code.replace(OWNER_PLACEHOLDER, OWNER_REAL)
code = code.replace(CUSTOM_FIELDS_PLACEHOLDER, CUSTOM_FIELDS_REAL)

config_node['parameters']['jsCode'] = code

# Fix user_name extraction to match deployed version (handles missing registration_data gracefully)
# The deployed v7 uses: (user.registration_data.first_name||'') + ' ' + (user.registration_data.last_name||'')
# Our template uses optional chaining which is safer

# Set credentials on all Didar CRM nodes
for n in wf['nodes']:
    if n['type'] == 'n8n-nodes-didar-crm.didarCrm':
        n['credentials'] = DIDAR_CRED

# Set workflow metadata to import as update
wf['name'] = 'Course Bot - Didar CRM (v8-fix)'

# Verify no remaining placeholders
all_text = json.dumps(wf)
placeholders_found = []
for p in ['STAGE_GUID_HERE', 'OWNER_GUID', 'FIELD_GUID', 'YOUR_']:
    if p in all_text:
        placeholders_found.append(p)

if placeholders_found:
    print(f"WARNING: Unfilled placeholders: {placeholders_found}")
else:
    print("All placeholders filled successfully")

with open(OUTPUT, 'w') as f:
    json.dump(wf, f, indent=2, ensure_ascii=False)

print(f"Deployment workflow written to: {OUTPUT}")
print(f"Nodes: {len(wf['nodes'])}")

# Verify key fixes
print("\n=== Verification ===")
code = config_node['parameters']['jsCode']
print(f"  lesson.lesson_number: {'YES' if 'lesson.lesson_number' in code else 'NO'}")
print(f"  DIDAR_API_KEY: {'YES' if '1t31qjd4bl43cxej1yybhr2uf24ael2a' in code else 'NO'}")
print(f"  phone_search: {'YES' if 'phone_search' in code else 'NO'}")

for name in ['Search Deal Reg V2', 'Search Deal V2', 'Search Deal Complete V2']:
    n = next(x for x in wf['nodes'] if x['name'] == name)
    print(f"  {name}: type={n['type']} (httpRequest)")
