#!/usr/bin/env python3
"""Quick CRM Audit — compare bot users with Didar CRM after backfill."""
import json
import urllib.request
import urllib.error

DIDAR_API_KEY = "1t31qjd4bl43cxej1yybhr2uf24ael2a"
DIDAR_BASE = "https://app.didar.me/api"
PIPELINE_ID = "9b0e5024-4822-4833-abe6-8ca426a937ae"
BOT_PANEL_URL = "http://193.163.201.132:8080"
BOT_ADMIN_USER = "admin"
BOT_ADMIN_PASS = "CourseBot@2024Admin"
LEAD_SCORE_FIELD = "Field_996_12_30"

STAGES = {
    "b7e97097-ff9b-4207-a2e7-07dd2ea606af": "register",
    "ffa64a67-02e0-462b-a0c2-60c85eee6af5": "lesson_1",
    "bcfe1289-12bf-4ee6-88e7-2dcf0ed48469": "lesson_2",
    "4223a51c-544b-41e2-94bc-1e99016fbaba": "lesson_3",
    "09856491-6d78-40df-b3ed-c80083e77a8f": "lesson_4",
    "0fcb3769-e1ad-45d5-8847-e51e97065d85": "lesson_5",
    "aee7d1c1-5f18-43e8-b1cb-050d59ce3517": "lesson_6",
    "d9fc8133-052f-465b-9289-4211272b6e18": "lesson_7",
    "6faab0b4-be10-478d-9655-bf41eca744a8": "lesson_8",
}

STAGE_GUIDS = {v: k for k, v in STAGES.items()}

def normalise_phone(raw):
    if not raw: return ""
    digits = "".join(c for c in str(raw) if c.isdigit())
    return digits[-10:] if len(digits) >= 10 else digits

def expected_stage_guid(completed, current_lesson, is_completed):
    if is_completed: return STAGE_GUIDS.get("lesson_8", "")
    inferred = max(0, (current_lesson or 1) - 1)
    effective = max(completed or 0, inferred)
    if effective > 0:
        key = f"lesson_{min(effective, 8)}"
        return STAGE_GUIDS.get(key, STAGE_GUIDS["register"])
    return STAGE_GUIDS["register"]

def api_post(url, body, headers=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", **(headers or {})})
    return json.loads(urllib.request.urlopen(req).read().decode())

# Get bot users
print("📋 Fetching bot users...")
token = api_post(f"{BOT_PANEL_URL}/api/auth/login",
                  {"username": BOT_ADMIN_USER, "password": BOT_ADMIN_PASS})["access_token"]
req = urllib.request.Request(f"{BOT_PANEL_URL}/api/audit/users",
                              headers={"Authorization": f"Bearer {token}"})
bot_users = json.loads(urllib.request.urlopen(req).read().decode())["items"]
print(f"  {len(bot_users)} users")

# Get CRM deals
print("📋 Fetching CRM deals...")
data = api_post(f"{DIDAR_BASE}/deal/search_v2?apikey={DIDAR_API_KEY}",
                {"Criteria": {"PipelineId": PIPELINE_ID}, "From": 0, "Limit": 5000})
deals = (data.get("search_respons") or data.get("Response", {})).get("List", [])
print(f"  {len(deals)} deals")

# Build lookup
deal_by_phone = {}
person_by_phone = {}
for d in deals:
    p = d.get("Person") or d.get("Contact") or {}
    for ph in [p.get("MobilePhone"), p.get("WorkPhone")]:
        norm = normalise_phone(ph)
        if norm:
            if norm not in deal_by_phone or d.get("Status") == "Pending":
                deal_by_phone[norm] = d
            if norm not in person_by_phone:
                person_by_phone[norm] = p

# Compare
matched = 0; stage_ok = 0; stage_mismatch = 0; score_ok = 0; score_mismatch = 0
no_deal = 0; no_phone = 0; fully_synced = 0
stage_mismatches_list = []
score_mismatches_list = []

for u in bot_users:
    phone = normalise_phone(u.get("phone", ""))
    if not phone:
        no_phone += 1
        continue
    deal = deal_by_phone.get(phone)
    person = person_by_phone.get(phone)
    if not deal:
        no_deal += 1
        continue
    matched += 1
    name = f"{u.get('first_name', '')} {u.get('last_name', '')}".strip()

    # Stage check
    exp = expected_stage_guid(u.get("completed_lessons", 0), u.get("current_lesson_number"), u.get("is_completed"))
    actual = deal.get("PipelineStageId", "")
    s_ok = (exp == actual)
    if s_ok:
        stage_ok += 1
    else:
        stage_mismatch += 1
        stage_mismatches_list.append(f"  {name}: CRM={STAGES.get(actual, actual[:8])} → expected={STAGES.get(exp, exp[:8])}")

    # Score check
    crm_score = 0
    if person:
        crm_score = int((person.get("Fields") or {}).get(LEAD_SCORE_FIELD, "0") or "0")
    bot_score = u.get("lead_score", 0)
    sc_ok = (crm_score == bot_score)
    if sc_ok:
        score_ok += 1
    else:
        score_mismatch += 1
        score_mismatches_list.append(f"  {name}: CRM={crm_score} → bot={bot_score}")

    if s_ok and sc_ok:
        fully_synced += 1

total = len(bot_users)
sync_rate = (fully_synced / matched * 100) if matched else 0

print(f"\n{'='*55}")
print(f"  📊 CRM AUDIT REPORT (After Backfill)")
print(f"{'='*55}")
print(f"  Total bot users:        {total}")
print(f"  With phone:             {total - no_phone}")
print(f"  Without phone:          {no_phone}")
print(f"  Matched to CRM deal:    {matched}")
print(f"  No CRM deal:            {no_deal}")
print(f"  ────────────────────────────────────")
print(f"  Stage matches:          {stage_ok}")
print(f"  Stage mismatches:       {stage_mismatch}")
print(f"  Score matches:          {score_ok}")
print(f"  Score mismatches:       {score_mismatch}")
print(f"  ────────────────────────────────────")
print(f"  ✅ Fully synced:        {fully_synced} / {matched}  ({sync_rate:.1f}%)")
print(f"{'='*55}")

if stage_mismatches_list:
    print(f"\n📌 Stage mismatches ({len(stage_mismatches_list)}):")
    for s in stage_mismatches_list[:20]:
        print(s)
    if len(stage_mismatches_list) > 20:
        print(f"  ... +{len(stage_mismatches_list)-20} more")

if score_mismatches_list:
    print(f"\n📊 Score mismatches ({len(score_mismatches_list)}):")
    for s in score_mismatches_list[:20]:
        print(s)
    if len(score_mismatches_list) > 20:
        print(f"  ... +{len(score_mismatches_list)-20} more")
