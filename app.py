"""
NaijaPlate AI — WhatsApp Bot
────────────────────────────
Twilio WhatsApp Sandbox + Flask webhook
Deploy on Railway or Render (free tier)

Run locally:  python whatsapp_bot.py
"""

import os
import json
import random
import re
from datetime import datetime
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client

# ─────────────────────────────────────────────────────────────────────────────
# APP SETUP
# ─────────────────────────────────────────────────────────────────────────────

app = Flask(__name__)

# Twilio credentials — set as environment variables (never hardcode!)
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN  = os.environ.get("TWILIO_AUTH_TOKEN",  "")

# ─────────────────────────────────────────────────────────────────────────────
# SESSION STORE  (in-memory; resets on server restart)
# For production, swap this for Redis or a simple SQLite file
# ─────────────────────────────────────────────────────────────────────────────

sessions = {}   # { "whatsapp:+2348012345678": { ...user state... } }

def get_session(phone: str) -> dict:
    if phone not in sessions:
        sessions[phone] = {
            "step":       "welcome",   # conversation FSM state
            "profile":    {},
            "last_plan":  None,
            "onboarding": {},          # temp storage during multi-step onboarding
        }
    return sessions[phone]

def save_session(phone: str, session: dict):
    sessions[phone] = session

# ─────────────────────────────────────────────────────────────────────────────
# NIGERIAN MEAL DATABASE  (subset of full 64-dish DB — 30 dishes for bot speed)
# ─────────────────────────────────────────────────────────────────────────────

