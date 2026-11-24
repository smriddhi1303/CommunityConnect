
import os
import json
import sqlite3
from datetime import datetime
from typing import TypedDict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from langgraph.graph import StateGraph, END


# ==========================================
# APPLICATION
# ==========================================

app = FastAPI(title="CommunityConnect API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==========================================
# DATABASE
# ==========================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "complaints.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_database():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            description TEXT NOT NULL,
            location TEXT NOT NULL,
            category TEXT,
            department TEXT,
            priority TEXT,
            estimated_time TEXT,
            status TEXT DEFAULT 'Pending',
            agent_activity TEXT,
            created_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_profile (
            id INTEGER PRIMARY KEY,
            name TEXT DEFAULT '',
            full_name TEXT DEFAULT '',
            email TEXT DEFAULT '',
            phone TEXT DEFAULT '',
            address TEXT DEFAULT '',
            city TEXT DEFAULT '',
            state TEXT DEFAULT '',
            pincode TEXT DEFAULT '',
            created_at TEXT
        )
    """)

    # Safely add columns to an older profile database
    existing_columns = {
        row["name"]
        for row in cursor.execute(
            "PRAGMA table_info(user_profile)"
        ).fetchall()
    }

    required_columns = {
        "name": "TEXT DEFAULT ''",
        "full_name": "TEXT DEFAULT ''",
        "email": "TEXT DEFAULT ''",
        "phone": "TEXT DEFAULT ''",
        "address": "TEXT DEFAULT ''",
        "city": "TEXT DEFAULT ''",
        "state": "TEXT DEFAULT ''",
        "pincode": "TEXT DEFAULT ''",
        "created_at": "TEXT"
    }

    for column, definition in required_columns.items():
        if column not in existing_columns:
            cursor.execute(
                f"ALTER TABLE user_profile ADD COLUMN {column} {definition}"
            )

    cursor.execute("""
        INSERT OR IGNORE INTO user_profile
        (id, name, full_name, created_at)
        VALUES (1, '', '', ?)
    """, (datetime.now().isoformat(),))

    cursor.execute("""
        UPDATE user_profile
        SET full_name = name
        WHERE (full_name IS NULL OR full_name = '')
        AND name IS NOT NULL
        AND name != ''
    """)

    cursor.execute("""
        UPDATE user_profile
        SET name = full_name
        WHERE (name IS NULL OR name = '')
        AND full_name IS NOT NULL
        AND full_name != ''
    """)

    conn.commit()
    conn.close()


initialize_database()


# ==========================================
# REQUEST MODELS
# ==========================================

class ComplaintRequest(BaseModel):
    description: str
    location: str


class ProfileRequest(BaseModel):
    full_name: str = ""
    email: str = ""
    phone: str = ""
    address: str = ""
    city: str = ""
    state: str = ""
    pincode: str = ""


class StatusRequest(BaseModel):
    status: str


# ==========================================
# LANGGRAPH AGENT STATE
# ==========================================

class ComplaintState(TypedDict, total=False):
    description: str
    location: str
    category: str
    department: str
    priority: str
    estimated_time: str
    agent_activity: list


# ==========================================
# AGENT 1: INTAKE AGENT
# ==========================================

def intake_agent(state: ComplaintState):

    activity = state.get("agent_activity", [])

    activity.append(
        "Intake Agent: Complaint received and details analyzed."
    )

    return {
        "agent_activity": activity
    }


# ==========================================
# AGENT 2: CLASSIFICATION AGENT
# ==========================================

def classification_agent(state: ComplaintState):

    description = state["description"].lower()

    category = "General Complaint"
    department = "Local Administration"

    if any(word in description for word in [
        "garbage", "waste", "dustbin", "dirty", "sanitation"
    ]):
        category = "Sanitation"
        department = "Sanitation Department"

    elif any(word in description for word in [
        "water", "leakage", "pipeline", "sewage", "drain"
    ]):
        category = "Water Supply"
        department = "Water Department"

    elif any(word in description for word in [
        "electricity", "light", "lights", "streetlight",
        "street light", "power", "wire", "electric"
    ]):
        category = "Electricity"
        department = "Electricity Department"

    elif any(word in description for word in [
        "road", "pothole", "street"
    ]):
        category = "Road Maintenance"
        department = "Public Works Department"

    activity = state.get("agent_activity", [])

    activity.append(
        f"Classification Agent: Complaint classified as {category}."
    )

    return {
        "category": category,
        "department": department,
        "agent_activity": activity
    }


# ==========================================
# AGENT 3: PRIORITY AGENT
# ==========================================

def priority_agent(state: ComplaintState):

    description = state["description"].lower()

    low_words = [
        "minor",
        "small issue",
        "slightly damaged",
        "cosmetic",
        "not urgent",
        "non-urgent"
    ]

    negated_urgent = [
        "not urgent",
        "no emergency",
        "not an emergency",
        "not dangerous",
        "no danger"
    ]

    urgent_words = [
        "emergency",
        "urgent",
        "danger",
        "accident",
        "fire",
        "injury",
        "overflow",
        "exposed wire",
        "electric shock",
        "major leakage",
        "flooding",
        "collapse",
        "severe",
        "no light",
        "no electricity",
        "power outage",
        "electricity outage",
        "power cut",
        "power failure",
        "no power"
    ]

    if any(word in description for word in low_words):
        priority = "Low"
        estimated_time = "5–7 days"

    elif any(word in description for word in negated_urgent):
        priority = "Low"
        estimated_time = "5–7 days"

    elif any(word in description for word in urgent_words):
        priority = "High"
        estimated_time = "Within 24 hours"

    else:
        priority = "Medium"
        estimated_time = "2–3 days"

    activity = state.get("agent_activity", [])

    activity.append(
        f"Priority Agent: Complaint assigned {priority} priority."
    )

    return {
        "priority": priority,
        "estimated_time": estimated_time,
        "agent_activity": activity
    }


# ==========================================
# AGENT 4: ROUTING AGENT
# ==========================================

def routing_agent(state: ComplaintState):

    activity = state.get("agent_activity", [])

    activity.append(
        f"Routing Agent: Complaint forwarded to {state['department']}."
    )

    return {
        "agent_activity": activity
    }


# ==========================================
# LANGGRAPH WORKFLOW
# ==========================================

workflow = StateGraph(ComplaintState)

workflow.add_node("intake", intake_agent)
workflow.add_node("classification", classification_agent)
workflow.add_node("priority", priority_agent)
workflow.add_node("routing", routing_agent)

workflow.set_entry_point("intake")

workflow.add_edge("intake", "classification")
workflow.add_edge("classification", "priority")
workflow.add_edge("priority", "routing")
workflow.add_edge("routing", END)

agent_graph = workflow.compile()


# ==========================================
# HOME API
# ==========================================

@app.get("/")
def home():

    return {
        "message": "CommunityConnect API is running!",
        "status": "Active"
    }


# ==========================================
# PROFILE APIs
# ==========================================

@app.get("/api/profile")
def get_profile():

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM user_profile WHERE id = 1"
    )

    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(
            status_code=404,
            detail="Profile not found"
        )

    profile = dict(row)

    if not profile.get("full_name"):
        profile["full_name"] = profile.get("name", "")

    return {"profile": profile}


@app.put("/api/profile")
def update_profile(profile: ProfileRequest):

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE user_profile
        SET name = ?,
            full_name = ?,
            email = ?,
            phone = ?,
            address = ?,
            city = ?,
            state = ?,
            pincode = ?
        WHERE id = 1
    """, (
        profile.full_name,
        profile.full_name,
        profile.email,
        profile.phone,
        profile.address,
        profile.city,
        profile.state,
        profile.pincode
    ))

    conn.commit()

    cursor.execute(
        "SELECT * FROM user_profile WHERE id = 1"
    )

    updated_profile = dict(cursor.fetchone())

    conn.close()

    return {
        "message": "Profile updated successfully",
        "profile": updated_profile
    }


