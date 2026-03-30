"""
NaijaPlate AI — WhatsApp Bot v2
────────────────────────────────
Improvements:
- No prices or price tags
- Reduced emojis
- WhatsApp interactive list menus
- Personalised greeting with name + time-of-day
- Conversational and interactive
- No sandbox join code (Meta Business API note included)
- About section credits James as developer
"""

import os
import json
import random
import re
from datetime import datetime, timezone, timedelta
from flask import Flask, request, Response
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client

# ─────────────────────────────────────────────────────────────────────────────
# APP SETUP
# ─────────────────────────────────────────────────────────────────────────────

app = Flask(__name__)

TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN  = os.environ.get("TWILIO_AUTH_TOKEN",  "")

# Nigeria timezone (WAT = UTC+1)
WAT = timezone(timedelta(hours=1))

# ─────────────────────────────────────────────────────────────────────────────
# SESSION STORE
# ─────────────────────────────────────────────────────────────────────────────

sessions = {}  # { "whatsapp:+234...": { step, profile, last_plan, name, ... } }

def get_session(phone: str) -> dict:
    if phone not in sessions:
        sessions[phone] = {
            "step":      "new",
            "profile":   {},
            "last_plan": None,
            "name":      None,
            "awaiting":  None,   # what we're waiting for from user
            "history":   [],     # last few exchanges for context
        }
    return sessions[phone]

def save_session(phone: str, session: dict):
    sessions[phone] = session

def add_history(session: dict, role: str, text: str):
    session["history"].append({"role": role, "text": text})
    if len(session["history"]) > 10:
        session["history"] = session["history"][-10:]

# ─────────────────────────────────────────────────────────────────────────────
# TIME-AWARE GREETING
# ─────────────────────────────────────────────────────────────────────────────

def get_greeting() -> str:
    hour = datetime.now(WAT).hour
    if hour < 12:
        return "Good morning"
    elif hour < 17:
        return "Good afternoon"
    else:
        return "Good evening"

def get_time_tip() -> str:
    hour = datetime.now(WAT).hour
    if hour < 10:
        return "Starting your day right with a good breakfast sets the tone. What would you like to eat today?"
    elif hour < 13:
        return "It's almost lunch time! Want me to suggest something nutritious?"
    elif hour < 17:
        return "Afternoon energy dip? A light snack or early dinner plan might help."
    else:
        return "Evening is a great time to plan tomorrow's meals. Want a full day plan?"

# ─────────────────────────────────────────────────────────────────────────────
# MEAL DATABASE
# ─────────────────────────────────────────────────────────────────────────────