MEAL_DB = [
    # BREAKFAST
    {"id":1,  "name":"Akara & Ogi (Pap)",              "type":"Breakfast","calories":380,"protein":18,"carbs":55,"fat":10,"cost":350, "allergens":["legumes"],         "tags":["High-Protein","Diabetic-Friendly","Budget-Friendly"]},
    {"id":2,  "name":"Moi Moi & Custard",              "type":"Breakfast","calories":420,"protein":22,"carbs":60,"fat":11,"cost":500, "allergens":["eggs","milk"],      "tags":["High-Protein","Budget-Friendly"]},
    {"id":3,  "name":"Yam & Egg Sauce",                "type":"Breakfast","calories":510,"protein":20,"carbs":70,"fat":18,"cost":600, "allergens":["eggs"],             "tags":["High-Protein","Energy-Boost"]},
    {"id":4,  "name":"Boli & Groundnut",               "type":"Breakfast","calories":440,"protein":10,"carbs":72,"fat":14,"cost":300, "allergens":["groundnut"],        "tags":["Budget-Friendly","Vegan"]},
    {"id":5,  "name":"Oatmeal & Tiger Nuts Milk",      "type":"Breakfast","calories":340,"protein":9, "carbs":58,"fat":8, "cost":450, "allergens":[],                   "tags":["Diabetic-Friendly","Weight-Loss","Hypertension-Friendly"]},
    {"id":6,  "name":"Agege Bread & Ewa Agoyin",       "type":"Breakfast","calories":580,"protein":20,"carbs":90,"fat":14,"cost":400, "allergens":["gluten","legumes"], "tags":["Budget-Friendly","High-Carb"]},
    {"id":7,  "name":"Sweet Potato & Egg Omelette",    "type":"Breakfast","calories":380,"protein":19,"carbs":45,"fat":14,"cost":550, "allergens":["eggs"],             "tags":["Diabetic-Friendly","Weight-Loss"]},
    {"id":8,  "name":"Kunu & Masa",                    "type":"Breakfast","calories":310,"protein":7, "carbs":58,"fat":5, "cost":280, "allergens":["gluten"],           "tags":["Low-Fat","Budget-Friendly","Diabetic-Friendly"]},
    {"id":9,  "name":"Grilled Fish & Fried Plantain",  "type":"Breakfast","calories":520,"protein":38,"carbs":48,"fat":16,"cost":900, "allergens":["fish"],             "tags":["High-Protein","Muscle-Building","Omega-3"]},
    {"id":10, "name":"Unripe Plantain Porridge",       "type":"Breakfast","calories":350,"protein":12,"carbs":58,"fat":9, "cost":420, "allergens":["fish"],             "tags":["Diabetic-Friendly","Low-Sugar","Heart-Healthy"]},
    # LUNCH
    {"id":11, "name":"Jollof Rice & Grilled Chicken",  "type":"Lunch",    "calories":650,"protein":42,"carbs":80,"fat":16,"cost":1200,"allergens":[],                   "tags":["High-Protein","Muscle-Building"]},
    {"id":12, "name":"Egusi Soup & Pounded Yam",       "type":"Lunch",    "calories":720,"protein":35,"carbs":75,"fat":32,"cost":1500,"allergens":[],                   "tags":["High-Protein","Traditional"]},
    {"id":13, "name":"Efo Riro & Brown Rice",          "type":"Lunch",    "calories":540,"protein":32,"carbs":55,"fat":20,"cost":1100,"allergens":[],                   "tags":["Diabetic-Friendly","Weight-Loss","Hypertension-Friendly"]},
    {"id":14, "name":"Beans Porridge & Fried Plantain","type":"Lunch",    "calories":620,"protein":28,"carbs":88,"fat":15,"cost":700, "allergens":["legumes","fish"],   "tags":["High-Protein","Budget-Friendly"]},
    {"id":15, "name":"Chicken Pepper Soup",            "type":"Lunch",    "calories":310,"protein":38,"carbs":8, "fat":14,"cost":1100,"allergens":[],                   "tags":["Low-Carb","Keto-Friendly","Ulcer-Friendly"]},
    {"id":16, "name":"Ofada Rice & Ayamase Stew",      "type":"Lunch",    "calories":690,"protein":34,"carbs":80,"fat":26,"cost":1300,"allergens":[],                   "tags":["Antioxidant-Rich","Traditional"]},
    {"id":17, "name":"Vegetable Yam Porridge (Asaro)", "type":"Lunch",    "calories":480,"protein":18,"carbs":72,"fat":14,"cost":700, "allergens":["fish"],             "tags":["Diabetic-Friendly","Budget-Friendly","Weight-Loss"]},
    {"id":18, "name":"Suya & Yaji Salad",              "type":"Lunch",    "calories":430,"protein":42,"carbs":20,"fat":22,"cost":900, "allergens":["groundnut"],        "tags":["High-Protein","Low-Carb","Keto-Friendly"]},
    {"id":19, "name":"Moi Moi & Nigerian Salad",       "type":"Lunch",    "calories":420,"protein":28,"carbs":45,"fat":14,"cost":800, "allergens":["eggs","legumes"],   "tags":["High-Protein","Weight-Loss"]},
    {"id":20, "name":"Miyan Taushe & Tuwon Masara",    "type":"Lunch",    "calories":620,"protein":28,"carbs":75,"fat":22,"cost":850, "allergens":["groundnut"],        "tags":["High-Fiber","Hypertension-Friendly"]},
    # DINNER
    {"id":21, "name":"Grilled Chicken & Roasted Veggies","type":"Dinner", "calories":420,"protein":48,"carbs":18,"fat":16,"cost":1400,"allergens":[],                   "tags":["High-Protein","Low-Carb","Weight-Loss","Muscle-Building"]},
    {"id":22, "name":"Ofe Akwu & Eba",                 "type":"Dinner",   "calories":680,"protein":36,"carbs":60,"fat":34,"cost":1200,"allergens":[],                   "tags":["High-Protein","Traditional"]},
    {"id":23, "name":"Beef Pepper Soup",               "type":"Dinner",   "calories":320,"protein":40,"carbs":6, "fat":16,"cost":1100,"allergens":[],                   "tags":["Low-Carb","Keto-Friendly","Ulcer-Friendly"]},
    {"id":24, "name":"Baked Tilapia & Coconut Rice",   "type":"Dinner",   "calories":540,"protein":40,"carbs":60,"fat":16,"cost":1600,"allergens":["fish"],             "tags":["High-Protein","Heart-Healthy","Omega-3"]},
    {"id":25, "name":"Plantain Frittata",              "type":"Dinner",   "calories":400,"protein":22,"carbs":44,"fat":16,"cost":700, "allergens":["eggs"],             "tags":["High-Protein","Gluten-Free","Weight-Loss"]},
    {"id":26, "name":"Vegetable Fried Rice (Vegan)",   "type":"Dinner",   "calories":450,"protein":10,"carbs":82,"fat":9, "cost":700, "allergens":[],                   "tags":["Vegan","Low-Fat","Heart-Healthy"]},
    {"id":27, "name":"Ogbono Soup & Semo",             "type":"Dinner",   "calories":640,"protein":34,"carbs":62,"fat":30,"cost":1100,"allergens":["okra"],             "tags":["Traditional","High-Protein"]},
    {"id":28, "name":"Turkey & Vegetable Stew & Yam",  "type":"Dinner",   "calories":560,"protein":40,"carbs":60,"fat":14,"cost":1500,"allergens":[],                   "tags":["High-Protein","Balanced","Weight-Loss"]},
    {"id":29, "name":"Light Vegetable Soup & Plantain","type":"Dinner",   "calories":350,"protein":14,"carbs":55,"fat":8, "cost":650, "allergens":["soy"],              "tags":["Vegan","Low-Calorie","Weight-Loss","Diabetic-Friendly"]},
    {"id":30, "name":"Goat Meat Stew & Boiled Yam",    "type":"Dinner",   "calories":620,"protein":44,"carbs":58,"fat":22,"cost":1800,"allergens":[],                   "tags":["High-Protein","Traditional","Weekend-Special"]},
]

