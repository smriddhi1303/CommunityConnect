
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import TypedDict, List
from langgraph.graph import StateGraph, START, END
import sqlite3
import json
import os
from datetime import datetime


# =========================
# DATABASE SETUP
# =========================

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "complaints.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def setup_database():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            description TEXT NOT NULL,
            location TEXT,
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
            name TEXT,
            email TEXT,
            phone TEXT,
            address TEXT
        )
    """)

    cursor.execute("""
        INSERT OR IGNORE INTO user_profile
        (id, name, email, phone, address)
        VALUES (1, '', '', '', '')
    """)

    conn.commit()
    conn.close()


setup_database()


# =========================
# FASTAPI APPLICATION
# =========================

app = FastAPI(title="CommunityConnect API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def home():
    return {
        "message": "CommunityConnect Backend is running!"
    }


# =========================
# PROFILE APIs
# =========================

@app.get("/api/profile")
def get_profile():
    conn = get_connection()
    profile = conn.execute(
        "SELECT * FROM user_profile WHERE id = 1"
    ).fetchone()
    conn.close()

    return dict(profile)


@app.put("/api/profile")
def update_profile(data: dict):
    allowed_fields = ["name", "email", "phone", "address"]

    conn = get_connection()
    cursor = conn.cursor()

    for field in allowed_fields:
        if field in data:
            cursor.execute(
                f"UPDATE user_profile SET {field} = ? WHERE id = 1",
                (str(data[field]),)
            )

    conn.commit()

    profile = cursor.execute(
        "SELECT * FROM user_profile WHERE id = 1"
    ).fetchone()

    conn.close()
    return dict(profile)


# =========================
# COMPLAINT MODEL
# =========================

class ComplaintRequest(BaseModel):
    description: str
    location: str = ""


# =========================
# LANGGRAPH AGENT STATE
# =========================

class ComplaintState(TypedDict):
    description: str
    location: str
    category: str
    department: str
    priority: str
    estimated_time: str
    activity: List[str]


# =========================
# AGENT 1: INTAKE AGENT
# =========================

def intake_agent(state: ComplaintState):
    activity = state["activity"] + [
        "Intake Agent: Complaint received and recorded."
    ]

    return {"activity": activity}


# =========================
# AGENT 2: CLASSIFICATION AGENT
# =========================

def classification_agent(state: ComplaintState):
    text = state["description"].lower()

    if any(word in text for word in [
        "garbage", "waste", "dustbin", "dirty", "sanitation"
    ]):
        category = "Sanitation"
        department = "Sanitation Department"

    elif any(word in text for word in [
        "water", "leakage", "pipeline", "sewage", "drain"
    ]):
        category = "Water Supply"
        department = "Water Department"

    elif any(word in text for word in [
        "electricity", "light", "lights", "streetlight",
        "street light", "power", "wire", "electric"
    ]):
        category = "Electricity"
        department = "Electricity Department"

    elif any(word in text for word in [
        "road", "pothole", "street"
    ]):
        category = "Road Maintenance"
        department = "Public Works Department"

    else:
        category = "General Complaint"
        department = "Local Administration"

    activity = state["activity"] + [
        f"Classification Agent: Complaint classified as {category}."
    ]

    return {
        "category": category,
        "department": department,
        "activity": activity
    }


# =========================
# AGENT 3: PRIORITY AGENT
# =========================

def priority_agent(state: ComplaintState):
    text = state["description"].lower()

    urgent_words = [
        "emergency", "urgent", "danger", "accident",
        "fire", "injury", "overflow", "exposed wire",
        "electric shock", "major leakage", "flooding",
        "collapse", "severe", "no light", "no electricity",
        "power outage", "electricity outage", "power cut",
        "power failure", "no power"
    ]

    low_words = [
        "minor", "small issue", "slightly damaged",
        "cosmetic", "not urgent", "non-urgent"
    ]

    negated_urgent = [
        "not urgent", "no emergency", "not an emergency",
        "not dangerous", "no danger"
    ]

    has_negation = any(word in text for word in negated_urgent)
    has_urgent = any(word in text for word in urgent_words)
    has_low = any(word in text for word in low_words)

    if has_urgent and not has_negation:
        priority = "High"
        estimated_time = "Within 24 hours"

    elif has_low:
        priority = "Low"
        estimated_time = "5–7 days"

    else:
        priority = "Medium"
        estimated_time = "2–3 days"

    activity = state["activity"] + [
        f"Priority Agent: Priority assigned as {priority}."
    ]

    return {
        "priority": priority,
        "estimated_time": estimated_time,
        "activity": activity
    }


# =========================
# AGENT 4: ROUTING AGENT
# =========================

def routing_agent(state: ComplaintState):
    activity = state["activity"] + [
        f"Routing Agent: Complaint forwarded to {state['department']}."
    ]

    return {"activity": activity}


# =========================
# LANGGRAPH WORKFLOW
# =========================

workflow = StateGraph(ComplaintState)

workflow.add_node("intake", intake_agent)
workflow.add_node("classification", classification_agent)
workflow.add_node("priority", priority_agent)
workflow.add_node("routing", routing_agent)

workflow.add_edge(START, "intake")
workflow.add_edge("intake", "classification")
workflow.add_edge("classification", "priority")
workflow.add_edge("priority", "routing")
workflow.add_edge("routing", END)

complaint_graph = workflow.compile()


# =========================
# SUBMIT COMPLAINT API
# =========================

@app.post("/api/complaints")
def submit_complaint(complaint: ComplaintRequest):

    if not complaint.description.strip():
        raise HTTPException(
            status_code=400,
            detail="Complaint description cannot be empty."
        )

    initial_state = {
        "description": complaint.description,
        "location": complaint.location,
        "category": "",
        "department": "",
        "priority": "",
        "estimated_time": "",
        "activity": []
    }

    result = complaint_graph.invoke(initial_state)

    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO complaints
        (description, location, category, department,
         priority, estimated_time, status, agent_activity, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        complaint.description,
        complaint.location,
        result["category"],
        result["department"],
        result["priority"],
        result["estimated_time"],
        "Pending",
        json.dumps(result["activity"]),
        created_at
    ))

    complaint_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return {
        "id": complaint_id,
        "description": complaint.description,
        "location": complaint.location,
        "category": result["category"],
        "department": result["department"],
        "priority": result["priority"],
        "estimated_time": result["estimated_time"],
        "status": "Pending",
        "agent_activity": result["activity"],
        "created_at": created_at
    }


# =========================
# GET COMPLAINT HISTORY API
# =========================

@app.get("/api/complaints")
def get_complaints():
    conn = get_connection()

    complaints = conn.execute(
        "SELECT * FROM complaints ORDER BY id DESC"
    ).fetchall()

    conn.close()

    result = []

    for complaint in complaints:
        item = dict(complaint)

        try:
            item["agent_activity"] = json.loads(
                item["agent_activity"] or "[]"
            )
        except (json.JSONDecodeError, TypeError):
            item["agent_activity"] = []

        result.append(item)

    return result


# =========================
# UPDATE COMPLAINT STATUS
# =========================

class StatusRequest(BaseModel):
    status: str


@app.put("/api/complaints/{complaint_id}/status")
def update_status(complaint_id: int, data: StatusRequest):

    if data.status not in ["Pending", "Completed", "Resolved"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid complaint status."
        )

    conn = get_connection()

    cursor = conn.cursor()

    existing = cursor.execute(
        "SELECT id FROM complaints WHERE id = ?",
        (complaint_id,)
    ).fetchone()

    if not existing:
        conn.close()
        raise HTTPException(
            status_code=404,
            detail="Complaint not found."
        )

    cursor.execute(
        "UPDATE complaints SET status = ? WHERE id = ?",
        (data.status, complaint_id)
    )

    conn.commit()

    updated = cursor.execute(
        "SELECT * FROM complaints WHERE id = ?",
        (complaint_id,)
    ).fetchone()

    conn.close()

    return dict(updated)


# =========================
# DELETE ALL COMPLAINTS
# =========================

@app.delete("/api/complaints")
def delete_all_complaints():

    conn = get_connection()
    conn.execute("DELETE FROM complaints")
    conn.commit()
    conn.close()

    return {
        "message": "All complaint history deleted successfully."
    }