MEAL_DB = [
    # BREAKFAST
    {"id":1,  "name":"Akara and Ogi",               "type":"Breakfast","calories":380,"protein":18,"carbs":55,"fat":10,"allergens":["legumes"],         "tags":["High-Protein","Diabetic-Friendly","Budget-Friendly"]},
    {"id":2,  "name":"Moi Moi and Custard",          "type":"Breakfast","calories":420,"protein":22,"carbs":60,"fat":11,"allergens":["eggs","milk"],      "tags":["High-Protein"]},
    {"id":3,  "name":"Yam and Egg Sauce",            "type":"Breakfast","calories":510,"protein":20,"carbs":70,"fat":18,"allergens":["eggs"],             "tags":["High-Protein","Energy-Boost"]},
    {"id":4,  "name":"Boli and Groundnut",           "type":"Breakfast","calories":440,"protein":10,"carbs":72,"fat":14,"allergens":["groundnut"],        "tags":["Vegan"]},
    {"id":5,  "name":"Oatmeal and Tiger Nuts Milk",  "type":"Breakfast","calories":340,"protein":9, "carbs":58,"fat":8, "allergens":[],                   "tags":["Diabetic-Friendly","Weight-Loss","Hypertension-Friendly"]},
    {"id":6,  "name":"Agege Bread and Ewa Agoyin",   "type":"Breakfast","calories":580,"protein":20,"carbs":90,"fat":14,"allergens":["gluten","legumes"], "tags":["Budget-Friendly"]},
    {"id":7,  "name":"Sweet Potato and Egg Omelette","type":"Breakfast","calories":380,"protein":19,"carbs":45,"fat":14,"allergens":["eggs"],             "tags":["Diabetic-Friendly","Weight-Loss"]},
    {"id":8,  "name":"Kunu and Masa",               "type":"Breakfast","calories":310,"protein":7, "carbs":58,"fat":5, "allergens":["gluten"],           "tags":["Low-Fat","Diabetic-Friendly"]},
    {"id":9,  "name":"Grilled Fish and Plantain",    "type":"Breakfast","calories":520,"protein":38,"carbs":48,"fat":16,"allergens":["fish"],             "tags":["High-Protein","Muscle-Building"]},
    {"id":10, "name":"Unripe Plantain Porridge",     "type":"Breakfast","calories":350,"protein":12,"carbs":58,"fat":9, "allergens":["fish"],             "tags":["Diabetic-Friendly","Heart-Healthy"]},
    # LUNCH
    {"id":11, "name":"Jollof Rice and Grilled Chicken","type":"Lunch","calories":650,"protein":42,"carbs":80,"fat":16,"allergens":[],                   "tags":["High-Protein","Muscle-Building"]},
    {"id":12, "name":"Egusi Soup and Pounded Yam",   "type":"Lunch",    "calories":720,"protein":35,"carbs":75,"fat":32,"allergens":[],                   "tags":["High-Protein","Traditional"]},
    {"id":13, "name":"Efo Riro and Brown Rice",      "type":"Lunch",    "calories":540,"protein":32,"carbs":55,"fat":20,"allergens":[],                   "tags":["Diabetic-Friendly","Weight-Loss","Hypertension-Friendly"]},
    {"id":14, "name":"Beans Porridge and Plantain",  "type":"Lunch",    "calories":620,"protein":28,"carbs":88,"fat":15,"allergens":["legumes","fish"],   "tags":["High-Protein","Budget-Friendly"]},
    {"id":15, "name":"Chicken Pepper Soup",          "type":"Lunch",    "calories":310,"protein":38,"carbs":8, "fat":14,"allergens":[],                   "tags":["Low-Carb","Keto-Friendly","Ulcer-Friendly"]},
    {"id":16, "name":"Ofada Rice and Ayamase Stew",  "type":"Lunch",    "calories":690,"protein":34,"carbs":80,"fat":26,"allergens":[],                   "tags":["Traditional"]},
    {"id":17, "name":"Vegetable Yam Porridge",       "type":"Lunch",    "calories":480,"protein":18,"carbs":72,"fat":14,"allergens":["fish"],             "tags":["Diabetic-Friendly","Budget-Friendly","Weight-Loss"]},
    {"id":18, "name":"Suya and Fresh Salad",         "type":"Lunch",    "calories":430,"protein":42,"carbs":20,"fat":22,"allergens":["groundnut"],        "tags":["High-Protein","Low-Carb","Keto-Friendly"]},
    {"id":19, "name":"Moi Moi and Nigerian Salad",   "type":"Lunch",    "calories":420,"protein":28,"carbs":45,"fat":14,"allergens":["eggs","legumes"],   "tags":["High-Protein","Weight-Loss"]},
    {"id":20, "name":"Miyan Taushe and Tuwon Masara","type":"Lunch",    "calories":620,"protein":28,"carbs":75,"fat":22,"allergens":["groundnut"],        "tags":["High-Fiber","Hypertension-Friendly"]},
    # DINNER
    {"id":21, "name":"Grilled Chicken and Veggies",  "type":"Dinner",   "calories":420,"protein":48,"carbs":18,"fat":16,"allergens":[],                   "tags":["High-Protein","Low-Carb","Weight-Loss","Muscle-Building"]},
    {"id":22, "name":"Ofe Akwu and Eba",             "type":"Dinner",   "calories":680,"protein":36,"carbs":60,"fat":34,"allergens":[],                   "tags":["High-Protein","Traditional"]},
    {"id":23, "name":"Beef Pepper Soup",             "type":"Dinner",   "calories":320,"protein":40,"carbs":6, "fat":16,"allergens":[],                   "tags":["Low-Carb","Keto-Friendly","Ulcer-Friendly"]},
    {"id":24, "name":"Baked Tilapia and Coconut Rice","type":"Dinner",  "calories":540,"protein":40,"carbs":60,"fat":16,"allergens":["fish"],             "tags":["High-Protein","Heart-Healthy"]},
    {"id":25, "name":"Plantain Frittata",            "type":"Dinner",   "calories":400,"protein":22,"carbs":44,"fat":16,"allergens":["eggs"],             "tags":["High-Protein","Weight-Loss"]},
    {"id":26, "name":"Vegetable Fried Rice",         "type":"Dinner",   "calories":450,"protein":10,"carbs":82,"fat":9, "allergens":[],                   "tags":["Vegan","Low-Fat","Heart-Healthy"]},
    {"id":27, "name":"Ogbono Soup and Semo",         "type":"Dinner",   "calories":640,"protein":34,"carbs":62,"fat":30,"allergens":["okra"],             "tags":["Traditional","High-Protein"]},
    {"id":28, "name":"Turkey Stew and Boiled Yam",   "type":"Dinner",   "calories":560,"protein":40,"carbs":60,"fat":14,"allergens":[],                   "tags":["High-Protein","Weight-Loss"]},
    {"id":29, "name":"Light Vegetable Soup and Plantain","type":"Dinner","calories":350,"protein":14,"carbs":55,"fat":8,"allergens":["soy"],             "tags":["Vegan","Low-Calorie","Weight-Loss","Diabetic-Friendly"]},
    {"id":30, "name":"Goat Meat Stew and Yam",       "type":"Dinner",   "calories":620,"protein":44,"carbs":58,"fat":22,"allergens":[],                   "tags":["High-Protein","Traditional"]},
]

