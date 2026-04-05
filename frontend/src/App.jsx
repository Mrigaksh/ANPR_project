import React, { useState, useEffect } from 'react';
import './App.css';

// Generic fetch wrapper (Will connect to Flask: http://localhost:5000/api)
const API_URL = 'http://localhost:5000/api';

function App() {
  const [auth, setAuth] = useState({ token: null, role: null, username: null });
  const [activeTab, setActiveTab] = useState('detection'); // Default tab
  const [isLoginMode, setIsLoginMode] = useState(true);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Dynamic Data States
  const [myStats, setMyStats] = useState({ total_scans: 0, average_confidence: 0 });
  const [myHistory, setMyHistory] = useState([]);

  const [teamHistory, setTeamHistory] = useState([]);

  const [adminStats, setAdminStats] = useState({ total_users: 0, total_scans: 0, subadmins: 0 });
  const [usersList, setUsersList] = useState([]);

  // Upload States
  const [uploadFile, setUploadFile] = useState(null);
  const [uploadResult, setUploadResult] = useState(null);
  const [isUploading, setIsUploading] = useState(false);

  // --- API Handlers ---
  const handleRegister = async (e) => {
    e.preventDefault();
    const username = e.target.username.value;
    const email = e.target.email.value;
    const password = e.target.password.value;
    try {
      const res = await fetch(`${API_URL}/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, email, password })
      });
      const data = await res.json();
      if (res.ok) {
        alert("Registration successful! Please log in.");
        setIsLoginMode(true); // Redirect back to login mode
      } else {
        alert(data.message);
      }
    } catch (err) {
      alert("Server connection failed. Is Flask running?");
    }
  };


  const handleLogin = async (e) => {
    e.preventDefault();
    const username = e.target.username.value;
    const password = e.target.password.value;
    try {
      const res = await fetch(`${API_URL}/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
      });
      const data = await res.json();
      if (res.ok) {
        setAuth({ token: data.token, role: data.role, username: data.username });
      } else {
        alert(data.message);
      }
    } catch (err) {
      alert("Server connection failed. Is Flask running?");
    }
  };

  const handleLogout = () => {
    setAuth({ token: null, role: null, username: null });
    setActiveTab('detection');
    setUploadResult(null);
  };

  const authFetch = async (endpoint) => {
    try {
      const res = await fetch(`${API_URL}${endpoint}`, {
        headers: { 'Authorization': `Bearer ${auth.token}` }
      });
      return await res.json();
    } catch (err) {
      console.error("Fetch Error:", err);
      return [];
    }
  };

  // --- UI Helpers ---
  const getConfidenceMeta = (conf) => {
    const percent = (conf * 100).toFixed(1);
    if (conf >= 0.75) return { color: '#10b981', label: 'High', percent }; // Green
    if (conf >= 0.50) return { color: '#f59e0b', label: 'Medium', percent }; // Orange
    return { color: '#ef4444', label: 'Low', percent }; // Red
  };

  const handleUploadClick = async () => {
    if (!uploadFile) return alert("Select an image first!");
    setIsUploading(true);

    const formData = new FormData();
    formData.append('image', uploadFile);

    try {
      const res = await fetch(`${API_URL}/upload`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${auth.token}` },
        body: formData
      });
      const data = await res.json();
      if (res.ok) {
        setUploadResult({
          text: data.plate_text,
          conf: data.confidence,
          imageUrl: data.image_url
        });
        // Refresh stats and history
        authFetch('/my-stats').then(d => setMyStats(d));
        authFetch('/my-history').then(d => setMyHistory(d));
      } else {
        alert(data.message);
      }
    } catch (err) {
      alert("Error processing image.");
    }
    setIsUploading(false);
  };

  // --- Dynamic Data Pre-loader ---
  useEffect(() => {
    if (!auth.token) return;

    if (activeTab === 'detection') {
      authFetch('/my-stats').then(data => setMyStats(data || { total_scans: 0, average_confidence: 0 }));
      authFetch('/my-history').then(data => setMyHistory(data || []));
    }
    else if (activeTab === 'team') {
      authFetch('/team-history').then(data => setTeamHistory(data || []));
    }
    else if (activeTab === 'admin') {
      authFetch('/admin/dashboard').then(data => setAdminStats(data || { total_users: 0, total_scans: 0, subadmins: 0 }));
      authFetch('/admin/users').then(data => setUsersList(data || []));
    }
  }, [activeTab, auth.token]);

  // --- Render Login if not Authed ---
  if (!auth.token) {
    return (
      <div className="auth-container">
        <div className="card auth-card">
          <h2 style={{ color: 'var(--primary)' }}>ANPR Platform</h2>
          <p>{isLoginMode ? "Sign in to your account" : "Create a new account"}</p>

          {isLoginMode ? (
            <form onSubmit={handleLogin}>
              <input className="input-field" name="username" type="text" placeholder="Username" required />
              <input className="input-field" name="password" type="password" placeholder="Password" required />
              <button className="primary-btn" type="submit" style={{ marginTop: '10px' }}>Login</button>
              <p style={{ marginTop: '1rem', textAlign: 'center', fontSize: '0.9rem' }}>
                Don't have an account? <span style={{ color: '#007bff', cursor: 'pointer', fontWeight: 'bold' }} onClick={() => setIsLoginMode(false)}>Register here</span>
              </p>
            </form>
          ) : (
            <form onSubmit={handleRegister}>
              <input className="input-field" name="username" type="text" placeholder="Username" required />
              <input className="input-field" name="email" type="email" placeholder="Email" required />
              <input className="input-field" name="password" type="password" placeholder="Password" required />
              <button className="primary-btn" type="submit" style={{ marginTop: '10px' }}>Register</button>
              <p style={{ marginTop: '1rem', textAlign: 'center', fontSize: '0.9rem' }}>
                Already have an account? <span style={{ color: '#007bff', cursor: 'pointer', fontWeight: 'bold' }} onClick={() => setIsLoginMode(true)}>Login here</span>
              </p>
            </form>
          )}
        </div>
      </div>
    );
  }

  const closeSidebar = () => setSidebarOpen(false);

  // --- RENDER SECTIONS BASED ON ROLE ---
  return (
    <div className="app-container">

      {/* Mobile hamburger button */}
      <button className="sidebar-toggle" onClick={() => setSidebarOpen(o => !o)} aria-label="Toggle menu">
        {sidebarOpen ? '✕' : '☰'}
      </button>

      {/* Mobile overlay */}
      <div className={`sidebar-overlay${sidebarOpen ? ' visible' : ''}`} onClick={closeSidebar} />

      {/* Dynamic Sidebar */}
      <div className={`sidebar${sidebarOpen ? ' open' : ''}`}>
        <h2>ANPR Hub</h2>
        <div style={{ marginBottom: '2rem', textAlign: 'center', color: '#94a3b8', fontSize: '0.9rem' }}>
          Welcome, {auth.username} <br /><span style={{ textTransform: 'uppercase', fontWeight: 600 }}>[{auth.role}]</span>
        </div>

        <button className={activeTab === 'detection' ? 'active' : ''} onClick={() => { setActiveTab('detection'); closeSidebar(); }}>
          Detection Module
        </button>

        {/* Subadmin & Admin Only */}
        {['subadmin', 'admin'].includes(auth.role) && (
          <button className={activeTab === 'team' ? 'active' : ''} onClick={() => { setActiveTab('team'); closeSidebar(); }}>
            Team Section
          </button>
        )}

        {/* Admin Only */}
        {auth.role === 'admin' && (
          <button className={activeTab === 'admin' ? 'active' : ''} onClick={() => { setActiveTab('admin'); closeSidebar(); }}>
            Admin Management
          </button>
        )}

        <button className="logout-btn" onClick={handleLogout}>Log Out</button>
      </div>

      {/* Dynamic Content Outlet */}
      <div className="main-content">

        {/* DETECTION MODULE TAB */}
        {activeTab === 'detection' && (
          <div>
            <h1>Plate Detection</h1>
            <div className="card">
              <h3>Upload & Process</h3>
              <p>Upload an image to extract number plate data.</p>
              <input type="file" className="input-field" style={{ marginBottom: '1rem' }} onChange={(e) => setUploadFile(e.target.files[0])} />
              <button className="primary-btn" style={{ width: '200px' }} onClick={handleUploadClick} disabled={isUploading}>
                {isUploading ? 'Processing ML...' : 'Process Image'}
              </button>

              {uploadResult && (
                <div className="upload-result">
                  {uploadResult.imageUrl && (
                    <img
                      src={`http://localhost:5000/api/uploads/${uploadResult.imageUrl}`}
                      alt="Scan"
                    />
                  )}
                  <div className="plate-display">
                    <small>Detected Plate</small>
                    <strong>{uploadResult.text}</strong>
                    <div style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', padding: '4px 12px', borderRadius: '20px', background: getConfidenceMeta(uploadResult.conf).color + '22', color: getConfidenceMeta(uploadResult.conf).color, fontWeight: 700, fontSize: '0.85rem' }}>
                      <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: getConfidenceMeta(uploadResult.conf).color, flexShrink: 0 }}></span>
                      {getConfidenceMeta(uploadResult.conf).label} ({getConfidenceMeta(uploadResult.conf).percent}%)
                    </div>
                  </div>
                </div>
              )}
            </div>

            <div className="metric-grid">
              <div className="metric-box">
                <h3>My Total Scans</h3>
                <p>{myStats.total_scans}</p>
              </div>
              <div className="metric-box">
                <h3>Average Confidence</h3>
                <p style={{ color: getConfidenceMeta(myStats.average_confidence).color }}>
                  {getConfidenceMeta(myStats.average_confidence).percent}%
                </p>
              </div>
            </div>

            <div className="card">
              <h3>My History</h3>
              <div className="table-wrapper">
                <table className="data-table">
                  <thead>
                    <tr><th>Date</th><th>Image</th><th>Plate Text</th><th>Confidence</th></tr>
                  </thead>
                  <tbody>
                    {myHistory.map((row, i) => {
                      const meta = getConfidenceMeta(row.conf);
                      return (
                        <tr key={i}>
                          <td>{new Date(row.date).toLocaleDateString()}</td>
                          <td>
                            <img
                              src={`http://localhost:5000/api/uploads/${row.image}`}
                              alt="thumb"
                              style={{ width: '60px', height: '40px', objectFit: 'cover', borderRadius: '4px' }}
                            />
                          </td>
                          <td style={{ fontWeight: 600 }}>{row.text}</td>
                          <td>
                            <span style={{ color: meta.color, fontWeight: 700 }}>
                              {meta.percent}% ({meta.label})
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                    {myHistory.length === 0 && <tr><td colSpan="4" style={{ textAlign: 'center', color: '#cbd5e1' }}>No recognitions yet.</td></tr>}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* TEAM MODULE TAB */}
        {activeTab === 'team' && ['subadmin', 'admin'].includes(auth.role) && (
          <div>
            <h1>Team Section</h1>
            <div className="metric-grid">
              <div className="metric-box">
                <h3>System Records</h3>
                <p>{teamHistory.length}</p>
              </div>
              <div className="metric-box">
                <h3>Export Data</h3>
                <button
                  className="primary-btn"
                  style={{ marginTop: '10px' }}
                  onClick={async () => {
                    try {
                      const res = await fetch(`${API_URL}/export-csv`, {
                        headers: { 'Authorization': `Bearer ${auth.token}` }
                      });
                      if (!res.ok) {
                        const err = await res.json();
                        alert(err.message);
                        return;
                      }
                      // Convert response to downloadable file
                      const blob = await res.blob();
                      const url = window.URL.createObjectURL(blob);
                      const a = document.createElement('a');
                      a.href = url;
                      a.download = 'team_recognitions.csv';
                      document.body.appendChild(a);
                      a.click();
                      a.remove();
                      window.URL.revokeObjectURL(url);
                    } catch (err) {
                      alert('Failed to download CSV.');
                    }
                  }}
                >
                  Download CSV
                </button>
              </div>
            </div>
            <div className="card">
              <h3>Team History</h3>
              <div className="table-wrapper">
                <table className="data-table">
                  <thead>
                    <tr><th>User</th><th>Date</th><th>Plate Text</th><th>Confidence</th></tr>
                  </thead>
                  <tbody>
                    {teamHistory.map((row, i) => (
                      <tr key={i}>
                        <td>{row.user}</td>
                        <td>{new Date(row.date).toLocaleDateString()}</td>
                        <td style={{ fontWeight: 600 }}>{row.text}</td>
                        <td>{(row.conf * 100).toFixed(1)}%</td>
                      </tr>
                    ))}
                    {teamHistory.length === 0 && <tr><td colSpan="4" style={{ textAlign: 'center', color: '#cbd5e1' }}>No system records.</td></tr>}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* ADMIN MODULE TAB */}
        {activeTab === 'admin' && auth.role === 'admin' && (
          <div>
            <h1>Admin Dashboard</h1>
            <div className="metric-grid">
              <div className="metric-box">
                <h3>Total Accounts</h3>
                <p>{adminStats.total_users}</p>
              </div>
              <div className="metric-box">
                <h3>Active Subadmins</h3>
                <p>{adminStats.subadmins}</p>
              </div>
              <div className="metric-box">
                <h3>System Scans</h3>
                <p>{adminStats.total_scans}</p>
              </div>
            </div>
            <div className="card">
              <h3>User Management</h3>
              <div className="table-wrapper">
                <table className="data-table">
                  <thead>
                    <tr><th>Username</th><th>Email</th><th>Role</th><th>Action</th></tr>
                  </thead>
                  <tbody>
                    {usersList.map((u, i) => (
                      <tr key={i}>
                        <td>{u.username}</td>
                        <td>{u.email}</td>
                        <td style={{ textTransform: 'capitalize' }}>{u.role}</td>
                        <td>
                          {u.role !== 'admin' && (
                            <button
                              style={{ padding: '4px 8px', borderRadius: '4px', cursor: 'pointer', background: 'var(--secondary)', border: 'none', color: 'var(--primary)' }}
                              onClick={async () => {
                                await fetch(`${API_URL}/admin/users/${u.id}/role`, {
                                  method: 'PUT',
                                  headers: { 'Authorization': `Bearer ${auth.token}`, 'Content-Type': 'application/json' },
                                  body: JSON.stringify({ role: u.role === 'user' ? 'subadmin' : 'user' })
                                });
                                authFetch('/admin/users').then(data => setUsersList(data || [])); // Auto-refresh users
                              }}
                            >
                              Toggle Role
                            </button>
                          )}
                          {u.role === 'admin' && <span style={{ color: '#94a3b8' }}>-</span>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

      </div>
    </div>
  );
}

export default App;