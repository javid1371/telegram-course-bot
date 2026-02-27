#!/usr/bin/env python3
"""
CRM Backfill Script — Syncs bot user data to Didar CRM.

Reads bot users from the audit API, fetches CRM deals, and updates:
1. Deal stages (lesson progress)
2. Person lead scores
3. Creates missing deals for users without CRM records

Run from the Telegram server:
    python3 /tmp/crm_backfill.py

Requires: urllib (stdlib only — no pip needed)
"""
import json
import urllib.request
import urllib.error
import time
import sys

# ─── Configuration ───
DIDAR_API_KEY = "1t31qjd4bl43cxej1yybhr2uf24ael2a"
DIDAR_BASE = "https://app.didar.me/api"
PIPELINE_ID = "9b0e5024-4822-4833-abe6-8ca426a937ae"

BOT_PANEL_URL = "http://193.163.201.132:8080"
BOT_ADMIN_USER = "admin"
BOT_ADMIN_PASS = "CourseBot@2024Admin"

LEAD_SCORE_FIELD = "Field_996_12_30"

STAGES = {
    "register": "b7e97097-ff9b-4207-a2e7-07dd2ea606af",
    "lesson_1": "ffa64a67-02e0-462b-a0c2-60c85eee6af5",
    "lesson_2": "bcfe1289-12bf-4ee6-88e7-2dcf0ed48469",
    "lesson_3": "4223a51c-544b-41e2-94bc-1e99016fbaba",
    "lesson_4": "09856491-6d78-40df-b3ed-c80083e77a8f",
    "lesson_5": "0fcb3769-e1ad-45d5-8847-e51e97065d85",
    "lesson_6": "aee7d1c1-5f18-43e8-b1cb-050d59ce3517",
    "lesson_7": "d9fc8133-052f-465b-9289-4211272b6e18",
    "lesson_8": "6faab0b4-be10-478d-9655-bf41eca744a8",
    "sales_wait": "6faab0b4-be10-478d-9655-bf41eca744a8",
}

OWNERS = [
    {"id": "a52a4294-f773-48cf-8201-d4402f7b7780", "name": "عباسی", "weight": 3},
    {"id": "f4d3c7ad-3fb4-42f3-bf78-04ca86a24a1f", "name": "غلامی", "weight": 2},
]

DRY_RUN = "--dry-run" in sys.argv
FORCE_DOWNGRADE = "--force-downgrade" in sys.argv

# ─── Helpers ──-
def normalise_phone(raw):
    if not raw:
        return ""
    digits = "".join(c for c in str(raw) if c.isdigit())
    return digits[-10:] if len(digits) >= 10 else digits


def didar_post(endpoint, body):
    """POST to Didar API with JSON body."""
    url = f"{DIDAR_BASE}/{endpoint}?apikey={DIDAR_API_KEY}"
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        resp = urllib.request.urlopen(req)
        return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        err = e.read().decode()[:500]
        print(f"  ❌ Didar API error {e.code}: {err}")
        return {"_error": True, "_code": e.code, "_message": err}


def search_person_by_phone(phone):
    """Search Didar for a person by phone and return first match."""
    norm = normalise_phone(phone)
    resp = didar_post("contact/PersonSearch", {
        "Criteria": {"Keywords": norm},
        "From": 0,
        "Limit": 5,
    })
    if not resp or resp.get("_error"):
        return None
    persons = (resp.get("Response") or {}).get("List", [])
    for p in persons:
        if normalise_phone(p.get("MobilePhone")) == norm:
            return p
    return persons[0] if persons else None


