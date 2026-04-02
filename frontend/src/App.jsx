import React, { useState } from 'react';
import './App.css';

// Generic fetch wrapper (Will connect to Flask: http://localhost:5000/api)
const API_URL = 'http://localhost:5000/api';

function App() {
  const [auth, setAuth] = useState({ token: null, role: null, username: null });
  const [activeTab, setActiveTab] = useState('detection'); // Default tab

  // Basic mock auth logic for now
  const handleLogin = (e) => {
    e.preventDefault();
    // In real app, fetch /api/login here
    // Simulated token:
    setAuth({ token: 'mock-jwt-token', role: 'admin', username: 'Ashutec' });
  };

  const handleLogout = () => {
    setAuth({ token: null, role: null, username: null });
    setActiveTab('detection');
  };

  if (!auth.token) {
    return (
      <div className="auth-container">
        <div className="card auth-card">
          <h2 style={{color: 'var(--primary)'}}>ANPR Platform</h2>
          <p>Sign in to your account</p>
          <form onSubmit={handleLogin}>
            <input className="input-field" type="text" placeholder="Username" required />
            <input className="input-field" type="password" placeholder="Password" required />
            <button className="primary-btn" type="submit">Login</button>
          </form>
        </div>
      </div>
    );
  }

  // --- RENDER SECTIONS BASED ON ROLE ---
  return (
    <div className="app-container">
      
      {/* Dynamic Sidebar */}
      <div className="sidebar">
        <h2>ANPR Hub</h2>
        <div style={{marginBottom:'2rem', textAlign:'center', color:'#94a3b8', fontSize:'0.9rem'}}>
          Welcome, {auth.username} <br/><span style={{textTransform:'uppercase', fontWeight:600}}>[{auth.role}]</span>
        </div>

        <button className={activeTab === 'detection' ? 'active' : ''} onClick={() => setActiveTab('detection')}>
          Detection Module
        </button>
        
        {/* Subadmin & Admin Only: Team Section */}
        {['subadmin', 'admin'].includes(auth.role) && (
          <button className={activeTab === 'team' ? 'active' : ''} onClick={() => setActiveTab('team')}>
            Team Section
          </button>
        )}

        {/* Admin Only: Admin Dashboard */}
        {auth.role === 'admin' && (
          <button className={activeTab === 'admin' ? 'active' : ''} onClick={() => setActiveTab('admin')}>
            Admin Management
          </button>
        )}

        <button className="logout-btn" onClick={handleLogout}>Log Out</button>
      </div>

      {/* Dynamic Content Outlet */}
      <div className="main-content">
        
        {activeTab === 'detection' && (
          <div>
            <h1>Plate Detection</h1>
            <div className="card">
              <h3>Upload & Process</h3>
              <p>Upload an image to extract number plate data.</p>
              <input type="file" className="input-field" style={{marginBottom: '1rem'}} />
              <button className="primary-btn" style={{width: '200px'}}>Process Image</button>
            </div>
            <div className="metric-grid">
              <div className="metric-box">
                <h3>My Total Scans</h3>
                <p>124</p>
              </div>
              <div className="metric-box">
                <h3>Average Confidence</h3>
                <p>87%</p>
              </div>
            </div>
            <div className="card">
              <h3>My History</h3>
              <table className="data-table">
                <thead>
                  <tr><th>Date</th><th>Plate Text</th><th>Confidence</th></tr>
                </thead>
                <tbody>
                  <tr><td>2026-04-02</td><td>NYC-1234</td><td>92.4%</td></tr>
                </tbody>
              </table>
            </div>
          </div>
        )}

        {activeTab === 'team' && ['subadmin', 'admin'].includes(auth.role) && (
          <div>
            <h1>Team Section</h1>
            <div className="metric-grid">
              <div className="metric-box">
                <h3>System Records</h3>
                <p>8,204</p>
              </div>
              <div className="metric-box">
                <h3>Export Data</h3>
                <button className="primary-btn" style={{marginTop:'10px'}}>Download CSV</button>
              </div>
            </div>
            <div className="card">
              <h3>Team History</h3>
              <table className="data-table">
                <thead>
                  <tr><th>User</th><th>Date</th><th>Plate Text</th><th>Confidence</th></tr>
                </thead>
                <tbody>
                  <tr><td>john_doe</td><td>2026-04-02</td><td>XYZ-999</td><td>88.1%</td></tr>
                </tbody>
              </table>
            </div>
          </div>
        )}

        {activeTab === 'admin' && auth.role === 'admin' && (
          <div>
            <h1>Admin Dashboard</h1>
            <div className="metric-grid">
              <div className="metric-box">
                <h3>Total Accounts</h3>
                <p>42</p>
              </div>
              <div className="metric-box">
                <h3>Active Subadmins</h3>
                <p>3</p>
              </div>
            </div>
            <div className="card">
              <h3>User Management</h3>
              <table className="data-table">
                <thead>
                  <tr><th>Username</th><th>Email</th><th>Role</th><th>Action</th></tr>
                </thead>
                <tbody>
                  <tr><td>ashutec</td><td>ashu@anpr.com</td><td>Admin</td><td>-</td></tr>
                  <tr><td>john_doe</td><td>john@anpr.com</td><td>User</td><td><button style={{padding:'4px 8px', borderRadius:'4px', cursor:'pointer'}}>Promote</button></td></tr>
                </tbody>
              </table>
            </div>
          </div>
        )}

      </div>
    </div>
  );
}

export default App;