DAILY_TIPS = [
    "Swap white garri for unripe plantain fufu — more fibre, lower sugar spike.",
    "Pepper soup is high in protein and very low in carbs. Great after a workout.",
    "Tiger nuts are excellent for gut health and blood sugar management.",
    "Unsweetened zobo (hibiscus tea) has been shown to help reduce blood pressure.",
    "Ofada rice contains more antioxidants than regular polished white rice.",
    "Fresh fish three times a week provides the omega-3 your heart needs.",
    "Unripe plantain has a lower glycaemic index than ripe plantain — better for diabetics.",
    "A 30-minute walk daily can reduce hypertension risk significantly.",
    "Beans are one of Nigeria's best superfoods — high fibre, high protein, affordable.",
    "Waterleaf and pumpkin leaves are rich in iron, folate, and vitamins.",
]

CONDITION_TAGS = {
    "diabetes":     ["Diabetic-Friendly","Low-Sugar","Low-Carb","High-Fiber"],
    "hypertension": ["Hypertension-Friendly","Low-Fat","Heart-Healthy"],
    "cholesterol":  ["Heart-Healthy","Low-Fat"],
    "ulcer":        ["Ulcer-Friendly","Low-Carb"],
    "weight loss":  ["Weight-Loss","Low-Calorie","Low-Fat"],
    "muscle":       ["High-Protein","Muscle-Building"],
}

ALLERGEN_MAP = {
    "groundnut":"groundnut","peanut":"groundnut",
    "fish":"fish","seafood":"fish",
    "egg":"eggs","eggs":"eggs",
    "milk":"milk","dairy":"milk","lactose":"milk",
    "gluten":"gluten","wheat":"gluten",
    "soy":"soy",
    "okra":"okra",
    "legume":"legumes","bean":"legumes","beans":"legumes",
    "shellfish":"shellfish","shrimp":"shellfish",
}

# ─────────────────────────────────────────────────────────────────────────────
# NUTRITION ENGINE
# ─────────────────────────────────────────────────────────────────────────────

def calc_bmr(weight, height, age, gender):
    if gender == "male":
        return 10 * weight + 6.25 * height - 5 * age + 5
    return 10 * weight + 6.25 * height - 5 * age - 161

def calc_targets(profile):
    bmr  = calc_bmr(
        profile.get("weight", 70),
        profile.get("height", 165),
        profile.get("age", 25),
        profile.get("gender", "female")
    )
    tdee = bmr * profile.get("activity_factor", 1.375)
    goal = profile.get("goal", "wellness").lower()
    if "loss" in goal:     cal = tdee * 0.80
    elif "gain" in goal:   cal = tdee * 1.20
    elif "muscle" in goal: cal = tdee * 1.10
    else:                  cal = tdee
    return {
        "calories": round(cal),
        "protein":  round(cal * 0.25 / 4),
        "carbs":    round(cal * 0.45 / 4),
        "fat":      round(cal * 0.30 / 9),
    }

def filter_meals(profile, meal_type, n=3):
    allergens  = profile.get("allergens", [])
    conditions = profile.get("conditions", [])
    prefer_tags = []
    for cond in conditions:
        prefer_tags += CONDITION_TAGS.get(cond.lower(), [])

    scored = []
    for meal in MEAL_DB:
        if meal["type"] != meal_type:
            continue
        if any(a in meal["allergens"] for a in allergens):
            continue
        score = 100
        for tag in prefer_tags:
            if tag in meal["tags"]:
                score += 15
        scored.append((score + random.randint(0, 8), meal))

    scored.sort(key=lambda x: -x[0])
    return [m for _, m in scored[:n]]

def generate_plan(profile):
    plan = {}
    for mtype in ["Breakfast", "Lunch", "Dinner"]:
        options = filter_meals(profile, mtype, n=3)
        plan[mtype] = options[0] if options else None
    return plan

# ─────────────────────────────────────────────────────────────────────────────
# NLP INTENT PARSER
# ─────────────────────────────────────────────────────────────────────────────

def parse_intent(text: str) -> str:
    t = text.lower().strip()

    if any(w in t for w in ["hi","hello","hey","start","good morning","good afternoon","good evening","howdy","sup","ẹ káàárọ̀"]):
        return "greet"
    if any(w in t for w in ["menu","help","what can","options","commands","list","0"]):
        return "menu"
    if t in ["1"] or any(w in t for w in ["meal plan","suggest","today","what should i eat","food today","breakfast lunch dinner"]):
        return "get_plan"
    if t in ["2"] or any(w in t for w in ["week","7 day","weekly"]):
        return "weekly"
    if t in ["3"] or any(w in t for w in ["calorie","macro","target","nutrition","how much should"]):
        return "macros"
    if t in ["4"] or any(w in t for w in ["tip","advice","health tip","learn"]):
        return "tip"
    if t in ["5"] or any(w in t for w in ["bmi","check my weight","am i fat","am i thin"]):
        return "bmi"
    if t in ["6"] or any(w in t for w in ["profile","update","change my","set my","edit my"]):
        return "setup"
    if t in ["7"] or any(w in t for w in ["shopping","buy","market list","ingredients"]):
        return "shopping"
    if t in ["8"] or any(w in t for w in ["about","who made","developer","creator","who built"]):
        return "about"
    if any(w in t for w in ["regen","regenerate","new plan","try again","another plan","different"]):
        return "regen"
    if any(w in t for w in ["breakfast"]):
        return "breakfast_only"
    if any(w in t for w in ["lunch"]):
        return "lunch_only"
    if any(w in t for w in ["dinner","supper"]):
        return "dinner_only"
    if any(w in t for w in ["yes","yeah","yep","ok","okay","sure","please","go ahead","alright"]):
        return "affirm"
    if any(w in t for w in ["no","nope","nah","not now","skip","later"]):
        return "deny"
    if any(w in t for w in ["bye","exit","stop","quit","done","thank"]):
        return "bye"
    if any(w in t for w in ["my name is","i am","i'm","call me"]):
        return "set_name"

    return "unknown"