def expected_stage_guid(completed_lessons, current_lesson_number, is_completed):
    """Get expected stage GUID for a user.

    Logic:
    - current_lesson_number = the lesson they're ON (next to do)
    - completed_lessons = count of lessons with completed_at in UserProgress
    - CRM stages reflect the LAST COMPLETED lesson number
    - So CRM stage "lesson_3" = user completed lesson 3

    We use max of both signals to avoid data gaps.
    """
    if is_completed:
        return STAGES.get("lesson_8", STAGES["sales_wait"])
    # current_lesson means they're working on it, so completed up to (N-1)
    inferred_from_current = max(0, (current_lesson_number or 1) - 1)
    effective = max(completed_lessons or 0, inferred_from_current)
    if effective > 0:
        key = f"lesson_{min(effective, 8)}"
        return STAGES.get(key, STAGES["register"])
    return STAGES["register"]


def pick_owner(index):
    """Round-robin owner assignment based on weights."""
    # Simple weighted: repeat each owner by weight
    expanded = []
    for o in OWNERS:
        expanded.extend([o] * o["weight"])
    return expanded[index % len(expanded)]


# ─── Step 1: Get bot users ───
def get_bot_users():
    print("📋 Fetching bot users from panel...")
    # Login
    login_req = urllib.request.Request(
        f"{BOT_PANEL_URL}/api/auth/login",
        data=json.dumps({"username": BOT_ADMIN_USER, "password": BOT_ADMIN_PASS}).encode(),
        headers={"Content-Type": "application/json"},
    )
    resp = urllib.request.urlopen(login_req)
    token = json.loads(resp.read().decode()).get("access_token")
    if not token:
        print("❌ Login failed")
        sys.exit(1)

    # Fetch users
    users_req = urllib.request.Request(
        f"{BOT_PANEL_URL}/api/audit/users",
        headers={"Authorization": f"Bearer {token}"},
    )
    resp = urllib.request.urlopen(users_req)
    data = json.loads(resp.read().decode())
    users = data.get("items", [])
    print(f"  Got {len(users)} users")
    return users


# ─── Step 2: Get all CRM deals ───
def get_crm_deals():
    print("📋 Fetching CRM deals from Didar...")
    data = didar_post("deal/search_v2", {
        "Criteria": {"PipelineId": PIPELINE_ID},
        "From": 0,
        "Limit": 5000,
    })
    deals = (data or {}).get("search_respons", {}).get("List", [])
    if not deals:
        deals = (data or {}).get("Response", {}).get("List", [])
    print(f"  Got {len(deals)} deals")
    return deals


# ─── Step 3: Build lookups ───
def build_lookups(deals):
    """Build deal lookup by normalised phone (using embedded Person data)."""
    deal_by_phone = {}
    person_by_phone = {}
    for d in deals:
        person = d.get("Person") or d.get("Contact") or {}
        phones = [person.get("MobilePhone"), person.get("WorkPhone")]
        for ph in phones:
            norm = normalise_phone(ph)
            if norm:
                # Keep only Pending deals; prefer first match
                if norm not in deal_by_phone or d.get("Status") == "Pending":
                    deal_by_phone[norm] = d
                if norm not in person_by_phone:
                    person_by_phone[norm] = person
    return deal_by_phone, person_by_phone


# ─── Step 4: Update deal stage ───
def update_deal_stage(deal, new_stage_guid):
    """Update a deal's pipeline stage."""
    body = {
        "Deal": {
            "Id": deal["Id"],
            "PipelineStageId": new_stage_guid,
            "PipelineId": PIPELINE_ID,
        }
    }
    return didar_post("deal/save_v2", body)


# ─── Step 5: Update person lead score ───
def update_person_lead_score(person, lead_score):
    """Update a person's lead_score custom field.
    Didar needs: {Contact: {Id, Type, FirstName, LastName, OwnerId, Fields}}
    """
    first_name = person.get("FirstName", "")
    last_name = person.get("LastName", "")
    # Didar requires LastName — derive from DisplayName if empty
    if not last_name:
        display = person.get("DisplayName", "")
        parts = display.strip().split()
        if len(parts) >= 2:
            last_name = parts[-1]
            first_name = first_name or " ".join(parts[:-1])
        else:
            last_name = display or first_name or "-"
    if not first_name:
        first_name = person.get("DisplayName", "-") or "-"

    body = {
        "Contact": {
            "Id": person["Id"],
            "Type": "Person",
            "FirstName": first_name,
            "LastName": last_name,
            "OwnerId": person.get("OwnerId", OWNERS[0]["id"]),
            "Fields": {LEAD_SCORE_FIELD: str(lead_score)},
        }
    }
    return didar_post("contact/save", body)


