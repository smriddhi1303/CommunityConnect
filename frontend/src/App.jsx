
import { useState, useEffect } from "react";
import "./App.css";

const API_URL = "http://127.0.0.1:8000/api/complaints";
const PROFILE_URL = "http://127.0.0.1:8000/api/profile";

const emptyProfile = {
  full_name: "",
  email: "",
  phone: "",
  address: "",
  city: "",
  state: "",
  pincode: "",
};

function App() {
  const [profile, setProfile] = useState(emptyProfile);
  const [savedProfile, setSavedProfile] = useState(emptyProfile);
  const [memberSince, setMemberSince] = useState("");

  const [complaints, setComplaints] = useState([]);
  const [description, setDescription] = useState("");
  const [location, setLocation] = useState("");

  const [editing, setEditing] = useState(false);
  const [profileLoading, setProfileLoading] = useState(true);
  const [savingProfile, setSavingProfile] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  // LOAD PROFILE
  const fetchProfile = async () => {
    try {
      const response = await fetch(PROFILE_URL);
      if (!response.ok) throw new Error("Profile loading failed");

      const data = await response.json();
      const p = data.profile || data;

      const loaded = {
        full_name: p.full_name || "",
        email: p.email || "",
        phone: p.phone || "",
        address: p.address || "",
        city: p.city || "",
        state: p.state || "",
        pincode: p.pincode || "",
      };

      setProfile(loaded);
      setSavedProfile(loaded);
      setMemberSince(p.created_at || "");

      if (!loaded.full_name) setEditing(true);
    } catch (err) {
      console.error(err);
      setError("Could not load profile.");
    } finally {
      setProfileLoading(false);
    }
  };

  // LOAD COMPLAINTS
  const fetchComplaints = async () => {
    try {
      const response = await fetch(API_URL);
      if (!response.ok) throw new Error("History loading failed");

      const data = await response.json();
      setComplaints(data);
    } catch (err) {
      console.error(err);
      setError("Could not load complaint history.");
    }
  };

  useEffect(() => {
    fetchProfile();
    fetchComplaints();
  }, []);

  // PROFILE INPUT
  const handleProfileChange = (e) => {
    setProfile({
      ...profile,
      [e.target.name]: e.target.value,
    });
  };

  // SAVE PROFILE
  const saveProfile = async (e) => {
    e.preventDefault();
    setSavingProfile(true);
    setError("");
    setMessage("");

    try {
      const response = await fetch(PROFILE_URL, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(profile),
      });

      if (!response.ok) throw new Error("Profile save failed");

      const data = await response.json();
      const p = data.profile || data;

      const updated = {
        full_name: p.full_name ?? profile.full_name,
        email: p.email ?? profile.email,
        phone: p.phone ?? profile.phone,
        address: p.address ?? profile.address,
        city: p.city ?? profile.city,
        state: p.state ?? profile.state,
        pincode: p.pincode ?? profile.pincode,
      };

      setProfile(updated);
      setSavedProfile(updated);
      setMemberSince(p.created_at || memberSince || new Date().toISOString());
      setEditing(false);
      setMessage("Profile saved successfully.");
    } catch (err) {
      console.error(err);
      setError("Could not save profile.");
    } finally {
      setSavingProfile(false);
    }
  };

  // SUBMIT COMPLAINT
  const submitComplaint = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setError("");
    setMessage("");

    try {
      const response = await fetch(API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ description, location }),
      });

      if (!response.ok) throw new Error("Complaint submission failed");

      setDescription("");
      setLocation("");
      await fetchComplaints();
      setMessage("Your complaint has been submitted successfully.");
    } catch (err) {
      console.error(err);
      setError("Could not submit complaint.");
    } finally {
      setSubmitting(false);
    }
  };

  // MARK COMPLAINT COMPLETED
  const completeComplaint = async (item) => {
    if (item.status === "Resolved") return;

    const confirmed = window.confirm(
      "Has this complaint actually been resolved?"
    );

    if (!confirmed) return;

    try {
      const response = await fetch(`${API_URL}/${item.id}/status`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: "Resolved" }),
      });

      if (!response.ok) throw new Error("Status update failed");

      await fetchComplaints();
      setMessage("Complaint marked as completed.");
      setError("");
    } catch (err) {
      console.error(err);
      setError("Could not update complaint status.");
    }
  };

  // REFRESH HISTORY - UPDATED
  const refreshHistory = async () => {
    if (refreshing) return;

    setRefreshing(true);
    setError("");
    setMessage("");

    try {
      const response = await fetch(API_URL);

      if (!response.ok) {
        throw new Error("Could not refresh complaint history.");
      }

      const data = await response.json();

      setComplaints(data);
      setMessage("Complaint history refreshed successfully!");
    } catch (err) {
      console.error("Refresh error:", err);
      setError("Could not refresh complaint history. Check backend connection.");
    } finally {
      setRefreshing(false);
    }
  };

  // DELETE ALL HISTORY
  const deleteHistory = async () => {
    if (!complaints.length) return;

    const confirmed = window.confirm(
      "Are you sure you want to delete all complaint records?"
    );

    if (!confirmed) return;

    try {
      const response = await fetch(API_URL, { method: "DELETE" });
      if (!response.ok) throw new Error("Delete failed");

      setComplaints([]);
      setMessage("Complaint history deleted.");
    } catch (err) {
      console.error(err);
      setError("Could not delete complaint history.");
    }
  };

  // STATISTICS
  const total = complaints.length;

  const resolved = complaints.filter(
    (item) => item.status === "Resolved"
  ).length;

  const pending = total - resolved;

  const resolutionPercent = total
    ? Math.round((resolved / total) * 100)
    : 0;

  // GRAPH DATA: CUMULATIVE RESOLVED COMPLAINTS
  const sortedComplaints = [...complaints].sort(
    (a, b) => new Date(a.created_at) - new Date(b.created_at)
  );

  let resolvedSoFar = 0;

  const graphValues = sortedComplaints.map((item) => {
    if (item.status === "Resolved") resolvedSoFar++;
    return resolvedSoFar;
  });

  const graphPoints = graphValues.length
    ? graphValues.map((value, index) => {
        const x =
          graphValues.length === 1
            ? 50
            : 20 + (index / (graphValues.length - 1)) * 360;

        const maxValue = Math.max(1, resolved, ...graphValues);
        const y = 145 - (value / maxValue) * 115;

        return `${x},${y}`;
      }).join(" ")
    : "20,145 380,145";

  const initials = profile.full_name
    ? profile.full_name.trim().charAt(0).toUpperCase()
    : "U";

  const formattedMemberSince = memberSince
    ? new Date(memberSince).toLocaleDateString("en-IN", {
        month: "short",
        year: "numeric",
      })
    : "New member";

  return (
    <div className="app">
      {/* HEADER */}
      <header className="hero">
        <h1>CommunityConnect</h1>
        <p>AI-Powered Community Problem Solving Platform</p>
        <span>Report problems. Connect departments. Build better communities.</span>
      </header>

      <main className="main-container">

        {/* TOP ROW: PROFILE + RECORDS */}
        <section className="top-row">

          {/* PROFILE */}
          <div className="profile-section">
            <div className="section-heading">
              <div>
                <span className="section-kicker">YOUR ACCOUNT</span>
                <h2>My Profile</h2>
              </div>

              {!editing && !profileLoading && (
                <button
                  className="edit-button"
                  onClick={() => {
                    setEditing(true);
                    setMessage("");
                    setError("");
                  }}
                >
                  ✎ Edit
                </button>
              )}
            </div>

            {profileLoading ? (
              <p className="muted">Loading profile...</p>
            ) : editing ? (
              <form className="profile-form" onSubmit={saveProfile}>
                <div className="profile-fields">
                  {[
                    ["full_name", "Full Name"],
                    ["email", "Email Address"],
                    ["phone", "Phone Number"],
                    ["address", "Address"],
                    ["city", "City"],
                    ["state", "State"],
                    ["pincode", "PIN Code"],
                  ].map(([name, label]) => (
                    <div className="field" key={name}>
                      <label>{label}</label>
                      <input
                        name={name}
                        type={name === "email" ? "email" : "text"}
                        value={profile[name]}
                        onChange={handleProfileChange}
                        placeholder={`Enter ${label.toLowerCase()}`}
                        required
                      />
                    </div>
                  ))}
                </div>

                <div className="profile-buttons">
                  <button className="primary-button" disabled={savingProfile}>
                    {savingProfile ? "Saving..." : "Save Profile"}
                  </button>

                  {savedProfile.full_name && (
                    <button
                      type="button"
                      className="secondary-button"
                      onClick={() => {
                        setProfile(savedProfile);
                        setEditing(false);
                      }}
                    >
                      Cancel
                    </button>
                  )}
                </div>
              </form>
            ) : (
              <div className="profile-info">
                <div className="profile-identity">
                  <div className="avatar">{initials}</div>
                  <div>
                    <h3>{profile.full_name}</h3>
                    <p>Community Member</p>
                    <span>Member since {formattedMemberSince}</span>
                  </div>
                </div>

                <div className="profile-details">
                  <div>
                    <span>Email</span>
                    <strong>{profile.email || "Not provided"}</strong>
                  </div>
                  <div>
                    <span>Phone</span>
                    <strong>{profile.phone || "Not provided"}</strong>
                  </div>
                  <div>
                    <span>Address</span>
                    <strong>{profile.address || "Not provided"}</strong>
                  </div>
                  <div>
                    <span>City</span>
                    <strong>{profile.city || "Not provided"}</strong>
                  </div>
                  <div>
                    <span>State</span>
                    <strong>{profile.state || "Not provided"}</strong>
                  </div>
                  <div>
                    <span>PIN Code</span>
                    <strong>{profile.pincode || "Not provided"}</strong>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* RECORDS CIRCLE */}
          <div className="records-section">
            <div className="records-circle">
              <span className="records-title">RECORDS</span>

              <div className="record-stat">
                <strong>{resolved}</strong>
                <span>Resolved</span>
              </div>

              <div className="record-divider"></div>

              <div className="record-stat">
                <strong>{total}</strong>
                <span>Total Complaints</span>
              </div>
            </div>

            <p className="records-caption">Your community activity</p>
          </div>
        </section>

        {/* BOTTOM ROW */}
        <section className="bottom-grid">

          {/* COMPLAINT FORM */}
          <div className="complaint-section">
            <span className="section-kicker">RAISE AN ISSUE</span>
            <h2>Report a Problem</h2>
            <p className="section-description">
              Tell us about a community issue. Our AI agents will analyze and
              route it to the right department.
            </p>

            <form onSubmit={submitComplaint}>
              <div className="field">
                <label>Complaint Description</label>
                <textarea
                  rows="5"
                  placeholder="Describe your problem..."
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  required
                />
              </div>

              <div className="field">
                <label>Location</label>
                <input
                  type="text"
                  placeholder="Enter problem location"
                  value={location}
                  onChange={(e) => setLocation(e.target.value)}
                  required
                />
              </div>

              <button className="primary-button submit-button" disabled={submitting}>
                {submitting ? "AI Agents Processing..." : "Submit Complaint"}
              </button>
            </form>

            <div className="form-note">
              <span className="live-dot"></span>
              AI-powered complaint analysis and routing
            </div>
          </div>

          {/* HISTORY */}
          <div className="history-section">
            <div className="section-heading history-heading">
              <div>
                <span className="section-kicker">YOUR SUBMISSIONS</span>
                <h2>History</h2>
              </div>

              <button
                className="refresh-button"
                onClick={refreshHistory}
                disabled={refreshing}
                title="Refresh history"
              >
                {refreshing ? "..." : "↻"}
              </button>
            </div>

            <div className="history-summary">
              <span>{pending} Pending</span>
              <span>{resolved} Resolved</span>
            </div>

            {complaints.length === 0 ? (
              <div className="empty-history">
                <span>📋</span>
                <p>No complaints yet</p>
                <small>Your submitted complaints will appear here.</small>
              </div>
            ) : (
              <div className="history-list">
                {complaints.map((item) => {
                  const isResolved = item.status === "Resolved";

                  return (
                    <article className="history-card" key={item.id}>
                      <div className="history-card-top">
                        <strong>{item.category || "General Complaint"}</strong>
                        <span className={`status-chip ${isResolved ? "resolved" : "pending"}`}>
                          {isResolved ? "Completed" : item.status || "Pending"}
                        </span>
                      </div>

                      <p>{item.description}</p>

                      <div className="history-meta">
                        <span>📍 {item.location}</span>
                        <span>CC{item.id}</span>
                      </div>

                      <div className="history-extra">
                        <span className={`priority-text ${(item.priority || "medium").toLowerCase()}`}>
                          {item.priority || "Medium"} Priority
                        </span>
                        <span>⏱ {item.estimated_time || "Not available"}</span>
                      </div>

                      <div className="department-line">
                        Department: {item.department || "Not assigned"}
                      </div>

                      {item.agent_activity?.length > 0 && (
                        <details className="agent-details">
                          <summary>View AI Agent Activity</summary>
                          {item.agent_activity.map((activity, index) => (
                            <p key={index}>✓ {activity}</p>
                          ))}
                        </details>
                      )}

                      <button
                        className={`complete-button ${isResolved ? "already-completed" : ""}`}
                        onClick={() => completeComplaint(item)}
                        disabled={isResolved}
                      >
                        {isResolved ? "✓ Completed" : "Mark as Completed"}
                      </button>
                    </article>
                  );
                })}
              </div>
            )}

            <button
              className="delete-history-button"
              onClick={deleteHistory}
              disabled={complaints.length === 0}
            >
              Delete All History
            </button>
          </div>

          {/* PROGRESS */}
          <div className="progress-section">
            <span className="section-kicker">YOUR PERFORMANCE</span>
            <h2>Progress</h2>
            <p className="section-description">
              Track the resolution of your reported problems.
            </p>

            <div className="progress-percentage">
              <strong>{resolutionPercent}%</strong>
              <span>Resolution Rate</span>
            </div>

            <div className="progress-track">
              <div
                className="progress-fill"
                style={{ width: `${resolutionPercent}%` }}
              ></div>
            </div>

            <div className="progress-legend">
              <div>
                <span className="legend-dot resolved-dot"></span>
                <span>Resolved</span>
                <strong>{resolved}</strong>
              </div>

              <div>
                <span className="legend-dot pending-dot"></span>
                <span>Pending</span>
                <strong>{pending}</strong>
              </div>
            </div>

            <div className="chart-area">
              <h3>Resolution Trend</h3>

              <svg
                className="progress-chart"
                viewBox="0 0 400 170"
                preserveAspectRatio="none"
                role="img"
                aria-label="Cumulative complaint resolution trend"
              >
                <line x1="20" y1="145" x2="380" y2="145" className="chart-axis" />
                <line x1="20" y1="30" x2="20" y2="145" className="chart-axis" />

                <line x1="20" y1="87" x2="380" y2="87" className="chart-gridline" />

                <polyline
                  points={graphPoints}
                  className="chart-line"
                />

                {graphValues.length > 0 && (
                  <circle
                    cx={graphValues.length === 1 ? 50 : 380}
                    cy={145 - (resolved / Math.max(1, resolved, ...graphValues)) * 115}
                    r="5"
                    className="chart-point"
                  />
                )}
              </svg>

              <div className="chart-labels">
                <span>Complaints</span>
                <span>Resolved</span>
              </div>
            </div>

            <div className="progress-message">
              {total === 0
                ? "Submit your first complaint to start tracking progress."
                : resolved === total
                ? "Great work! All your complaints are resolved."
                : `${pending} complaint(s) are still awaiting resolution.`}
            </div>
          </div>
        </section>

        {error && <div className="global-message error-message">{error}</div>}
        {message && <div className="global-message success-message">{message}</div>}
      </main>

      <footer>
        CommunityConnect <span>•</span> AI-Powered Community Platform
      </footer>
    </div>
  );
}

export default App;