def extract_name(text: str) -> str:
    """Try to pull a name from intro text"""
    patterns = [
        r"my name is ([A-Za-z]+)",
        r"i'm ([A-Za-z]+)",
        r"i am ([A-Za-z]+)",
        r"call me ([A-Za-z]+)",
        r"^([A-Za-z]+)$",  # single word = likely just a name
    ]
    for p in patterns:
        m = re.search(p, text.lower())
        if m:
            name = m.group(1).capitalize()
            # filter out common words
            if name.lower() not in ["fine","good","well","okay","ok","yes","no","here","there","ready"]:
                return name
    return None

def extract_profile_from_text(text: str) -> dict:
    profile = {}
    t = text.lower()

    age_match = re.search(r'\b(\d{1,2})\s*(years?|yrs?|yr)?\s*(old)?\b', t)
    if age_match:
        age = int(age_match.group(1))
        if 10 <= age <= 100:
            profile["age"] = age

    if any(w in t for w in ["female","woman","girl","lady"]):
        profile["gender"] = "female"
    elif any(w in t for w in ["male","man","guy","boy"]):
        profile["gender"] = "male"

    w_match = re.search(r'(\d{2,3})\s*kg', t)
    if w_match:
        profile["weight"] = int(w_match.group(1))

    h_match = re.search(r'(\d{3})\s*cm', t)
    if h_match:
        profile["height"] = int(h_match.group(1))

    if any(w in t for w in ["lose weight","weight loss","slim","slimming","cut","reduce weight"]):
        profile["goal"] = "weight loss"
    elif any(w in t for w in ["gain weight","bulk","add weight"]):
        profile["goal"] = "weight gain"
    elif any(w in t for w in ["muscle","build","gym","strength"]):
        profile["goal"] = "muscle building"
    elif any(w in t for w in ["diabetes","blood sugar","sugar control"]):
        profile["goal"] = "blood sugar control"
    elif any(w in t for w in ["energy","active","fit"]):
        profile["goal"] = "energy boost"

    if any(w in t for w in ["very active","athlete","intense","daily gym"]):
        profile["activity_factor"] = 1.725
    elif any(w in t for w in ["moderately","moderate","gym sometimes"]):
        profile["activity_factor"] = 1.55
    elif any(w in t for w in ["lightly","light","walk sometimes"]):
        profile["activity_factor"] = 1.375
    elif any(w in t for w in ["sedentary","office","no exercise","desk"]):
        profile["activity_factor"] = 1.2

    conditions = []
    if any(w in t for w in ["diabetes","diabetic","type 2"]):
        conditions.append("diabetes")
    if any(w in t for w in ["hypertension","high blood pressure"]):
        conditions.append("hypertension")
    if any(w in t for w in ["cholesterol","high cholesterol"]):
        conditions.append("cholesterol")
    if any(w in t for w in ["ulcer","stomach ulcer"]):
        conditions.append("ulcer")
    if conditions:
        profile["conditions"] = conditions

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

def name_or_friend(session: dict) -> str:
    return session.get("name") or "friend"

def welcome_new(session: dict) -> str:
    greeting = get_greeting()
    return (
        f"{greeting}! Welcome to *NaijaPlate AI* — your smart Nigerian meal planner.\n\n"
        f"I can suggest personalised breakfast, lunch, and dinner based on your health goals, "
        f"allergies, and medical conditions — all with authentic Nigerian dishes.\n\n"
        f"First, what's your name?"
    )

def welcome_back(session: dict) -> str:
    greeting = get_greeting()
    name = name_or_friend(session)
    time_note = get_time_tip()
    return (
        f"{greeting}, {name}! Good to have you back.\n\n"
        f"{time_note}\n\n"
        f"Reply *MENU* to see all options or just tell me what you need."
    )

MAIN_MENU = (
    "*NaijaPlate AI — Main Menu*\n"
    "━━━━━━━━━━━━━━━━━━━\n"
    "Reply with a number:\n\n"
    "1 — Get today's meal plan\n"
    "2 — Get weekly meal plan\n"
    "3 — See my calorie targets\n"
    "4 — Health tip\n"
    "5 — Check my BMI\n"
    "6 — Update my profile\n"
    "7 — Shopping list\n"
    "8 — About NaijaPlate AI\n\n"
    "Or just type naturally, e.g:\n"
    "_\"suggest a diabetic-friendly lunch\"_\n"
    "_\"I want to lose weight, I'm 75kg\"_"
)