# ─── Step 6: Create person + deal for missing users ───
def create_person_and_deal(user, owner):
    """Create a new person and deal in Didar CRM."""
    # Create person
    name = (user.get("first_name") or "") + " " + (user.get("last_name") or "")
    name = name.strip() or "Bot User"
    phone = user.get("phone", "")

    first_name = user.get("first_name") or name.split()[0]
    last_name = user.get("last_name") or (name.split()[-1] if len(name.split()) > 1 else "")
    if not last_name:
        last_name = first_name or "-"

    person_body = {
        "Contact": {
            "Type": "Person",
            "FirstName": first_name,
            "LastName": last_name,
            "MobilePhone": phone,
            "OwnerId": owner["id"],
            "VisibilityType": "Owner",
            "Fields": {LEAD_SCORE_FIELD: str(user.get("lead_score", 0))},
        }
    }
    print(f"    Creating person: {name} ({phone})...")
    resp = didar_post("contact/save", person_body)

    person_id = None
    if resp and not resp.get("_error"):
        # Parse person ID from response
        response_data = resp.get("Response") or resp
        person_id = response_data.get("Id")
        if not person_id and isinstance(response_data, dict):
            contact = response_data.get("Contact") or {}
            person_id = contact.get("Id")
    elif resp and "Duplicate" in resp.get("_message", ""):
        # Person already exists — search by phone
        print(f"    ℹ️  Person already exists, searching...")
        existing = search_person_by_phone(phone)
        if existing:
            person_id = existing.get("Id")
            print(f"    ✓ Found existing person: {person_id}")

    if not person_id:
        print(f"    ❌ Could not get person ID")
        return None

    # Create deal
    completed = user.get("completed_lessons", 0)
    lesson = user.get("current_lesson_number")
    stage_guid = expected_stage_guid(completed, lesson, user.get("is_completed"))
    deal_body = {
        "Deal": {
            "PersonId": person_id,
            "PipelineId": PIPELINE_ID,
            "PipelineStageId": stage_guid,
            "OwnerId": owner["id"],
            "Title": f"دوره خروج از بحران {name}",
            "CompanyId": "00000000-0000-0000-0000-000000000000",
            "Status": "Won" if user.get("is_completed") else "Pending",
        }
    }
    print(f"    Creating deal for {name}...")
    deal_resp = didar_post("deal/save_v2", deal_body)
    return deal_resp