DAILY_TIPS = [
    "💡 *Naija Tip:* Swap white garri for unripe plantain fufu — more fibre, lower sugar spike!",
    "💡 *Naija Tip:* Pepper soup is basically protein broth — great post-workout meal!",
    "💡 *Naija Tip:* Tiger nuts (aya/ofio) are great for gut health and blood sugar.",
    "💡 *Naija Tip:* Drink unsweetened zobo — hibiscus can help lower blood pressure slightly.",
    "💡 *Naija Tip:* Ofada rice has more antioxidants than polished white rice. Switch am!",
    "💡 *Naija Tip:* Fresh fish 3x per week gives your heart the omega-3 it needs. E good jara!",
    "💡 *Naija Tip:* Unripe plantain has a low glycaemic index — better for diabetics than ripe.",
    "💡 *Naija Tip:* A 30-min walk daily can reduce hypertension risk by up to 30%!",
]

CONDITION_TAGS = {
    "diabetes":      ["Diabetic-Friendly","Low-Sugar","Low-Carb","High-Fiber"],
    "hypertension":  ["Hypertension-Friendly","Low-Fat","High-Fiber","Heart-Healthy"],
    "cholesterol":   ["Heart-Healthy","Low-Fat","Omega-3"],
    "ulcer":         ["Ulcer-Friendly","Low-Carb"],
    "weight loss":   ["Weight-Loss","Low-Calorie","Low-Fat"],
    "muscle":        ["High-Protein","Muscle-Building"],
}

ALLERGEN_MAP = {
    "groundnut": "groundnut", "peanut": "groundnut",
    "fish":      "fish",      "seafood": "fish",
    "egg":       "eggs",      "eggs": "eggs",
    "milk":      "milk",      "dairy": "milk", "lactose": "milk",
    "gluten":    "gluten",    "wheat": "gluten",
    "soy":       "soy",
    "okra":      "okra",
    "legume":    "legumes",   "bean": "legumes", "beans": "legumes",
    "shellfish": "shellfish", "shrimp": "shellfish",
}

# ─────────────────────────────────────────────────────────────────────────────
# NUTRITION ENGINE
# ─────────────────────────────────────────────────────────────────────────────

def calc_bmr(weight, height, age, gender):
    if gender == "male":
        return 10 * weight + 6.25 * height - 5 * age + 5
    return 10 * weight + 6.25 * height - 5 * age - 161

def calc_targets(profile):
    bmr  = calc_bmr(profile["weight"], profile["height"], profile["age"], profile["gender"])
    tdee = bmr * profile.get("activity_factor", 1.375)
    goal = profile.get("goal", "wellness").lower()
    if "loss" in goal:      cal = tdee * 0.80
    elif "gain" in goal:    cal = tdee * 1.20
    elif "muscle" in goal:  cal = tdee * 1.10
    else:                   cal = tdee
    return {"calories": round(cal), "protein": round(cal * 0.25 / 4),
            "carbs": round(cal * 0.45 / 4), "fat": round(cal * 0.30 / 9)}

def filter_meals(profile, meal_type, n=3):
    allergens   = profile.get("allergens", [])
    conditions  = profile.get("conditions", [])
    budget      = profile.get("budget", 3000) / 3 * 1.3  # per-meal budget with 30% flex
    prefer_tags = []
    for cond in conditions:
        prefer_tags += CONDITION_TAGS.get(cond.lower(), [])

    scored = []
    for meal in MEAL_DB:
        if meal["type"] != meal_type:
            continue
        # hard filter: allergens
        if any(a in meal["allergens"] for a in allergens):
            continue
        # hard filter: budget
        if meal["cost"] > budget:
            continue
        # score
        score = 100
        for tag in prefer_tags:
            if tag in meal["tags"]:
                score += 15
        scored.append((score + random.randint(0, 10), meal))

    scored.sort(key=lambda x: -x[0])
    return [m for _, m in scored[:n]]