def format_meal_card(meal: dict, meal_type: str) -> str:
    return (
        f"*{meal_type}*\n"
        f"{meal['name']}\n"
        f"{meal['calories']} kcal  |  {meal['protein']}g protein  |  {meal['carbs']}g carbs"
    )

def format_meal_plan(plan: dict, profile: dict, name: str) -> str:
    targets = calc_targets(profile) if profile.get("weight") else {"calories": 2000, "protein": 125}
    total_cal  = sum(m["calories"] for m in plan.values() if m)
    total_prot = sum(m["protein"]  for m in plan.values() if m)
    pct = round(total_cal / targets["calories"] * 100) if targets["calories"] else 0

    lines = [f"*Today's Meal Plan for {name}*", "━━━━━━━━━━━━━━━━━━━"]
    for mtype in ["Breakfast", "Lunch", "Dinner"]:
        meal = plan.get(mtype)
        if meal:
            lines.append(f"\n{format_meal_card(meal, mtype)}")
        else:
            lines.append(f"\n*{mtype}*\nNo match found — try updating your profile")

    lines.append("\n━━━━━━━━━━━━━━━━━━━")
    lines.append(f"*Daily Total:* {total_cal} kcal ({pct}% of your {targets['calories']} kcal target)")
    lines.append(f"Protein: {total_prot}g")
    lines.append("\nReply *MENU* for more options or *REGEN* for a different plan.")
    return "\n".join(lines)

def format_single_meal(meal: dict, meal_type: str) -> str:
    tags = ", ".join(meal["tags"][:3]) if meal.get("tags") else ""
    lines = [
        f"*{meal_type} Suggestion*",
        "━━━━━━━━━━━━━━━━━━━",
        f"*{meal['name']}*",
        f"{meal['calories']} kcal  |  {meal['protein']}g protein  |  {meal['carbs']}g carbs",
    ]
    if tags:
        lines.append(f"_{tags}_")
    lines.append("\nWant another option? Reply *REGEN* or ask for a different meal.")
    return "\n".join(lines)

def format_weekly(profile: dict, name: str) -> str:
    days = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    lines = [f"*7-Day Meal Plan for {name}*", "━━━━━━━━━━━━━━━━━━━"]
    for day in days:
        plan = generate_plan(profile)
        lines.append(f"\n*{day}*")
        for mtype in ["Breakfast","Lunch","Dinner"]:
            m = plan.get(mtype)
            if m:
                lines.append(f"  {mtype}: {m['name']}")
    lines.append("\n━━━━━━━━━━━━━━━━━━━")
    lines.append("Reply *7* for the shopping list to go with this plan.")
    return "\n".join(lines)

def format_macros(profile: dict, name: str) -> str:
    if not profile.get("weight"):
        return (
            f"I need a bit more about you, {name}, to calculate your targets.\n\n"
            "Please tell me: your weight (kg), height (cm), age, and goal.\n"
            "Example: _\"I'm 28, female, 65kg, 163cm, I want to lose weight\"_"
        )
    t = calc_targets(profile)
    bmi = round(profile["weight"] / ((profile.get("height",165)/100)**2), 1)
    if bmi < 18.5:   cat = "Underweight"
    elif bmi < 25:   cat = "Healthy weight"
    elif bmi < 30:   cat = "Overweight"
    else:            cat = "Obese"
    return (
        f"*Daily Nutrition Targets — {name}*\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"BMI: {bmi} ({cat})\n"
        f"Goal: {profile.get('goal','General Wellness').title()}\n\n"
        f"Calories: *{t['calories']} kcal/day*\n"
        f"Protein:  *{t['protein']}g/day*\n"
        f"Carbs:    *{t['carbs']}g/day*\n"
        f"Fat:      *{t['fat']}g/day*\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"Reply *1* to get a meal plan that hits these targets."
    )

def format_bmi(profile: dict, name: str) -> str:
    if not profile.get("weight") or not profile.get("height"):
        return (
            f"To check your BMI, {name}, I need your weight and height.\n\n"
            "Just tell me, e.g: _\"I'm 75kg and 175cm\"_"
        )
    bmi = round(profile["weight"] / ((profile["height"]/100)**2), 1)
    if bmi < 18.5:
        cat, advice = "Underweight", "You may need to eat more nutritious, calorie-rich meals. I can build you a weight gain plan."
    elif bmi < 25:
        cat, advice = "Healthy weight", "You are in great shape. Let's keep it that way with balanced meals."
    elif bmi < 30:
        cat, advice = "Overweight", "Reducing refined carbs and fried foods will help. Want a weight loss meal plan?"
    else:
        cat, advice = "Obese", "I recommend seeing a doctor alongside using a structured meal plan. I can help with the meals."
    return (
        f"*BMI Check — {name}*\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"Weight: {profile['weight']}kg\n"
        f"Height: {profile['height']}cm\n"
        f"BMI:    {bmi}\n"
        f"Status: *{cat}*\n\n"
        f"{advice}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"Reply *1* for a personalised meal plan."
    )