# ─── Main ───
def main():
    mode_label = "🔍 DRY RUN" if DRY_RUN else "🚀 LIVE"
    print(f"\n{'='*50}")
    print(f"  CRM Backfill Script — {mode_label}")
    print(f"{'='*50}\n")

    bot_users = get_bot_users()
    deals = get_crm_deals()
    deal_by_phone, person_by_phone = build_lookups(deals)

    # Reverse stage lookup
    stage_to_name = {}
    for name, guid in STAGES.items():
        if guid not in stage_to_name:
            stage_to_name[guid] = name

    stats = {
        "total": 0,
        "no_phone": 0,
        "stage_updated": 0,
        "stage_already_ok": 0,
        "stage_downgrade_skipped": 0,
        "score_updated": 0,
        "score_already_ok": 0,
        "deal_created": 0,
        "deal_missing_skipped": 0,
        "errors": 0,
    }

    missing_users = []
    owner_index = 0

    for user in bot_users:
        stats["total"] += 1
        phone = normalise_phone(user.get("phone", ""))
        if not phone:
            stats["no_phone"] += 1
            continue

        deal = deal_by_phone.get(phone)
        person = person_by_phone.get(phone)
        name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
        lesson = user.get("current_lesson_number")
        completed = user.get("completed_lessons", 0)
        bot_score = user.get("lead_score", 0)
        is_completed = user.get("is_completed", False)

        if not deal:
            missing_users.append(user)
            continue

        # ── Check stage ──
        exp_stage_guid = expected_stage_guid(completed, lesson, is_completed)
        actual_stage_guid = deal.get("PipelineStageId", "")
        exp_stage_name = stage_to_name.get(exp_stage_guid, exp_stage_guid[:8])
        actual_stage_name = stage_to_name.get(actual_stage_guid, actual_stage_guid[:8])

        if actual_stage_guid != exp_stage_guid:
            # Check if this is a downgrade (CRM is ahead of bot)
            stage_order = list(STAGES.values())
            try:
                actual_idx = stage_order.index(actual_stage_guid)
            except ValueError:
                actual_idx = -1
            try:
                exp_idx = stage_order.index(exp_stage_guid)
            except ValueError:
                exp_idx = -1

            is_downgrade = exp_idx < actual_idx and actual_idx >= 0 and exp_idx >= 0

            if is_downgrade and not FORCE_DOWNGRADE:
                print(f"⚠️  {name} ({phone}) SKIP downgrade: {actual_stage_name} → {exp_stage_name}  [lesson={lesson}, completed={completed}]")
                stats["stage_downgrade_skipped"] += 1
            else:
                print(f"📌 {name} ({phone}) stage: {actual_stage_name} → {exp_stage_name}  [lesson={lesson}, completed={completed}]")
                if not DRY_RUN:
                    result = update_deal_stage(deal, exp_stage_guid)
                    if result and not result.get("_error"):
                        stats["stage_updated"] += 1
                    else:
                        stats["errors"] += 1
                    time.sleep(0.3)  # Rate limiting
                else:
                    stats["stage_updated"] += 1
        else:
            stats["stage_already_ok"] += 1

        # ── Check lead score ──
        if person:
            crm_score = int((person.get("Fields") or {}).get(LEAD_SCORE_FIELD, "0") or "0")
            if crm_score != bot_score:
                print(f"📊 {name} ({phone}) score: {crm_score} → {bot_score}")
                if not DRY_RUN:
                    result = update_person_lead_score(person, bot_score)
                    if result and not result.get("_error"):
                        stats["score_updated"] += 1
                    else:
                        stats["errors"] += 1
                    time.sleep(0.3)
                else:
                    stats["score_updated"] += 1
            else:
                stats["score_already_ok"] += 1

    # ── Create missing deals ──
    print(f"\n{'─'*50}")
    print(f"📦 {len(missing_users)} users without CRM deals")
    print(f"{'─'*50}")

    for user in missing_users:
        phone = user.get("phone", "")
        name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
        owner = pick_owner(owner_index)
        owner_index += 1

        print(f"  ➕ {name} ({phone}) → owner: {owner['name']}")
        if not DRY_RUN:
            result = create_person_and_deal(user, owner)
            if result and not result.get("_error"):
                stats["deal_created"] += 1
            else:
                stats["errors"] += 1
            time.sleep(0.5)
        else:
            stats["deal_created"] += 1

    # ── Summary ──
    print(f"\n{'='*50}")
    print(f"  📊 Backfill Summary — {mode_label}")
    print(f"{'='*50}")
    print(f"  Total users:          {stats['total']}")
    print(f"  Without phone:        {stats['no_phone']}")
    print(f"  Stages updated:       {stats['stage_updated']}")
    print(f"  Stages already OK:    {stats['stage_already_ok']}")
    print(f"  Downgrades skipped:   {stats['stage_downgrade_skipped']}")
    print(f"  Scores updated:       {stats['score_updated']}")
    print(f"  Scores already OK:    {stats['score_already_ok']}")
    print(f"  Deals created:        {stats['deal_created']}")
    print(f"  Errors:               {stats['errors']}")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()