# ==========================================
# SUBMIT COMPLAINT API
# ==========================================

@app.post("/api/complaints")
def submit_complaint(complaint: ComplaintRequest):

    description = complaint.description.strip()
    location = complaint.location.strip()

    if not description or not location:
        raise HTTPException(
            status_code=400,
            detail="Description and location are required."
        )

    initial_state = {
        "description": description,
        "location": location,
        "agent_activity": []
    }

    result = agent_graph.invoke(initial_state)

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO complaints (
            description,
            location,
            category,
            department,
            priority,
            estimated_time,
            status,
            agent_activity,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        description,
        location,
        result["category"],
        result["department"],
        result["priority"],
        result["estimated_time"],
        "Pending",
        json.dumps(result["agent_activity"]),
        datetime.now().isoformat()
    ))

    complaint_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return {
        "message": "Complaint submitted successfully",
        "complaint_id": complaint_id,
        "category": result["category"],
        "department": result["department"],
        "priority": result["priority"],
        "estimated_time": result["estimated_time"],
        "status": "Pending",
        "agent_activity": result["agent_activity"]
    }


# ==========================================
# GET COMPLAINT HISTORY API
# ==========================================

@app.get("/api/complaints")
def get_complaints():

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM complaints
        ORDER BY id DESC
    """)

    rows = cursor.fetchall()
    conn.close()

    complaints = []

    for row in rows:

        item = dict(row)

        try:
            item["agent_activity"] = json.loads(
                item["agent_activity"] or "[]"
            )
        except (json.JSONDecodeError, TypeError):
            item["agent_activity"] = []

        complaints.append(item)

    return complaints


# ==========================================
# UPDATE COMPLAINT STATUS API
# ==========================================

@app.put("/api/complaints/{complaint_id}/status")
def update_complaint_status(
    complaint_id: int,
    status_data: StatusRequest
):

    allowed_statuses = ["Pending", "Completed", "Resolved"]

    if status_data.status not in allowed_statuses:
        raise HTTPException(
            status_code=400,
            detail="Invalid complaint status."
        )

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE complaints
        SET status = ?
        WHERE id = ?
    """, (
        status_data.status,
        complaint_id
    ))

    if cursor.rowcount == 0:
        conn.close()

        raise HTTPException(
            status_code=404,
            detail="Complaint not found."
        )

    conn.commit()
    conn.close()

    return {
        "message": "Complaint status updated successfully",
        "complaint_id": complaint_id,
        "status": status_data.status
    }


# ==========================================
# DELETE ALL COMPLAINTS API
# ==========================================

@app.delete("/api/complaints")
def delete_all_complaints():

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM complaints")

    conn.commit()
    conn.close()

    return {
        "message": "All complaint history deleted successfully"
    }