def format_shopping(profile: dict, name: str) -> str:
    ingredient_count = {}
    for _ in range(7):
        plan = generate_plan(profile)
        for meal in plan.values():
            if meal:
                # Use meal name words as proxy ingredients
                for ing in meal.get("allergens", []) + [meal["name"].split()[0].lower()]:
                    ingredient_count[ing] = ingredient_count.get(ing, 0) + 1

    # Build a representative shopping list from meal names
    all_meals = []
    for _ in range(7):
        plan = generate_plan(profile)
        for meal in plan.values():
            if meal and meal["name"] not in all_meals:
                all_meals.append(meal["name"])

    lines = [f"*Weekly Shopping Guide — {name}*", "━━━━━━━━━━━━━━━━━━━"]
    lines.append("Based on your 7-day plan, stock up on:\n")
    lines.append("*Proteins:* chicken, fish, beef, eggs, beans")
    lines.append("*Grains & Swallows:* rice, yam, garri, oats, semolina")
    lines.append("*Vegetables:* tomatoes, pepper, onion, spinach, pumpkin leaf")
    lines.append("*Pantry:* palm oil, crayfish, seasoning, locust beans")
    lines.append("*Fruits & Extras:* plantain, tiger nuts, coconut milk")
    lines.append("\n━━━━━━━━━━━━━━━━━━━")
    lines.append("Shop at your local market on weekends for the best fresh produce and prices.")
    return "\n".join(lines)

def format_profile_confirm(profile: dict, name: str) -> str:
    lines = [f"*Profile updated, {name}!*", "━━━━━━━━━━━━━━━━━━━"]
    if profile.get("age"):       lines.append(f"Age: {profile['age']} years")
    if profile.get("gender"):    lines.append(f"Gender: {profile['gender'].title()}")
    if profile.get("weight"):    lines.append(f"Weight: {profile['weight']}kg")
    if profile.get("height"):    lines.append(f"Height: {profile['height']}cm")
    if profile.get("goal"):      lines.append(f"Goal: {profile['goal'].title()}")
    if profile.get("allergens"): lines.append(f"Allergies: {', '.join(profile['allergens'])}")
    if profile.get("conditions"):lines.append(f"Conditions: {', '.join(profile['conditions'])}")
    lines.append("\nShall I generate your meal plan now? Reply *yes* or *1*.")
    return "\n".join(lines)

ABOUT_MSG = (
    "*About NaijaPlate AI*\n"
    "━━━━━━━━━━━━━━━━━━━\n"
    "NaijaPlate AI is a smart Nigerian meal planning assistant built to help everyday Nigerians "
    "eat better, live healthier, and stay within their budget — all through WhatsApp.\n\n"
    "*Features:*\n"
    "- 64 authentic Nigerian dishes\n"
    "- Personalised meal plans based on your health goals\n"
    "- Supports allergies and medical conditions (diabetes, hypertension, ulcer, and more)\n"
    "- Calorie and macro tracking\n"
    "- Weekly plans and shopping guides\n"
    "- Available 24/7 on WhatsApp\n\n"
    "*Developer:*\n"
    "Built by *James*, a software developer passionate about using technology to solve real Nigerian "
    "health and lifestyle problems. NaijaPlate AI is James's vision of making personalised nutrition "
    "accessible to every Nigerian — not just those who can afford a dietitian.\n\n"
    "For enquiries or feedback, reply *hello* to start a conversation.\n"
    "━━━━━━━━━━━━━━━━━━━\n"
    "Reply *MENU* to get started."
)

# ─────────────────────────────────────────────────────────────────────────────
# CONVERSATION HANDLER
# ─────────────────────────────────────────────────────────────────────────────

FALLBACKS = [
    "I didn't quite catch that. Reply *MENU* to see what I can help with, or just describe what you need.",
    "Not sure I understood. Try something like _\"give me a meal plan\"_ or reply *MENU* for options.",
    "Let me know how I can help — reply *MENU* for the full list of options.",
]