def generate_plan(profile):
    plan = {}
    for mtype in ["Breakfast", "Lunch", "Dinner"]:
        options = filter_meals(profile, mtype, n=3)
        plan[mtype] = options[0] if options else None
    return plan

def plan_summary(plan, targets):
    total_cal  = sum(m["calories"] for m in plan.values() if m)
    total_prot = sum(m["protein"]  for m in plan.values() if m)
    total_cost = sum(m["cost"]     for m in plan.values() if m)
    pct = round(total_cal / targets["calories"] * 100) if targets["calories"] else 0
    return total_cal, total_prot, total_cost, pct

# ─────────────────────────────────────────────────────────────────────────────
# NLP INTENT PARSER
# ─────────────────────────────────────────────────────────────────────────────

def parse_intent(text: str) -> str:
    t = text.lower().strip()

    if any(w in t for w in ["hi","hello","hey","start","begin","ẹ káàárọ̀","good morning","good afternoon","good evening","howdy","sup"]):
        return "greet"
    if any(w in t for w in ["menu","help","what can","options","commands","list"]):
        return "menu"
    if any(w in t for w in ["meal","plan","suggest","eat","food","today","breakfast","lunch","dinner","recommend"]):
        return "get_plan"
    if any(w in t for w in ["week","7 day","7-day","weekly"]):
        return "weekly"
    if any(w in t for w in ["calorie","macro","target","nutrition","how much should"]):
        return "macros"
    if any(w in t for w in ["tip","advice","naija tip","health tip","learn"]):
        return "tip"
    if any(w in t for w in ["profile","setup","update","change my","edit","set my","my age","my weight","my height"]):
        return "setup"
    if any(w in t for w in ["budget","cost","cheap","affordable","price"]):
        return "budget_info"
    if any(w in t for w in ["allerg","intoleran","avoid","can't eat","cannot eat","i don't eat","i no dey eat"]):
        return "allergy_info"
    if any(w in t for w in ["shopping","buy","market","list","ingredients"]):
        return "shopping"
    if any(w in t for w in ["bmi","weight","how fat","how thin","check my"]):
        return "bmi"
    if any(w in t for w in ["bye","exit","stop","quit","done"]):
        return "bye"
    if t in [str(i) for i in range(1, 10)]:
        return f"menu_{t}"

    return "unknown"

# ─────────────────────────────────────────────────────────────────────────────
# QUICK PROFILE EXTRACTOR FROM FREE TEXT
# (e.g. "I am 28, female, 62kg, 165cm, weight loss, budget 2000")
# ─────────────────────────────────────────────────────────────────────────────