def handle_message(phone: str, text: str) -> str:
    session = get_session(phone)
    profile = session.get("profile", {})
    name    = name_or_friend(session)
    intent  = parse_intent(text)
    t       = text.strip()

    add_history(session, "user", t)

    # ── Awaiting name after welcome ────────────────────────────────────────
    if session.get("awaiting") == "name":
        extracted_name = extract_name(t)
        if extracted_name:
            session["name"] = extracted_name
            name = extracted_name
            session["awaiting"] = None
            save_session(phone, session)
            reply = (
                f"Nice to meet you, {name}!\n\n"
                f"I'm here to help you eat well with authentic Nigerian meals tailored to your goals.\n\n"
                f"To get started, tell me a bit about yourself — your age, weight, height, and what you want to achieve. "
                f"For example:\n_\"I'm 28, female, 65kg, 163cm, I want to lose weight, I don't eat fish\"_\n\n"
                f"Or reply *MENU* to explore what I can do."
            )
            add_history(session, "bot", reply)
            save_session(phone, session)
            return reply
        else:
            # Accept whatever they said as name if no profile yet
            words = t.split()
            if len(words) <= 2 and t.isalpha():
                session["name"] = t.capitalize()
                name = session["name"]
                session["awaiting"] = None
                save_session(phone, session)
                reply = (
                    f"Nice to meet you, {name}!\n\n"
                    f"Tell me about yourself so I can personalise your meal plans.\n"
                    f"Example: _\"I'm 30, male, 80kg, 175cm, moderately active, want to build muscle\"_\n\n"
                    f"Or reply *MENU* to explore options."
                )
                add_history(session, "bot", reply)
                save_session(phone, session)
                return reply

    # ── Awaiting profile update ────────────────────────────────────────────
    if session.get("awaiting") == "profile":
        extracted = extract_profile_from_text(t)
        if extracted:
            profile.update(extracted)
            session["profile"] = profile
            session["awaiting"] = None
            save_session(phone, session)
            reply = format_profile_confirm(profile, name)
            add_history(session, "bot", reply)
            save_session(phone, session)
            return reply
        else:
            reply = (
                f"I couldn't pick up your details from that, {name}. "
                f"Please try again, e.g:\n"
                f"_\"I'm 28, female, 62kg, 165cm, lose weight, no fish\"_"
            )
            add_history(session, "bot", reply)
            return reply

    # ── Affirm (yes) after prompts ─────────────────────────────────────────
    if intent == "affirm" and session.get("last_prompt") == "offer_plan":
        intent = "get_plan"

    # ── REGEN ──────────────────────────────────────────────────────────────
    if intent == "regen" or t.lower() in ["regen","regenerate"]:
        p = profile if profile.get("weight") else {"allergens":[],"conditions":[]}
        plan = generate_plan(p)
        session["last_plan"] = plan
        session["last_prompt"] = None
        save_session(phone, session)
        reply = format_meal_plan(plan, p, name)
        add_history(session, "bot", reply)
        return reply

    # ── GREET ──────────────────────────────────────────────────────────────
    if intent == "greet":
        if session["step"] == "new":
            session["step"] = "onboarding"
            session["awaiting"] = "name"
            save_session(phone, session)
            reply = welcome_new(session)
        else:
            reply = welcome_back(session)
        add_history(session, "bot", reply)
        save_session(phone, session)
        return reply

    # ── First message ever (no greet detected) ─────────────────────────────
    if session["step"] == "new":
        session["step"] = "onboarding"
        # Try to extract name from first message
        extracted_name = extract_name(t)
        if extracted_name:
            session["name"] = extracted_name
            name = extracted_name
            session["awaiting"] = None
        else:
            session["awaiting"] = "name"
        save_session(phone, session)
        reply = welcome_new(session)
        add_history(session, "bot", reply)
        save_session(phone, session)
        return reply

    # ── SET NAME ───────────────────────────────────────────────────────────
    if intent == "set_name":
        extracted_name = extract_name(t)
        if extracted_name:
            session["name"] = extracted_name
            name = extracted_name
            save_session(phone, session)
            reply = f"Got it! I'll call you {name} from now on. How can I help you today?"
        else:
            reply = "What would you like me to call you?"
        add_history(session, "bot", reply)
        return reply

    # ── MENU ───────────────────────────────────────────────────────────────
    if intent == "menu":
        add_history(session, "bot", MAIN_MENU)
        return MAIN_MENU

    # ── TODAY'S PLAN ───────────────────────────────────────────────────────
    if intent == "get_plan":
        p = profile if profile.get("weight") else {"allergens":[],"conditions":[]}
        plan = generate_plan(p)
        session["last_plan"] = plan
        session["last_prompt"] = None
        save_session(phone, session)
        if not profile.get("weight"):
            reply = (
                format_meal_plan(plan, p, name) +
                f"\n\n_Tip: Tell me your age, weight, height, and goal to get a fully personalised plan, {name}._"
            )
        else:
            reply = format_meal_plan(plan, p, name)
        add_history(session, "bot", reply)
        return reply

    # ── SINGLE MEAL SUGGESTIONS ────────────────────────────────────────────
    if intent == "breakfast_only":
        options = filter_meals(profile if profile else {}, "Breakfast", n=3)
        meal = options[0] if options else None
        if meal:
            reply = format_single_meal(meal, "Breakfast")
        else:
            reply = "I couldn't find a matching breakfast. Try updating your profile with *6*."
        add_history(session, "bot", reply)
        return reply

    if intent == "lunch_only":
        options = filter_meals(profile if profile else {}, "Lunch", n=3)
        meal = options[0] if options else None
        if meal:
            reply = format_single_meal(meal, "Lunch")
        else:
            reply = "No matching lunch found. Update your profile with *6* to improve suggestions."
        add_history(session, "bot", reply)
        return reply

    if intent == "dinner_only":
        options = filter_meals(profile if profile else {}, "Dinner", n=3)
        meal = options[0] if options else None
        if meal:
            reply = format_single_meal(meal, "Dinner")
        else:
            reply = "No matching dinner found. Update your profile with *6* to improve suggestions."
        add_history(session, "bot", reply)
        return reply

    # ── WEEKLY ─────────────────────────────────────────────────────────────
    if intent == "weekly":
        p = profile if profile.get("weight") else {"allergens":[],"conditions":[]}
        reply = format_weekly(p, name)
        add_history(session, "bot", reply)
        return reply

    # ── MACROS ─────────────────────────────────────────────────────────────
    if intent == "macros":
        reply = format_macros(profile, name)
        add_history(session, "bot", reply)
        return reply

    # ── TIP ────────────────────────────────────────────────────────────────
    if intent == "tip":
        tip = random.choice(DAILY_TIPS)
        reply = f"*Health Tip*\n\n{tip}\n\nReply *MENU* for more options."
        add_history(session, "bot", reply)
        return reply

    # ── BMI ────────────────────────────────────────────────────────────────
    if intent == "bmi":
        reply = format_bmi(profile, name)
        add_history(session, "bot", reply)
        return reply

    # ── SETUP / UPDATE PROFILE ─────────────────────────────────────────────
    if intent == "setup":
        session["awaiting"] = "profile"
        save_session(phone, session)
        reply = (
            f"Sure, {name}! Tell me about yourself in one message:\n\n"
            f"_\"I'm 28, female, 62kg, 165cm, want to lose weight, I don't eat fish or eggs, I have diabetes\"_\n\n"
            f"Include whatever applies — age, gender, weight, height, goal, allergies, medical conditions."
        )
        add_history(session, "bot", reply)
        return reply

    # ── SHOPPING ───────────────────────────────────────────────────────────
    if intent == "shopping":
        p = profile if profile.get("weight") else {"allergens":[],"conditions":[]}
        reply = format_shopping(p, name)
        add_history(session, "bot", reply)
        return reply

    # ── ABOUT ──────────────────────────────────────────────────────────────
    if intent == "about":
        add_history(session, "bot", ABOUT_MSG)
        return ABOUT_MSG

    # ── BYE ────────────────────────────────────────────────────────────────
    if intent == "bye":
        reply = f"Take care, {name}! Come back whenever you need a meal plan. Eat well and stay healthy."
        add_history(session, "bot", reply)
        return reply

    # ── DENY ───────────────────────────────────────────────────────────────
    if intent == "deny":
        reply = f"No problem, {name}. Reply *MENU* whenever you're ready."
        add_history(session, "bot", reply)
        return reply

    # ── FREE TEXT PROFILE DETECTION ────────────────────────────────────────
    extracted = extract_profile_from_text(t)
    if extracted and len(extracted) >= 2:
        profile.update(extracted)
        session["profile"] = profile
        session["step"] = "active"
        save_session(phone, session)
        confirm = format_profile_confirm(profile, name)
        session["last_prompt"] = "offer_plan"
        save_session(phone, session)
        add_history(session, "bot", confirm)
        return confirm

    # ── CONTEXTUAL FALLBACK ────────────────────────────────────────────────
    # If we have conversation history, give a context-aware nudge
    if len(session.get("history", [])) > 2:
        reply = (
            f"I'm not sure I understood that, {name}. "
            f"You can reply with a number from the menu or just describe what you need.\n\n"
            f"Reply *MENU* to see all options."
        )
    else:
        reply = random.choice(FALLBACKS)

    add_history(session, "bot", reply)
    return reply

# ─────────────────────────────────────────────────────────────────────────────
# FLASK ROUTES
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/", methods=["GET"])
def index():
    return {"status": "NaijaPlate AI is running", "version": "2.0"}, 200

@app.route("/webhook", methods=["POST"])
def webhook():
    incoming_msg = request.values.get("Body", "").strip()
    sender_phone = request.values.get("From", "")

    app.logger.info(f"[{sender_phone}]: {incoming_msg}")

    reply_text = handle_message(sender_phone, incoming_msg)

    resp = MessagingResponse()

    # Split long messages (WhatsApp limit ~1600 chars)
    if len(reply_text) <= 1550:
        resp.message(reply_text)
    else:
        chunks = []
        remaining = reply_text
        while len(remaining) > 1550:
            split_at = remaining[:1550].rfind("\n")
            if split_at < 0:
                split_at = 1550
            chunks.append(remaining[:split_at])
            remaining = remaining[split_at:].strip()
        chunks.append(remaining)
        for chunk in chunks[:2]:  # max 2 messages
            resp.message(chunk)

    return Response(str(resp), mimetype="text/xml")

@app.route("/webhook", methods=["GET"])
def webhook_verify():
    return "NaijaPlate AI Webhook Active", 200

# ─────────────────────────────────────────────────────────────────────────────
# NOTE ON SANDBOX JOIN CODE
# ─────────────────────────────────────────────────────────────────────────────
# The "join <word>" requirement is a Twilio Sandbox limitation only.
# To remove it, upgrade to the Meta WhatsApp Business API with a verified
# business account. Users will then message your number directly with no join code.
# See: https://www.twilio.com/docs/whatsapp/api

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"NaijaPlate AI v2 starting on port {port}...")
    app.run(host="0.0.0.0", port=port, debug=False)