def extract_profile_from_text(text: str) -> dict:
    profile = {}
    t = text.lower()

    # Age
    age_match = re.search(r'\b(\d{1,2})\s*(years?|yrs?|yr)?\s*(old)?\b', t)
    if age_match:
        age = int(age_match.group(1))
        if 10 <= age <= 100:
            profile["age"] = age

    # Gender
    if any(w in t for w in ["female","woman","girl","lady","she/her"]):
        profile["gender"] = "female"
    elif any(w in t for w in ["male","man","guy","boy","he/him"]):
        profile["gender"] = "male"

    # Weight (kg)
    w_match = re.search(r'(\d{2,3})\s*kg', t)
    if w_match:
        profile["weight"] = int(w_match.group(1))

    # Height (cm)
    h_match = re.search(r'(\d{3})\s*cm', t)
    if h_match:
        profile["height"] = int(h_match.group(1))

    # Budget
    b_match = re.search(r'(?:₦|naira|budget|ngn)\s*(\d{3,6})', t)
    if not b_match:
        b_match = re.search(r'(\d{3,6})\s*(?:₦|naira|ngn)', t)
    if b_match:
        profile["budget"] = int(b_match.group(1))

    # Goal
    if any(w in t for w in ["lose weight","weight loss","slim","slimming","cut down","reduce"]):
        profile["goal"] = "weight loss"
    elif any(w in t for w in ["gain weight","bulk","bulking","add weight"]):
        profile["goal"] = "weight gain"
    elif any(w in t for w in ["muscle","build","gym","strength"]):
        profile["goal"] = "muscle building"
    elif any(w in t for w in ["diabetes","blood sugar","sugar control"]):
        profile["goal"] = "blood sugar control"
    elif any(w in t for w in ["energy","active","fit"]):
        profile["goal"] = "energy boost"

    # Activity
    if any(w in t for w in ["very active","athlete","intense","daily gym"]):
        profile["activity_factor"] = 1.725
    elif any(w in t for w in ["moderately","moderate","3-5","gym sometimes"]):
        profile["activity_factor"] = 1.55
    elif any(w in t for w in ["lightly","light","1-3","walk sometimes"]):
        profile["activity_factor"] = 1.375
    elif any(w in t for w in ["sedentary","office","no exercise","desk"]):
        profile["activity_factor"] = 1.2

    # Conditions
    conditions = []
    if any(w in t for w in ["diabetes","diabetic","type 2","blood sugar"]):
        conditions.append("diabetes")
    if any(w in t for w in ["hypertension","high blood pressure","bp"]):
        conditions.append("hypertension")
    if any(w in t for w in ["cholesterol","high cholesterol"]):
        conditions.append("cholesterol")
    if any(w in t for w in ["ulcer","stomach ulcer"]):
        conditions.append("ulcer")
    if conditions:
        profile["conditions"] = conditions

    # Allergens
    user_allergens = []
    for key, val in ALLERGEN_MAP.items():
        if key in t and val not in user_allergens:
            user_allergens.append(val)
    if user_allergens:
        profile["allergens"] = user_allergens

    return profile

# ─────────────────────────────────────────────────────────────────────────────
# RESPONSE BUILDERS
# ─────────────────────────────────────────────────────────────────────────────

MAIN_MENU = """🍲 *NaijaPlate AI Menu*
━━━━━━━━━━━━━━━━━━━
Reply with a number or just type naturally:

*1* — 🍽️ Get today's meal plan
*2* — 📅 Get weekly meal plan
*3* — 🧮 See my calorie targets
*4* — 🛒 Shopping list
*5* — 💡 Health tip
*6* — ⚖️ Check my BMI
*7* — 👤 Update my profile
*8* — ℹ️ About NaijaPlate AI

Or just type what you want, e.g:
_"suggest a diabetic-friendly lunch"_
_"I want to lose weight, I'm 75kg"_"""

def welcome_msg(is_new: bool) -> str:
    if is_new:
        return """🇳🇬 *Welcome to NaijaPlate AI!* 🍲

Your smart Nigerian meal planner on WhatsApp!

To get started, tell me a bit about yourself. Just type naturally, e.g:

_"I'm 28, female, 68kg, 165cm, want to lose weight, budget ₦2500, I don't eat fish"_

Or type *MENU* to see all options.

E go sweet! 😄"""
    return f"""👋 Welcome back to *NaijaPlate AI!*

Type *MENU* to see options or just tell me what you need.
E.g: _"Give me today's meal plan"_"""

def format_meal_plan(plan, profile) -> str:
    targets = calc_targets(profile) if profile.get("weight") else {"calories": 2000, "protein": 125, "carbs": 225, "fat": 67}
    total_cal, total_prot, total_cost, pct = plan_summary(plan, targets)

    lines = ["🍽️ *Today's NaijaPlate Meal Plan*", "━━━━━━━━━━━━━━━━━━━"]
    emojis = {"Breakfast": "🌅", "Lunch": "☀️", "Dinner": "🌙"}

    for mtype in ["Breakfast", "Lunch", "Dinner"]:
        meal = plan.get(mtype)
        if meal:
            lines.append(f"\n{emojis[mtype]} *{mtype}*")
            lines.append(f"🍲 {meal['name']}")
            lines.append(f"🔥 {meal['calories']} kcal  💪 {meal['protein']}g protein  💰 ₦{meal['cost']:,}")
            if meal.get("tags"):
                lines.append(f"🏷️ {' · '.join(meal['tags'][:3])}")
        else:
            lines.append(f"\n{emojis[mtype]} *{mtype}*")
            lines.append("⚠️ No match found — try updating your budget or allergies")

    lines.append("\n━━━━━━━━━━━━━━━━━━━")
    lines.append(f"📊 *Daily Totals*")
    lines.append(f"🔥 {total_cal} kcal ({pct}% of your {targets['calories']} kcal target)")
    lines.append(f"💪 {total_prot}g protein  💰 ₦{total_cost:,} total")
    lines.append("\nReply *MENU* for more options or *REGEN* to regenerate 🔄")
    return "\n".join(lines)

def format_weekly_plan(profile) -> str:
    days = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    lines = ["📅 *Your 7-Day NaijaPlate Plan*", "━━━━━━━━━━━━━━━━━━━"]
    used = []
    for day in days:
        plan = generate_plan(profile)
        lines.append(f"\n*{day}*")
        for mtype in ["Breakfast","Lunch","Dinner"]:
            m = plan.get(mtype)
            if m:
                lines.append(f"  {'🌅' if mtype=='Breakfast' else '☀️' if mtype=='Lunch' else '🌙'} {m['name']} (₦{m['cost']:,})")
    lines.append("\n━━━━━━━━━━━━━━━━━━━")
    lines.append("Reply *SHOP* for the full shopping list 🛒")
    return "\n".join(lines)

def format_macros(profile) -> str:
    if not profile.get("weight"):
        return ("⚠️ I need your profile to calculate targets!\n\n"
                "Tell me: _\"I'm 30, male, 75kg, 175cm, moderately active\"_")
    t = calc_targets(profile)
    bmi = round(profile["weight"] / ((profile["height"]/100)**2), 1) if profile.get("height") else "?"
    cat = ("Underweight" if isinstance(bmi,float) and bmi<18.5
           else "Healthy ✅" if isinstance(bmi,float) and bmi<25
           else "Overweight ⚠️" if isinstance(bmi,float) and bmi<30
           else "Obese 🔴")
    return f"""🧮 *Your Daily Nutrition Targets*
━━━━━━━━━━━━━━━━━━━
⚖️ BMI: *{bmi}* ({cat})
🎯 Goal: *{profile.get('goal','General Wellness').title()}*

🔥 Calories: *{t['calories']} kcal/day*
💪 Protein:  *{t['protein']}g/day*
🍞 Carbs:    *{t['carbs']}g/day*
🥑 Fat:      *{t['fat']}g/day*

💰 Daily Budget: *₦{profile.get('budget',3000):,}*
━━━━━━━━━━━━━━━━━━━
These targets are based on your profile.
Reply *1* to get a meal plan that hits these targets!"""

def format_shopping(profile) -> str:
    all_ingredients = {}
    for _ in range(7):  # week's worth
        plan = generate_plan(profile)
        for meal in plan.values():
            if meal:
                for ing in meal.get("ingredients", [meal["name"]]):
                    all_ingredients[ing] = all_ingredients.get(ing, 0) + 1

    lines = ["🛒 *Weekly Shopping List*", "━━━━━━━━━━━━━━━━━━━"]
    for item, count in sorted(all_ingredients.items(), key=lambda x: -x[1])[:20]:
        lines.append(f"• {item.title()} ×{count}")
    lines.append("\n━━━━━━━━━━━━━━━━━━━")
    lines.append(f"💡 Pro tip: Shop at your local market on weekends for the best prices!")
    return "\n".join(lines)

def format_bmi(profile) -> str:
    if not profile.get("weight") or not profile.get("height"):
        return ("⚠️ I need your weight and height to calculate BMI.\n\n"
                "Tell me: _\"I'm 75kg, 175cm\"_")
    bmi = round(profile["weight"] / ((profile["height"]/100)**2), 1)
    if bmi < 18.5:   cat, advice = "Underweight 📉", "You need to eat more nutritious meals. Consider weight gain plan!"
    elif bmi < 25:   cat, advice = "Healthy Weight ✅", "You're in great shape! Focus on maintaining with balanced meals."
    elif bmi < 30:   cat, advice = "Overweight ⚠️", "Time to cut down on carbs & fried food. I can help with a weight loss plan!"
    else:            cat, advice = "Obese 🔴", "Please see a doctor and let's get you on a structured meal plan."
    return f"""⚖️ *Your BMI Check*
━━━━━━━━━━━━━━━━━━━
Weight: *{profile['weight']}kg*
Height: *{profile['height']}cm*
BMI:    *{bmi}*
Status: *{cat}*

💬 {advice}
━━━━━━━━━━━━━━━━━━━
Reply *1* to get a personalised meal plan!"""

def format_profile_confirm(profile) -> str:
    lines = ["✅ *Profile Updated!*", "━━━━━━━━━━━━━━━━━━━"]
    if profile.get("age"):       lines.append(f"🎂 Age: {profile['age']} yrs")
    if profile.get("gender"):    lines.append(f"👤 Gender: {profile['gender'].title()}")
    if profile.get("weight"):    lines.append(f"⚖️ Weight: {profile['weight']}kg")
    if profile.get("height"):    lines.append(f"📏 Height: {profile['height']}cm")
    if profile.get("goal"):      lines.append(f"🎯 Goal: {profile['goal'].title()}")
    if profile.get("budget"):    lines.append(f"💰 Budget: ₦{profile['budget']:,}/day")
    if profile.get("allergens"): lines.append(f"⚠️ Allergies: {', '.join(profile['allergens'])}")
    if profile.get("conditions"):lines.append(f"🏥 Conditions: {', '.join(profile['conditions'])}")
    lines.append("\nReply *1* to get your personalised meal plan now! 🍽️")
    return "\n".join(lines)

# ─────────────────────────────────────────────────────────────────────────────
# MAIN CONVERSATION HANDLER
# ─────────────────────────────────────────────────────────────────────────────

def handle_message(phone: str, text: str) -> str:
    session = get_session(phone)
    profile = session.get("profile", {})
    intent  = parse_intent(text)
    t       = text.lower().strip()

    # ── Handle REGEN shortcut ──────────────────────────────────────────────
    if t in ["regen", "regenerate", "new plan", "try again"]:
        plan = generate_plan(profile) if profile.get("weight") else generate_plan({"budget":3000,"allergens":[],"conditions":[]})
        session["last_plan"] = plan
        save_session(phone, session)
        return format_meal_plan(plan, profile)

    if t in ["shop", "shopping"]:
        return format_shopping(profile or {"budget":3000,"allergens":[],"conditions":[]})

    # ── Handle numbered menu shortcuts ────────────────────────────────────
    menu_map = {
        "1": "get_plan", "2": "weekly", "3": "macros",
        "4": "shopping", "5": "tip",    "6": "bmi",
        "7": "setup",    "8": "about",
    }
    if t in menu_map:
        intent = menu_map[t]

    # ── WELCOME / GREET ───────────────────────────────────────────────────
    if intent == "greet" or session["step"] == "welcome":
        is_new = not bool(profile.get("weight"))
        session["step"] = "idle"
        save_session(phone, session)
        return welcome_msg(is_new)

    # ── MAIN MENU ─────────────────────────────────────────────────────────
    if intent == "menu":
        return MAIN_MENU

    # ── GET TODAY'S MEAL PLAN ─────────────────────────────────────────────
    if intent == "get_plan":
        p = profile if profile.get("weight") else {"budget":3000,"allergens":[],"conditions":[],"activity_factor":1.375,"goal":"wellness"}
        plan = generate_plan(p)
        session["last_plan"] = plan
        save_session(phone, session)
        return format_meal_plan(plan, p)

    # ── WEEKLY PLAN ───────────────────────────────────────────────────────
    if intent == "weekly":
        p = profile if profile.get("weight") else {"budget":3000,"allergens":[],"conditions":[],"activity_factor":1.375}
        return format_weekly_plan(p)

    # ── MACROS / TARGETS ──────────────────────────────────────────────────
    if intent == "macros":
        return format_macros(profile)

    # ── TIP ───────────────────────────────────────────────────────────────
    if intent == "tip":
        return random.choice(DAILY_TIPS) + "\n\nReply *MENU* for more options."

    # ── BMI ───────────────────────────────────────────────────────────────
    if intent == "bmi":
        return format_bmi(profile)

    # ── SHOPPING LIST ─────────────────────────────────────────────────────
    if intent == "shopping":
        p = profile if profile.get("weight") else {"budget":3000,"allergens":[],"conditions":[]}
        return format_shopping(p)

    # ── SETUP / UPDATE PROFILE ────────────────────────────────────────────
    if intent == "setup":
        session["step"] = "collecting_profile"
        save_session(phone, session)
        return """👤 *Update Your Profile*
━━━━━━━━━━━━━━━━━━━
Just tell me about yourself in one message! E.g:

_"I'm 28, female, 62kg, 165cm, want to lose weight, budget ₦2000, I don't eat fish or eggs, I have diabetes"_

Include whatever applies to you — age, gender, weight (kg), height (cm), goal, daily budget in ₦, allergies, and medical conditions."""

    # ── ABOUT ─────────────────────────────────────────────────────────────
    if intent == "about":
        return """ℹ️ *About NaijaPlate AI*
━━━━━━━━━━━━━━━━━━━
🇳🇬 NaijaPlate AI is your smart Nigerian meal planner built with love for everyday Nigerians.

✅ 64 authentic Nigerian dishes
✅ Personalised to your health goals
✅ Works with your daily budget
✅ Manages allergies & medical conditions
✅ Calculates your calorie & macro targets
✅ Available 24/7 on WhatsApp

*Built for Nigeria, by Nigerians.* 💚

Type *MENU* to get started!"""

    # ── BYE ───────────────────────────────────────────────────────────────
    if intent == "bye":
        return "👋 Take care and *chop well*! Come back anytime for your NaijaPlate meal plan. 🍲🇳🇬"

    # ── PROFILE COLLECTION (multi-turn) ───────────────────────────────────
    if session["step"] == "collecting_profile":
        extracted = extract_profile_from_text(text)
        if extracted:
            # Merge with existing profile
            profile.update(extracted)
            session["profile"] = profile
            session["step"] = "idle"
            save_session(phone, session)
            reply = format_profile_confirm(profile)
            return reply
        else:
            return ("🤔 I couldn't quite catch your details. Try something like:\n\n"
                    "_\"I'm 28, female, 62kg, 165cm, lose weight, budget ₦2500, no fish\"_\n\n"
                    "Or type *MENU* to explore options.")

    # ── FREE TEXT PROFILE UPDATE (any message that has profile info) ───────
    extracted = extract_profile_from_text(text)
    if extracted and len(extracted) >= 2:  # at least 2 fields detected
        profile.update(extracted)
        session["profile"] = profile
        session["step"] = "idle"
        save_session(phone, session)
        confirm = format_profile_confirm(profile)
        plan = generate_plan(profile)
        session["last_plan"] = plan
        save_session(phone, session)
        return confirm + "\n\n" + format_meal_plan(plan, profile)

    # ── UNKNOWN ───────────────────────────────────────────────────────────
    fallbacks = [
        "🤔 I didn't quite get that. Type *MENU* to see what I can do!",
        "😄 Omo, I no understand that one! Try typing *MENU* or *1* for a meal plan.",
        "🍲 Hmm, not sure what you mean. Type *MENU* for options or *1* for today's meal plan!",
    ]
    return random.choice(fallbacks)

# ─────────────────────────────────────────────────────────────────────────────
# FLASK WEBHOOK ROUTES
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/", methods=["GET"])
def index():
    """Health check endpoint — Railway/Render will ping this"""
    return {"status": "NaijaPlate AI WhatsApp Bot is running! 🍲🇳🇬", "version": "1.0"}, 200

@app.route("/webhook", methods=["POST"])
def webhook():
    """
    Twilio sends POST here whenever a WhatsApp message is received.
    Configure this URL in your Twilio Sandbox settings.
    """
    incoming_msg = request.values.get("Body",    "").strip()
    sender_phone = request.values.get("From",    "")   # e.g. "whatsapp:+2348012345678"

    app.logger.info(f"MSG from {sender_phone}: {incoming_msg}")

    # Generate reply
    reply_text = handle_message(sender_phone, incoming_msg)

    # Build TwiML response
    resp = MessagingResponse()
    msg  = resp.message()

    # WhatsApp messages max ~1600 chars — split if needed
    if len(reply_text) <= 1600:
        msg.body(reply_text)
    else:
        # Send first chunk, append continuation note
        chunk = reply_text[:1550]
        last_newline = chunk.rfind("\n")
        if last_newline > 0:
            chunk = chunk[:last_newline]
        msg.body(chunk + "\n\n_(Reply *MORE* for the rest)_")
        # Store overflow in session for next message (simple approach)
        phone = sender_phone
        session = get_session(phone)
        session["overflow"] = reply_text[len(chunk):]
        save_session(phone, session)

    return str(resp), 200, {"Content-Type": "text/xml"}

@app.route("/webhook", methods=["GET"])
def webhook_verify():
    """Some platforms send a GET to verify the webhook is alive"""
    return "NaijaPlate AI Webhook Active ✅", 200

# ─────────────────────────────────────────────────────────────────────────────
# ENTRYPOINT
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"🍲 NaijaPlate AI WhatsApp Bot starting on port {port}...")
    print(f"📡 Webhook URL: http://0.0.0.0:{port}/webhook")
    app.run(host="0.0.0.0", port=port, debug=False)